"""Adversarial arrival traces must not manufacture a landing or park."""

from datetime import timedelta

from app.services.flight_events.detector import advance_detection
from app.services.flight_events.models import DetectionPolicy, DetectionState
from tests.unit.test_flight_events import START, feed, observation


def test_go_around_resets_landing_candidate():
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    state, events = feed(state, 0, 10, speed=25, altitude=100)
    assert not events
    assert state.candidate is not None
    state, events = feed(state, 11, 45, speed=150, altitude=1500)
    assert not events
    assert state.movement == "airborne"
    assert state.candidate is None


def test_airport_overflight_and_slow_airborne_without_descent_are_not_landings():
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    state, events = feed(state, 0, 40, speed=200, altitude=1000)
    assert not events
    state, events = feed(state, 41, 90, speed=20, altitude=10000)
    assert not events
    assert state.movement == "airborne"
    assert state.uncertain


def test_duplicate_and_delayed_samples_cannot_advance_parking():
    state = DetectionState(movement="taxi_in")
    state, _ = feed(state, 0, 100)
    candidate_start = state.candidate.since
    for sample in [observation(100), observation(50)]:
        result = advance_detection(state, sample, DetectionPolicy())
        state = result.state
        assert not result.emitted_events
        assert state.candidate.since == candidate_start
        assert state.last_observed_at == START + timedelta(seconds=100)


def test_position_jump_resets_parking_even_at_zero_speed():
    state = DetectionState(movement="taxi_in")
    state, _ = feed(state, 0, 290)
    result = advance_detection(
        state, observation(291, latitude=40.01), DetectionPolicy()
    )
    assert not result.emitted_events
    assert result.state.candidate.since == START + timedelta(seconds=291)
