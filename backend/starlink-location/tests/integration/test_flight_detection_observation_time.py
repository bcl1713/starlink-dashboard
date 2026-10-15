"""RPC latency must not earn automatic departure or arrival persistence."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.metrics import update_metrics_from_telemetry
from app.live.client import StarlinkClient
from app.live.coordinator import LiveCoordinator
from app.models.config import SimulationConfig
from app.models.flight_status import FlightPhase
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.flight_state import get_flight_state_manager


@pytest.fixture
def live_detection(monkeypatch):
    origin = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
    clock = [origin]
    location = {"latitude": 1.0, "longitude": 1.0, "altitude": 100.0}
    history_delay = [0]
    frozen = SimpleNamespace(now=lambda tz: clock[0])
    for module in (
        "app.live.client",
        "app.live.coordinator",
        "app.core.metrics.metric_updater",
        "app.services.flight_state.manager",
    ):
        monkeypatch.setattr(f"{module}.datetime", frozen)

    # Stub only transport and clocks: collection timestamps, speed provenance,
    # freshness, continuity and phase detection all use production code.
    dish = StarlinkClient(connect_immediately=False)
    dish.context = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(dish, "connect", lambda: False)
    monkeypatch.setattr(dish, "get_status_data", lambda: ({"uptime": 3600}, {}, {}))
    monkeypatch.setattr(dish, "get_location_data", lambda: location.copy())

    def history(parse_samples=10):
        clock[0] += timedelta(seconds=history_delay[0])
        return ({}, {}, {}, {}, {}, {}, {})

    monkeypatch.setattr(dish, "get_history_stats", history)
    monkeypatch.setattr("app.live.coordinator.StarlinkClient", lambda **kwargs: dish)
    coordinator = LiveCoordinator(SimulationConfig())
    manager = get_flight_state_manager()
    manager.reset()
    manager.reset_detection()
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Observation timing", file_path="timing.kml", point_count=2
        ),
        points=[
            RoutePoint(latitude=10, longitude=10, sequence=0),
            RoutePoint(latitude=1, longitude=1, sequence=1),
        ],
    )

    def collect(observed, delay=0, moving=False):
        clock[0] = origin + timedelta(seconds=observed)
        history_delay[0] = delay
        location["longitude"] = 1 + observed * 0.001 if moving else 1
        telemetry = coordinator.update()
        assert telemetry.position.observed_at == origin + timedelta(seconds=observed)
        update_metrics_from_telemetry(telemetry, active_route=route)
        return telemetry

    yield manager, clock, origin, collect
    coordinator.shutdown()
    manager.reset()
    manager.reset_detection()


@pytest.mark.parametrize("phase", [FlightPhase.PRE_DEPARTURE, FlightPhase.IN_FLIGHT])
def test_delayed_history_rpc_cannot_complete_detection_dwell(live_detection, phase):
    manager, clock, origin, collect = live_detection
    moving = phase == FlightPhase.PRE_DEPARTURE
    if not moving:
        manager.transition_phase(phase)
    departure_time = manager.get_status().departure_time
    regular = [0, 1] if moving else [0, 1, *range(6, 52, 5)]
    delayed = 2 if moving else 52
    confirmation = 11 if moving else 61

    for observed in regular:
        collect(observed, moving=moving)
        assert manager.get_status().phase == phase

    telemetry = collect(delayed, delay=9, moving=moving)
    assert clock[0] == origin + timedelta(seconds=confirmation)
    assert telemetry.position.speed_observed_at == telemetry.position.observed_at
    if moving:
        assert telemetry.position.speed > 50
    else:
        assert telemetry.position.speed == 0
    status = manager.get_status()
    assert status.phase == phase
    assert status.departure_time == departure_time
    assert status.arrival_time is None
    if moving:
        assert status.speed_persistence_seconds == 1

    # The next collection is nine seconds later, still continuous. Only now do
    # accepted observations span the full 10-second / 60-second requirement.
    collect(confirmation, delay=1, moving=moving)
    status = manager.get_status()
    confirmed_at = origin + timedelta(seconds=confirmation)
    processed_at = confirmed_at + timedelta(seconds=1)
    if moving:
        assert status.phase == FlightPhase.IN_FLIGHT
        assert status.speed_persistence_seconds == 10
        assert status.departure_time == confirmed_at
        assert status.last_departure_check_time == processed_at
    else:
        assert status.phase == FlightPhase.POST_ARRIVAL
        assert status.departure_time == departure_time
        assert status.arrival_time == confirmed_at
        assert status.last_arrival_check_time == processed_at
