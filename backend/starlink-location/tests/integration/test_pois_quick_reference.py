"""Integration tests for POI ETA quick-reference behavior."""

from types import SimpleNamespace

from app.services.flight_state_manager import get_flight_state_manager
from app.mission.dependencies import get_route_manager


def test_pre_departure_other_poi_retains_eta(test_client, monkeypatch):
    """
    Verify that non-route POIs keep their ETA during pre-departure countdowns.

    Grafana's quick reference panel filters out rows where
    route_aware_status == "not_on_route". Pre-departure POIs of type "other"
    should therefore surface with a different status so their ETA is visible.
    """

    # Ensure we start from pre-departure state
    flight_state = get_flight_state_manager()
    flight_state.reset()

    # Provide a stub active route so POI endpoint enters route-aware branch
    stub_route = SimpleNamespace(
        metadata=SimpleNamespace(file_path="routes/test-flight.kml"),
        timing_profile=SimpleNamespace(has_timing_data=False),
    )
    stub_route_manager = SimpleNamespace(get_active_route=lambda: stub_route)

    # Override dependency instead of monkeypatching global
    test_client.app.dependency_overrides[get_route_manager] = lambda: stub_route_manager

    # Create a standalone "other" POI
    create_response = test_client.post(
        "/api/pois",
        json={
            "name": "CommKa swap",
            "latitude": 41.0,
            "longitude": -73.0,
            "icon": "marker",
            "category": "other",
            "description": "Test swap point",
        },
    )
    assert create_response.status_code == 201, create_response.text
    poi_payload = create_response.json()
    poi_id = poi_payload["id"]

    # Fetch ETAs and ensure the POI is surfaced with a pre-departure status
    eta_response = test_client.get("/api/pois/etas", params={"category": "other"})
    assert eta_response.status_code == 200, eta_response.text
    payload = eta_response.json()

    poi_rows = [poi for poi in payload.get("pois", []) if poi["name"] == "CommKa swap"]
    assert poi_rows, "CommKa swap POI should be included in quick reference payload"

    poi_entry = poi_rows[0]
    assert poi_entry["route_aware_status"] == "pre_departure"
    assert poi_entry["eta_seconds"] >= 0
    assert poi_entry["eta_type"] == flight_state.get_status().eta_mode.value

    # Cleanup created POI to avoid cross-test interference
    delete_response = test_client.delete(f"/api/pois/{poi_id}")
    assert delete_response.status_code in (200, 204), delete_response.text

    # Clear overrides
    test_client.app.dependency_overrides.clear()
