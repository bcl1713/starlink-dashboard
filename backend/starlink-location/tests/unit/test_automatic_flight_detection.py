"""Regression coverage for telemetry provenance reaching automatic flight phase."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.core.metrics import update_metrics_from_telemetry
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
    clock[0] += timedelta(seconds=61)
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
    clock[0] += timedelta(seconds=11)
    telemetry = sample()
    telemetry.position.speed = 100
    update_metrics_from_telemetry(telemetry)
    assert manager.get_status().phase == FlightPhase.IN_FLIGHT
