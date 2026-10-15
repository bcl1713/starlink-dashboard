"""All public estimates share the published mission clock and real freshness."""

from datetime import datetime, timezone

import pytest

from app.models.poi import POICreate
from tests.integration.test_simulation_run_api import api, start

__all__ = ["api"]


@pytest.fixture
def timed_api(api, monkeypatch):
    import app.core.metrics.metric_updater as metrics
    from app.api import active_x_link, flight_status, overview_upcoming_pois
    from app.api.pois import etas
    from app.api.routes import eta

    client, service, clocks = api
    clocks.utc = datetime.now(timezone.utc)
    client.app.state.coordinator = service.coordinator
    client.app.include_router(flight_status.router)
    client.app.include_router(overview_upcoming_pois.router)
    client.app.include_router(active_x_link.router)
    client.app.include_router(etas.router, prefix="/api/pois")
    client.app.include_router(eta.router, prefix="/api/routes")
    monkeypatch.setattr(etas, "_coordinator", service.coordinator)
    monkeypatch.setattr(overview_upcoming_pois, "_utc_now", clocks.utc_now)

    def publish(telemetry, tick):
        from app.simulation.run_timing import mission_time_context

        metrics.update_metrics_from_telemetry(
            telemetry,
            active_route=tick.plan.artifacts.route,
            poi_manager=service.poi_manager,
            mission_context=mission_time_context(tick.status),
            simulation_plan=tick.plan,
            simulation_frame=tick.frame,
        )

    service.publish = publish
    return client, service, clocks


def test_api_estimates_and_metrics_share_simulated_now(timed_api):
    from app.core.metrics.prometheus_metrics import starlink_eta_poi_seconds

    client, service, clocks = timed_api
    assert start(client).status_code == 200
    clocks.elapsed = 12
    service.collect(service.coordinator, service.publish)
    flight = client.get("/api/flight-status").json()
    assert flight["time_since_departure_seconds"] == 120
    assert flight["mission_time"]["simulation_time"] == "2025-01-01T01:02:00Z"
    assert flight["timestamp"].startswith("2026-")
    upcoming = client.get("/api/overview/upcoming-pois").json()
    arrival = next(poi for poi in upcoming["pois"] if poi["kind"] == "arrival")
    assert upcoming["position_state"] == "fresh"
    assert upcoming["mission_time"]["run_id"] == flight["mission_time"]["run_id"]
    assert arrival["eta_seconds"] == 1080
    assert arrival["estimated_arrival_time"] == "2025-01-01T01:20:00Z"
    assert upcoming["calculated_at"].startswith("2026-")
    pois = client.get("/api/pois/etas").json()
    arrival_poi = next(poi for poi in pois["pois"] if poi["name"] == "Arrival")
    assert arrival_poi["eta_seconds"] == 1080
    assert pois["timestamp"].startswith("2026-")
    route = client.get(
        "/api/routes/replay/eta/location",
        params={
            "latitude": 0,
            "longitude": 2,
            "current_position_lat": 0,
            "current_position_lon": 0.4,
        },
    ).json()
    assert route["estimated_time_remaining_seconds"] == 1080
    assert (
        starlink_eta_poi_seconds.labels(
            name="Arrival", category="mission-event", eta_type="estimated"
        )._value.get()
        == 1080
    )
    clocks.elapsed = 120
    service.collect(service.coordinator, service.publish)
    assert (
        client.get("/api/flight-status").json()["time_since_departure_seconds"] == 1200
    )
    assert client.get("/api/flight-status").json()["phase"] == "post_arrival"
    assert (
        client.get("/api/overview/upcoming-pois").json()["mission_time"]["phase"]
        == "post_arrival"
    )


def test_paced_handoff_reads_do_not_mutate_live_tracker(timed_api):
    from app.mission.models import XTransition
    from app.mission.storage import load_mission_v2, save_mission_v2
    from app.services import active_x_handoff

    client, service, clocks = timed_api
    mission = load_mission_v2("mission-1")
    mission.legs[0].transports.x_transitions = [
        XTransition(id="swap", latitude=0, longitude=1, target_satellite_id="X-2")
    ]
    save_mission_v2(mission)
    for name, lon in [("X-1", -30), ("X-2", 30)]:
        service.poi_manager.create_poi(
            POICreate(name=name, latitude=0, longitude=lon, category="satellite")
        )
    active_x_handoff.reset_x_handoff_state()
    assert start(client).status_code == 200
    clocks.elapsed = 30
    service.collect(service.coordinator, service.publish)
    for _ in range(10):
        assert client.get("/api/active-x-link").json()["satellite_id"] == "X-2"
    assert not active_x_handoff._HANDOFF_TRACKERS
    assert start(client).status_code == 200
    assert client.get("/api/active-x-link").json()["satellite_id"] == "X-1"
    assert not active_x_handoff._HANDOFF_TRACKERS


@pytest.mark.parametrize("path", ["/api/flight-status", "/api/flight-status/arrive"])
def test_manual_flight_changes_rejected_during_replay(timed_api, path):
    client, service, _clocks = timed_api
    assert start(client).status_code == 200
    before = service.status().run
    assert client.post(path, json={}).status_code == 409
    assert service.status().run == before
