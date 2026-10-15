"""Regression coverage for telemetry provenance reaching automatic flight phase."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.metrics import update_metrics_from_telemetry
from app.live.coordinator import LiveCoordinator
from app.models.config import SimulationConfig
from app.models.flight_status import FlightPhase
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.flight_state import get_flight_state_manager
from app.services.route_eta_calculator import RouteETACalculator
from tests.conftest import default_mock_telemetry


@pytest.fixture
def detection(monkeypatch):
    clock = [datetime(2026, 10, 1, 12, tzinfo=timezone.utc)]
    frozen = SimpleNamespace(now=lambda tz: clock[0])
    monkeypatch.setattr("app.core.metrics.metric_updater.datetime", frozen)
    monkeypatch.setattr("app.services.flight_state.manager.datetime", frozen)
    manager = get_flight_state_manager()
    manager.reset()
    manager.reset_detection()
    manager.transition_phase(FlightPhase.IN_FLIGHT)
    route = ParsedRoute(
        metadata=RouteMetadata(
            name="Arrival regression", file_path="arrival.kml", point_count=2
        ),
        points=[
            RoutePoint(latitude=10, longitude=10, sequence=0),
            RoutePoint(latitude=1, longitude=1, sequence=1),
        ],
    )

    def sample():
        telemetry = default_mock_telemetry()
        telemetry.position.latitude = 1
        telemetry.position.longitude = 1
        telemetry.position.speed = 0
        telemetry.position.observed_at = clock[0]
        telemetry.position.speed_observed_at = clock[0]
        return telemetry

    yield manager, clock, route, sample
    manager.reset()
    manager.reset_detection()


@pytest.mark.parametrize(
    "missing", ["default", "stale", "invalid", "unknown_speed", "stale_speed"]
)
def test_unverified_samples_cannot_trigger_arrival(detection, missing):
    manager, clock, route, sample = detection
    # Reproduce the original geometric hazard: default GPS projects past arrival.
    assert (
        RouteETACalculator(route).get_route_progress(0, 0)["distance_remaining_meters"]
        == 0
    )
    for elapsed in [0, 61]:
        clock[0] += timedelta(seconds=elapsed)
        telemetry = sample()
        if missing == "default":
            telemetry.position.latitude = telemetry.position.longitude = 0
            telemetry.position.observed_at = None
        elif missing == "stale":
            telemetry.position.observed_at -= timedelta(seconds=10)
        elif missing == "invalid":
            telemetry.position.latitude = 91
        elif missing == "unknown_speed":
            telemetry.position.speed_observed_at = None
        else:
            telemetry.position.speed_observed_at -= timedelta(seconds=10)
        update_metrics_from_telemetry(telemetry, active_route=route)
    assert manager.get_status().phase == FlightPhase.IN_FLIGHT
    assert manager.get_status().arrival_time is None


@pytest.mark.parametrize("gap", ["gps_missing", "telemetry_missing", "stale"])
def test_missing_observation_breaks_arrival_dwell_without_resetting_phase(
    detection, gap
):
    manager, clock, route, sample = detection
    update_metrics_from_telemetry(sample(), active_route=route)
    clock[0] += timedelta(seconds=30)
    missing = sample()
    if gap == "gps_missing":
        missing.position.observed_at = None
    elif gap == "stale":
        missing.position.observed_at -= timedelta(seconds=10)
    else:
        missing = None
    update_metrics_from_telemetry(missing, active_route=route)
    clock[0] += timedelta(seconds=31)
    update_metrics_from_telemetry(sample(), active_route=route)
    assert manager.get_status().phase == FlightPhase.IN_FLIGHT
    for _ in range(12):
        clock[0] += timedelta(seconds=5)
        update_metrics_from_telemetry(sample(), active_route=route)
    assert manager.get_status().phase == FlightPhase.POST_ARRIVAL


def test_missing_observation_breaks_departure_persistence(detection):
    manager, clock, _route, sample = detection
    manager.reset()
    telemetry = sample()
    telemetry.position.speed = 100
    update_metrics_from_telemetry(telemetry)
    clock[0] += timedelta(seconds=5)
    update_metrics_from_telemetry(None)
    clock[0] += timedelta(seconds=6)
    telemetry = sample()
    telemetry.position.speed = 100
    update_metrics_from_telemetry(telemetry)
    assert manager.get_status().phase == FlightPhase.PRE_DEPARTURE
    for _ in range(2):
        clock[0] += timedelta(seconds=5)
        telemetry = sample()
        telemetry.position.speed = 100
        update_metrics_from_telemetry(telemetry)
    assert manager.get_status().phase == FlightPhase.IN_FLIGHT


@pytest.mark.parametrize("phase", [FlightPhase.PRE_DEPARTURE, FlightPhase.IN_FLIGHT])
def test_silent_live_collection_gap_restarts_detection(detection, monkeypatch, phase):
    manager, clock, route, sample = detection
    manager.reset()
    manager.reset_detection()
    if phase == FlightPhase.IN_FLIGHT:
        manager.transition_phase(phase)
    departure_time = manager.get_status().departure_time
    origin = clock[0]
    frozen = SimpleNamespace(now=lambda tz: clock[0])
    monkeypatch.setattr("app.live.coordinator.datetime", frozen)

    def dish_sample():
        telemetry = sample()
        if phase == FlightPhase.PRE_DEPARTURE:
            # Verified movement above 50 knots, including across the silent gap.
            elapsed = (clock[0] - origin).total_seconds()
            telemetry.position.longitude += elapsed * 0.001
        return telemetry

    dish = SimpleNamespace(connect=lambda: False, get_telemetry=dish_sample)
    monkeypatch.setattr("app.live.coordinator.StarlinkClient", lambda **kwargs: dish)
    coordinator = LiveCoordinator(SimulationConfig())

    def collect(elapsed):
        clock[0] = origin + timedelta(seconds=elapsed)
        update_metrics_from_telemetry(coordinator.update(), active_route=route)

    for elapsed in [0, 1, 62]:
        collect(elapsed)
    status = manager.get_status()
    assert status.phase == phase
    assert status.departure_time == departure_time
    assert status.arrival_time is None
    if phase == FlightPhase.PRE_DEPARTURE:
        assert status.speed_persistence_seconds == 0

    # Recovery starts a new dwell/persistence period; regular observations can
    # still establish the automatic phase transition after that full period.
    confirmed = (
        FlightPhase.POST_ARRIVAL
        if phase == FlightPhase.IN_FLIGHT
        else FlightPhase.IN_FLIGHT
    )
    finish = 122 if phase == FlightPhase.IN_FLIGHT else 72
    for elapsed in range(67, finish + 1, 5):
        collect(elapsed)
        assert manager.get_status().phase == (confirmed if elapsed == finish else phase)


@pytest.mark.parametrize(("gap", "confirmation"), [(9.999, 12), (10, 21)])
def test_departure_requires_continuous_observations_at_freshness_boundary(
    detection, gap, confirmation
):
    manager, clock, _route, sample = detection
    manager.reset()
    manager.reset_detection()
    origin = clock[0]
    for elapsed in [1, 1 + gap]:
        clock[0] = origin + timedelta(seconds=elapsed)
        telemetry = sample()
        telemetry.position.speed = 100
        update_metrics_from_telemetry(telemetry)
    assert manager.get_status().phase == FlightPhase.PRE_DEPARTURE
    for elapsed in ([12] if gap < 10 else [16, 21]):
        clock[0] = origin + timedelta(seconds=elapsed)
        telemetry = sample()
        telemetry.position.speed = 100
        update_metrics_from_telemetry(telemetry)
    status = manager.get_status()
    assert status.phase == FlightPhase.IN_FLIGHT
    assert status.departure_time == origin + timedelta(seconds=confirmation)


@pytest.mark.parametrize(
    ("observations", "confirmed_at"),
    [
        ([(0, 2), (1, 2), (5, 2), (10, 2), (11, 2), (12, 12), (17, 17), (22, 22)], 22),
        ([(0, 5), (1, 1), (2, 2), (7, 7), (10, 10), (12, 12)], 12),
    ],
)
def test_reused_or_backward_observations_cannot_establish_departure(
    detection, observations, confirmed_at
):
    manager, clock, _route, sample = detection
    manager.reset()
    manager.reset_detection()
    origin = clock[0]
    for processed_at, observed_at in observations:
        clock[0] = origin + timedelta(seconds=processed_at)
        telemetry = sample()
        telemetry.position.speed = 100
        # Clock skew within the allowed five seconds is fresh, but repeating
        # the same collection or moving backward cannot establish persistence.
        telemetry.position.observed_at = origin + timedelta(seconds=observed_at)
        telemetry.position.speed_observed_at = telemetry.position.observed_at
        update_metrics_from_telemetry(telemetry)
        status = manager.get_status()
        assert status.phase == (
            FlightPhase.IN_FLIGHT
            if processed_at == confirmed_at
            else FlightPhase.PRE_DEPARTURE
        )
    assert status.departure_time == origin + timedelta(seconds=confirmed_at)
