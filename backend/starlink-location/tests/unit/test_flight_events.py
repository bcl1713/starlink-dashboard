"""Synthetic movement traces prove transitions, not field calibration."""

from datetime import datetime, timedelta, timezone

from app.services.flight_events.detector import advance_detection
from app.services.flight_events.models import (
    DetectionPolicy,
    DetectionState,
    FlightObservation,
)

START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def observation(second, speed=0, altitude=100, distance=1000, **changes):
    now = START + timedelta(seconds=second)
    values = {
        "observed_at": now,
        "position_observed_at": now,
        "speed_observed_at": now,
        "altitude_observed_at": now,
        "altitude_validity_source": "test",
        "altitude_usable": True,
        "latitude": 40,
        "longitude": -70,
        "speed_knots": speed,
        "altitude_feet": altitude,
        "destination_distance_m": distance,
        "source_mode": "live",
        "mission_id": "m",
        "leg_id": "l",
        "route_id": "r",
    }
    return FlightObservation(**(values | changes))


def feed(state, begin, end, **values):
    events = []
    for second in range(begin, end + 1):
        result = advance_detection(
            state, observation(second, **values), DetectionPolicy()
        )
        state = result.state
        events.extend(result.emitted_events)
    return state, events


def test_full_flight_and_dv_reposition():
    state, _ = feed(DetectionState(), 0, 300)
    assert state.movement == "parked"
    state, events = feed(state, 301, 320, speed=10)
    assert events[0].kind == "off_blocks"
    assert events[0].occurred_at == START + timedelta(seconds=301)
    state, events = feed(state, 321, 350, speed=120, altitude=500)
    assert state.movement == "airborne"
    assert [e.kind for e in events] == ["takeoff"]
    state, _ = feed(state, 351, 360, speed=200, altitude=10000)
    state, events = feed(state, 361, 400, speed=25, altitude=100)
    assert [e.kind for e in events] == ["landed"]
    state, events = feed(state, 401, 710)
    assert state.destination_complete
    assert [e.kind for e in events] == ["on_blocks"]
    state, events = feed(state, 711, 3450, speed=10)
    assert state.movement == "parked"
    assert state.destination_complete
    assert not events


def test_fuel_stop_remains_open():
    state = DetectionState(movement="taxi_in", uncertain=False)
    state, _events = feed(state, 0, 310, distance=50000)
    assert state.movement == "parked_at_stop"
    assert not state.destination_complete
    state, _events = feed(state, 311, 340, speed=10, distance=50000)
    assert state.movement == "taxi_out"


def test_startup_airborne_resumes_current_movement_without_inventing_events():
    state = DetectionState()
    state, events = feed(state, 0, 19, speed=150, altitude=5000)
    assert not events
    assert state.movement == "unknown"
    assert state.uncertain
    state, events = feed(state, 20, 40, speed=150, altitude=5000)
    assert state.movement == "airborne"
    assert not events


def test_stale_altitude_does_not_invent_landing_events():
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    for second in range(50, 100):
        result = advance_detection(
            state,
            observation(second, speed=20, altitude_observed_at=START),
            DetectionPolicy(),
        )
        state = result.state
        assert not result.emitted_events
    assert state.movement == "airborne"
    assert state.uncertain


def test_gap_and_taxi_hold_reset_candidates():
    state = DetectionState(movement="taxi_in", uncertain=False)
    state, _ = feed(state, 0, 100)
    state, _ = feed(state, 101, 110, speed=5)
    state, events = feed(state, 111, 300)
    assert not events
    result = advance_detection(state, observation(400), DetectionPolicy())
    assert result.state.candidate.since == START + timedelta(seconds=400)
    assert not result.emitted_events


def test_received_age_does_not_refresh_old_position():
    sample = observation(0, speed=100, received_at=START + timedelta(seconds=60))
    assert not sample.usable_motion
    assert not sample.usable_altitude
