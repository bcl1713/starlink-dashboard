"""Integration tests for the flight status API."""

from datetime import datetime, timezone


def test_get_flight_status_payload_contains_metadata(test_client):
    response = test_client.get("/api/flight-status")
    assert response.status_code == 200

    payload = response.json()
    expected_keys = {
        "phase",
        "eta_mode",
        "time_until_departure_seconds",
        "time_since_departure_seconds",
        "active_route_id",
        "active_route_name",
        "has_timing_data",
        "scheduled_departure_time",
        "scheduled_arrival_time",
        "departure_time",
        "arrival_time",
        "timestamp",
    }

    assert expected_keys.issubset(payload.keys())
    assert payload["phase"] in {"pre_departure", "in_flight", "post_arrival"}
    assert payload["eta_mode"] in {"anticipated", "estimated"}


def test_manual_depart_and_arrive_endpoints(test_client):
    # Ensure clean slate
    reset_resp = test_client.post("/api/flight-status")
    assert reset_resp.status_code == 200

    depart_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    depart_resp = test_client.post(
        "/api/flight-status/depart",
        json={"timestamp": depart_timestamp, "reason": "test"},
    )
    assert depart_resp.status_code == 200
    depart_payload = depart_resp.json()
    assert depart_payload["phase"] == "in_flight"
    assert depart_payload["eta_mode"] == "estimated"
    assert depart_payload["departure_time"] is not None

    arrive_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    arrive_resp = test_client.post(
        "/api/flight-status/arrive",
        json={"timestamp": arrive_timestamp, "reason": "test"},
    )
    assert arrive_resp.status_code == 200
    arrive_payload = arrive_resp.json()
    assert arrive_payload["phase"] == "post_arrival"
    assert arrive_payload["arrival_time"] is not None

    # Reset at end to avoid leaking state to other tests
    cleanup_resp = test_client.post("/api/flight-status")
    assert cleanup_resp.status_code == 200
