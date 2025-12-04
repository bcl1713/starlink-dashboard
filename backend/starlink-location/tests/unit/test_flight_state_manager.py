"""Unit tests for the FlightStateManager singleton."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.models.flight_status import ETAMode, FlightPhase
from app.models.route import ParsedRoute, RouteMetadata, RouteTimingProfile, RoutePoint
from app.services.flight_state import get_flight_state_manager


@pytest.fixture
def flight_state_manager():
    """Provide a fresh FlightStateManager instance for each test."""
    manager = get_flight_state_manager()
    with manager._lock:
        manager._status.phase = FlightPhase.PRE_DEPARTURE
        manager._status.eta_mode = ETAMode.ANTICIPATED
        manager._status.active_route_id = None
        manager._status.active_route_name = None
        manager._status.has_timing_data = False
        manager._status.scheduled_departure_time = None
        manager._status.scheduled_arrival_time = None
        manager._status.departure_time = None
        manager._status.arrival_time = None
        manager._status.speed_persistence_seconds = 0.0
        manager._status.last_departure_check_time = None
        manager._status.last_arrival_check_time = None
        manager._status.time_until_departure_seconds = None
        manager._status.time_since_departure_seconds = None
        manager._above_threshold_start_time = None
        manager._last_speed_sample_time = None
        manager._arrival_start_time = None
        manager._arrival_distance_at_start = None
        manager._phase_change_callbacks.clear()
        manager._mode_change_callbacks.clear()
    yield manager
    with manager._lock:
        manager._status.phase = FlightPhase.PRE_DEPARTURE
        manager._status.eta_mode = ETAMode.ANTICIPATED
        manager._status.active_route_id = None
        manager._status.active_route_name = None
        manager._status.has_timing_data = False
        manager._status.scheduled_departure_time = None
        manager._status.scheduled_arrival_time = None
        manager._status.departure_time = None
        manager._status.arrival_time = None
        manager._status.speed_persistence_seconds = 0.0
        manager._status.last_departure_check_time = None
        manager._status.last_arrival_check_time = None
        manager._status.time_until_departure_seconds = None
        manager._status.time_since_departure_seconds = None
        manager._above_threshold_start_time = None
        manager._last_speed_sample_time = None
        manager._arrival_start_time = None
        manager._arrival_distance_at_start = None


@pytest.fixture
def sample_route(tmp_path):
    """Provide a parsed route with timing metadata for state manager tests."""
    departure = datetime.now(timezone.utc) + timedelta(minutes=30)
    arrival = departure + timedelta(hours=2)
    metadata = RouteMetadata(
        name="Test Route",
        description="",
        file_path=str(tmp_path / "test-route.kml"),
        imported_at=datetime.now(timezone.utc),
        point_count=2,
    )
    points = [
        RoutePoint(latitude=40.0, longitude=-74.0, sequence=0),
        RoutePoint(latitude=41.0, longitude=-73.0, sequence=1),
    ]
    timing_profile = RouteTimingProfile(
        departure_time=departure,
        arrival_time=arrival,
        has_timing_data=True,
        segment_count_with_timing=2,
    )
    return ParsedRoute(
        metadata=metadata,
        points=points,
        waypoints=[],
        timing_profile=timing_profile,
    )


@pytest.fixture
def route_without_timing(tmp_path):
    """Provide a route without timing metadata to exercise edge cases."""
    metadata = RouteMetadata(
        name="No Timing",
        description="",
        file_path=str(tmp_path / "no-timing.kml"),
        imported_at=datetime.now(timezone.utc),
        point_count=1,
    )
    return ParsedRoute(
        metadata=metadata,
        points=[RoutePoint(latitude=35.0, longitude=-120.0, sequence=0)],
        waypoints=[],
        timing_profile=RouteTimingProfile(has_timing_data=False),
    )


def test_singleton_identity():
    manager_a = get_flight_state_manager()
    manager_b = get_flight_state_manager()
    assert manager_a is manager_b


def test_initial_state_pre_departure(flight_state_manager):
    status = flight_state_manager.get_status()
    assert status.phase == FlightPhase.PRE_DEPARTURE
    assert status.eta_mode == ETAMode.ANTICIPATED
    assert status.departure_time is None
    assert status.arrival_time is None


def test_departure_check_requires_persistence(flight_state_manager):
    """Departure should not trigger from a single speed sample above threshold."""
    threshold = flight_state_manager.DEPARTURE_SPEED_THRESHOLD_KNOTS

    triggered = flight_state_manager.check_departure(threshold + 5.0)
    assert triggered is False

    # Drop below threshold to reset persistence tracking
    flight_state_manager.check_departure(threshold - 20.0)

    status = flight_state_manager.get_status()
    assert status.phase == FlightPhase.PRE_DEPARTURE
    assert status.speed_persistence_seconds == 0.0


def test_check_departure_ignored_when_already_in_flight(flight_state_manager):
    """Ensure we do not re-trigger departure once airborne."""
    flight_state_manager.transition_phase(FlightPhase.IN_FLIGHT)
    triggered = flight_state_manager.check_departure(
        flight_state_manager.DEPARTURE_SPEED_THRESHOLD_KNOTS + 15.0
    )
    assert triggered is False
    assert flight_state_manager.get_status().phase == FlightPhase.IN_FLIGHT


def test_speed_persistence_triggers_departure(flight_state_manager):
    with flight_state_manager._lock:
        flight_state_manager._above_threshold_start_time = datetime.now(
            timezone.utc
        ) - timedelta(
            seconds=flight_state_manager.DEPARTURE_SPEED_PERSISTENCE_SECONDS + 1
        )
    triggered = flight_state_manager.check_departure(
        flight_state_manager.DEPARTURE_SPEED_THRESHOLD_KNOTS + 5
    )
    status = flight_state_manager.get_status()
    assert triggered is True
    assert status.phase == FlightPhase.IN_FLIGHT
    assert status.eta_mode == ETAMode.ESTIMATED
    assert status.departure_time is not None


def test_transition_phase_updates_eta_mode(flight_state_manager):
    transitioned = flight_state_manager.transition_phase(FlightPhase.IN_FLIGHT)
    assert transitioned is True
    status = flight_state_manager.get_status()
    assert status.phase == FlightPhase.IN_FLIGHT
    assert status.eta_mode == ETAMode.ESTIMATED

    transitioned_back = flight_state_manager.transition_phase(FlightPhase.PRE_DEPARTURE)
    assert transitioned_back is True
    status_back = flight_state_manager.get_status()
    assert status_back.phase == FlightPhase.PRE_DEPARTURE
    assert status_back.eta_mode == ETAMode.ANTICIPATED


def test_arrival_detection_sets_post_arrival(flight_state_manager):
    flight_state_manager.transition_phase(FlightPhase.IN_FLIGHT)
    with flight_state_manager._lock:
        flight_state_manager._arrival_start_time = datetime.now(
            timezone.utc
        ) - timedelta(seconds=flight_state_manager.ARRIVAL_DWELL_TIME_SECONDS + 1)
        flight_state_manager._arrival_distance_at_start = 80.0

    triggered = flight_state_manager.check_arrival(
        distance_to_destination_m=50.0,
        current_speed_knots=10.0,
    )
    status = flight_state_manager.get_status()
    assert triggered is True
    assert status.phase == FlightPhase.POST_ARRIVAL
    assert status.arrival_time is not None


def test_transition_same_phase_returns_false(flight_state_manager):
    transitioned = flight_state_manager.transition_phase(FlightPhase.PRE_DEPARTURE)
    assert transitioned is False


def test_reset_returns_to_pre_departure(flight_state_manager):
    flight_state_manager.transition_phase(FlightPhase.IN_FLIGHT)
    flight_state_manager.transition_phase(FlightPhase.POST_ARRIVAL)
    flight_state_manager.reset()
    status = flight_state_manager.get_status()
    assert status.phase == FlightPhase.PRE_DEPARTURE
    assert status.eta_mode == ETAMode.ANTICIPATED
    assert status.departure_time is None
    assert status.arrival_time is None


def test_update_route_context_sets_metadata(flight_state_manager, sample_route):
    flight_state_manager.update_route_context(
        sample_route, auto_reset=True, reason="test"
    )
    status = flight_state_manager.get_status()

    assert status.active_route_id == Path(sample_route.metadata.file_path).stem
    assert status.active_route_name == sample_route.metadata.name
    assert status.has_timing_data is True
    assert status.scheduled_departure_time == sample_route.timing_profile.departure_time
    assert status.scheduled_arrival_time == sample_route.timing_profile.arrival_time
    assert status.phase == FlightPhase.PRE_DEPARTURE
    assert status.time_until_departure_seconds is not None


def test_update_route_context_same_route_no_reset(flight_state_manager, sample_route):
    flight_state_manager.update_route_context(
        sample_route, auto_reset=True, reason="initial"
    )
    flight_state_manager.transition_phase(FlightPhase.IN_FLIGHT)

    flight_state_manager.update_route_context(
        sample_route, auto_reset=False, reason="reload"
    )
    status = flight_state_manager.get_status()

    assert status.phase == FlightPhase.IN_FLIGHT
    assert status.active_route_id == Path(sample_route.metadata.file_path).stem


def test_clear_route_context(flight_state_manager, sample_route):
    flight_state_manager.update_route_context(sample_route, auto_reset=True)
    flight_state_manager.clear_route_context()

    status = flight_state_manager.get_status()
    assert status.active_route_id is None
    assert status.active_route_name is None
    assert status.scheduled_departure_time is None
    assert status.has_timing_data is False


def test_update_route_context_without_timing_data(
    flight_state_manager, route_without_timing
):
    """Routes lacking timing metadata should not populate schedule fields."""
    flight_state_manager.update_route_context(
        route_without_timing, auto_reset=True, reason="no-timing"
    )
    status = flight_state_manager.get_status()

    assert status.active_route_id == Path(route_without_timing.metadata.file_path).stem
    assert status.has_timing_data is False
    assert status.scheduled_departure_time is None
    assert status.scheduled_arrival_time is None


def test_thread_safe_access_under_load(flight_state_manager):
    """Concurrent reads/writes should not raise or corrupt state."""

    def toggle_phases():
        for _ in range(10):
            flight_state_manager.transition_phase(FlightPhase.IN_FLIGHT)
            flight_state_manager.transition_phase(FlightPhase.POST_ARRIVAL)
            flight_state_manager.reset()

    def read_status():
        for _ in range(50):
            status = flight_state_manager.get_status()
            assert isinstance(status.phase, FlightPhase)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(toggle_phases),
            executor.submit(toggle_phases),
            executor.submit(read_status),
            executor.submit(read_status),
        ]
        for future in futures:
            future.result()

    assert flight_state_manager.get_status().phase == FlightPhase.PRE_DEPARTURE


def test_trigger_departure_sets_timestamp(flight_state_manager):
    requested = datetime.now(timezone.utc)
    triggered = flight_state_manager.trigger_departure(requested, reason="manual test")

    assert triggered is True
    status = flight_state_manager.get_status()
    assert status.phase == FlightPhase.IN_FLIGHT
    assert status.departure_time is not None
    delta = abs(status.departure_time - requested)
    assert delta.total_seconds() < 1.5
    assert status.time_since_departure_seconds is not None
    assert status.time_until_departure_seconds == 0.0


def test_trigger_arrival_sets_timestamp(flight_state_manager):
    flight_state_manager.trigger_departure()
    requested = datetime.now(timezone.utc)

    triggered = flight_state_manager.trigger_arrival(requested, reason="arrived")
    assert triggered is True

    status = flight_state_manager.get_status()
    assert status.phase == FlightPhase.POST_ARRIVAL
    assert status.arrival_time is not None
    delta = abs(status.arrival_time - requested)
    assert delta.total_seconds() < 1.5
