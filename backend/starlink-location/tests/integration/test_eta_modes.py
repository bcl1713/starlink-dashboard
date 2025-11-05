"""Integration tests covering flight status transitions and ETA metadata."""

import textwrap
from uuid import uuid4


def _upload_stub_route(test_client, prefix: str) -> dict:
    """Upload a minimal KML route without timing metadata and return response JSON."""
    route_name = f"{prefix}-{uuid4().hex[:6]}"
    filename = f"{route_name}.kml"
    kml_content = textwrap.dedent(
        f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
          <Document>
            <name>{route_name}</name>
            <Placemark>
              <LineString>
                <coordinates>
                  -73.0000,40.0000,0
                  -72.5000,40.5000,0
                  -72.0000,41.0000,0
                </coordinates>
              </LineString>
            </Placemark>
          </Document>
        </kml>
        """
    ).encode("utf-8")

    files = {
        "file": (
            filename,
            kml_content,
            "application/vnd.google-earth.kml+xml",
        )
    }
    response = test_client.post("/api/routes/upload", files=files)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["id"], "Upload response must include route identifier"
    return payload


def test_flight_status_manual_transitions(test_client):
    """Verify manual depart/arrive endpoints drive flight phase + ETA mode."""
    # Reset to known state
    reset_resp = test_client.post("/api/flight-status")
    assert reset_resp.status_code == 200
    reset_payload = reset_resp.json()
    assert reset_payload["phase"] == "pre_departure"
    assert reset_payload["eta_mode"] == "anticipated"

    # Trigger departure
    depart_resp = test_client.post(
        "/api/flight-status/depart",
        json={"reason": "integration-test"},
    )
    assert depart_resp.status_code == 200
    depart_payload = depart_resp.json()
    assert depart_payload["phase"] == "in_flight"
    assert depart_payload["eta_mode"] == "estimated"
    assert isinstance(depart_payload["departure_time"], str)

    # Trigger arrival
    arrive_resp = test_client.post(
        "/api/flight-status/arrive",
        json={"reason": "integration-test"},
    )
    assert arrive_resp.status_code == 200
    arrive_payload = arrive_resp.json()
    assert arrive_payload["phase"] == "post_arrival"
    assert arrive_payload["eta_mode"] == "estimated"
    assert isinstance(arrive_payload["arrival_time"], str)

    # Reset again to avoid leaking state for downstream tests
    cleanup_resp = test_client.post("/api/flight-status")
    assert cleanup_resp.status_code == 200


def test_poi_eta_endpoint_includes_eta_metadata(test_client):
    """Ensure POI ETAs expose eta_type / flight phase metadata."""
    response = test_client.get("/api/pois/etas")
    assert response.status_code == 200

    payload = response.json()
    assert "pois" in payload
    for poi in payload["pois"]:
        # New metadata fields should always be present
        assert "eta_type" in poi
        assert "is_pre_departure" in poi
        assert "flight_phase" in poi


def test_metrics_exposes_eta_type_labels(test_client):
    """Prometheus metrics should include eta_type label for POI distance/ETA."""
    # Seed a POI so the metrics exporter produces ETA samples with labels
    poi_resp = test_client.post(
        "/api/pois",
        json={
            "name": f"Metrics Test POI {uuid4().hex[:4]}",
            "latitude": 40.0,
            "longitude": -73.0,
            "icon": "marker",
            "category": "test",
        },
    )
    assert poi_resp.status_code == 201
    poi_id = poi_resp.json()["id"]

    metrics_resp = test_client.get("/metrics")
    assert metrics_resp.status_code == 200
    body = metrics_resp.text

    assert "starlink_eta_poi_seconds" in body
    assert 'eta_type="' in body
    assert "starlink_distance_to_poi_meters" in body

    # Cleanup POI to avoid leaking state between tests
    delete_resp = test_client.delete(f"/api/pois/{poi_id}")
    assert delete_resp.status_code in (200, 204)


def test_eta_modes_fallback_without_timing_data(test_client):
    """Routes lacking timing metadata should fall back to distance-based ETAs."""
    # Ensure clean baseline
    reset_resp = test_client.post("/api/flight-status")
    assert reset_resp.status_code == 200

    route_payload = _upload_stub_route(test_client, "no-timing-route")
    route_id = route_payload["id"]

    activate_resp = test_client.post(f"/api/routes/{route_id}/activate")
    assert activate_resp.status_code == 200
    assert activate_resp.json()["is_active"] is True
    assert activate_resp.json()["has_timing_data"] is False

    poi_name = f"Fallback POI {uuid4().hex[:4]}"
    poi_resp = test_client.post(
        "/api/pois",
        json={
            "name": poi_name,
            "latitude": 40.5,
            "longitude": -72.5,
            "icon": "marker",
            "category": "test",
            "route_id": route_id,
        },
    )
    assert poi_resp.status_code == 201, poi_resp.text
    poi_id = poi_resp.json()["id"]

    etas_resp = test_client.get("/api/pois/etas")
    assert etas_resp.status_code == 200
    pois_payload = etas_resp.json()
    assert "pois" in pois_payload

    target_entry = next(
        (entry for entry in pois_payload["pois"] if entry["name"] == poi_name),
        None,
    )
    assert target_entry is not None, "Expected POI entry missing from ETA response"

    assert target_entry["eta_type"] == "anticipated"
    assert target_entry["flight_phase"] == "pre_departure"
    assert target_entry["eta_seconds"] is not None
    assert target_entry["eta_seconds"] >= 0  # Fallback uses positive default speed

    detail_resp = test_client.get(f"/api/routes/{route_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["has_timing_data"] is False
    assert detail.get("timing_profile") in (None, {}) or detail["timing_profile"].get("has_timing_data") is False

    # Cleanup to avoid leaking state into unrelated tests
    delete_resp = test_client.delete(f"/api/pois/{poi_id}")
    assert delete_resp.status_code in (200, 204)
    test_client.post("/api/routes/deactivate")
    test_client.post("/api/flight-status")


def test_route_activation_resets_flight_state(test_client):
    """Activating a new route should reset flight state back to pre-departure."""
    reset_resp = test_client.post("/api/flight-status")
    assert reset_resp.status_code == 200

    first_route = _upload_stub_route(test_client, "reset-test-a")
    second_route = _upload_stub_route(test_client, "reset-test-b")

    activate_first = test_client.post(f"/api/routes/{first_route['id']}/activate")
    assert activate_first.status_code == 200, activate_first.text
    assert activate_first.json()["is_active"] is True

    depart_resp = test_client.post(
        "/api/flight-status/depart",
        json={"reason": "integration-test"},
    )
    assert depart_resp.status_code == 200
    assert depart_resp.json()["phase"] == "in_flight"

    activate_second = test_client.post(f"/api/routes/{second_route['id']}/activate")
    assert activate_second.status_code == 200, activate_second.text
    assert activate_second.json()["is_active"] is True
    assert activate_second.json()["id"] == second_route["id"]

    status_resp = test_client.get("/api/flight-status")
    assert status_resp.status_code == 200
    status_payload = status_resp.json()

    assert status_payload["phase"] == "pre_departure"
    assert status_payload["eta_mode"] == "anticipated"
    assert status_payload["active_route_id"] == second_route["id"]
    assert status_payload["departure_time"] is None
    assert status_payload["arrival_time"] is None

    # Cleanup to ensure other tests start with neutral state
    test_client.post("/api/routes/deactivate")
    test_client.post("/api/flight-status")
