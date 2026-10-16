"""Operator event commands validate identity, ordering and correction targets."""

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.flight_events import router
from app.services.flight_events.live_adapter import FlightEventRuntime
from tests.unit.test_flight_events import START


def test_manual_sequence_and_targeted_correction(tmp_path, monkeypatch):
    app = FastAPI()
    app.state.flight_event_runtime = FlightEventRuntime(tmp_path)
    app.include_router(router)
    monkeypatch.setattr(
        "app.api.flight_events.load_mission_v2",
        lambda _: SimpleNamespace(legs=[SimpleNamespace(id="l")]),
    )
    client = TestClient(app)
    base = "/api/v2/missions/m/legs/l/flight-events"
    result = client.post(
        base,
        json={
            "kind": "off_blocks",
            "occurred_at": START.isoformat(),
            "reason": "observed",
        },
    )
    assert result.status_code == 200
    event = result.json()
    result = client.patch(
        base + "/" + event["event_id"],
        json={
            "expected_revision": 1,
            "occurred_at": START.isoformat(),
            "reason": "corrected",
        },
    )
    assert result.status_code == 200
    assert result.json()["revision"] == 2
    assert (
        client.patch(
            base + "/" + event["event_id"],
            json={
                "expected_revision": 1,
                "occurred_at": START.isoformat(),
                "reason": "stale",
            },
        ).status_code
        == 409
    )
    assert client.get("/api/v2/missions/m/legs/other/flight-events").status_code == 404
