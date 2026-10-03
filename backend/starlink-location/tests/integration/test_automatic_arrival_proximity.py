"""Automatic arrival requires proximity to the actual final route waypoint."""

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
from app.services.kml.geometry import haversine_distance
from app.services.route_eta_calculator import RouteETACalculator


@pytest.fixture
def live_arrival(monkeypatch):
    origin = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    clock = [origin]
    location = {"latitude": 1.0, "longitude": 1.0, "altitude": 100.0}
    frozen = SimpleNamespace(now=lambda tz: clock[0])
    for module in (
        "app.live.client",
        "app.live.coordinator",
        "app.core.metrics.metric_updater",
        "app.services.flight_state.manager",
    ):
        monkeypatch.setattr(f"{module}.datetime", frozen)

    # Only transport and time are stubbed. GPS provenance, derived live speed,
    # observation continuity and the metrics-to-phase path use production code.
    dish = StarlinkClient(connect_immediately=False)
    dish.context = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(dish, "connect", lambda: False)
    monkeypatch.setattr(dish, "get_status_data", lambda: ({"uptime": 3600}, {}, {}))
    monkeypatch.setattr(dish, "get_location_data", lambda: location.copy())
    monkeypatch.setattr(
        dish, "get_history_stats", lambda **kwargs: ({}, {}, {}, {}, {}, {}, {})
    )
    monkeypatch.setattr("app.live.coordinator.StarlinkClient", lambda **kwargs: dish)
    coordinator = LiveCoordinator(SimulationConfig())
    manager = get_flight_state_manager()
    manager.reset()
    manager.reset_detection()
    manager.transition_phase(FlightPhase.IN_FLIGHT)
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Arrival proximity", file_path="proximity.kml", point_count=2
        ),
        points=[
            RoutePoint(latitude=10, longitude=10, sequence=0),
            RoutePoint(latitude=1, longitude=1, sequence=1),
        ],
    )

    def collect(elapsed, position):
        clock[0] = origin + timedelta(seconds=elapsed)
        location["latitude"], location["longitude"] = position
        telemetry = coordinator.update()
        assert telemetry.position.observed_at == clock[0]
        if elapsed > 0:
            assert telemetry.position.speed_observed_at == clock[0]
        update_metrics_from_telemetry(telemetry, active_route=route)
        return manager.get_status()

    yield manager, route, origin, collect
    coordinator.shutdown()
    manager.reset()
    manager.reset_detection()


@pytest.mark.parametrize(
    "position",
    [(0, 0), (1, 0), (1.001, 1)],
    ids=["endpoint-overshoot", "cross-track", "outside-100m-radius"],
)
def test_projected_arrival_zone_cannot_establish_distant_arrival(
    live_arrival, position
):
    manager, route, _origin, collect = live_arrival
    destination = route.points[-1]
    assert (
        haversine_distance(*position, destination.latitude, destination.longitude)
        > manager.ARRIVAL_DISTANCE_THRESHOLD_M
    )
    # These valid GPS positions project within the old arrival zone despite
    # being outside the actual destination radius (157 km for the overshoot).
    assert (
        RouteETACalculator(route).get_route_progress(*position)[
            "distance_remaining_meters"
        ]
        <= manager.ARRIVAL_DISTANCE_THRESHOLD_M
    )
    for elapsed in range(64):
        status = collect(elapsed, position)
        assert status.phase == FlightPhase.IN_FLIGHT
        assert status.arrival_time is None


@pytest.mark.parametrize(
    "position",
    [(1, 1), (1.0004, 1.0004), (1.0005, 0.9995)],
    ids=["at-destination", "near-destination", "near-destination-off-route"],
)
def test_destination_proximity_confirms_arrival_after_full_dwell(
    live_arrival, position
):
    manager, route, origin, collect = live_arrival
    destination = route.points[-1]
    assert (
        haversine_distance(*position, destination.latitude, destination.longitude)
        < manager.ARRIVAL_DISTANCE_THRESHOLD_M
    )
    for elapsed in range(62):
        status = collect(elapsed, position)
        # The first live sample has no verified speed. Dwell begins at t=1.
        assert status.phase == (
            FlightPhase.POST_ARRIVAL if elapsed == 61 else FlightPhase.IN_FLIGHT
        )
        assert status.arrival_time == (
            origin + timedelta(seconds=61) if elapsed == 61 else None
        )


def test_leaving_destination_radius_restarts_arrival_dwell(live_arrival):
    _manager, _route, origin, collect = live_arrival
    for elapsed in range(31):
        assert collect(elapsed, (1, 1)).phase == FlightPhase.IN_FLIGHT
    assert collect(31, (0, 0)).phase == FlightPhase.IN_FLIGHT
    for elapsed in range(32, 93):
        status = collect(elapsed, (1, 1))
        assert status.phase == (
            FlightPhase.POST_ARRIVAL if elapsed == 92 else FlightPhase.IN_FLIGHT
        )
        assert status.arrival_time == (
            origin + timedelta(seconds=92) if elapsed == 92 else None
        )
