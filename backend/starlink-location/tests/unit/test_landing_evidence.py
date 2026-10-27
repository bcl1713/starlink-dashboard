"""Landing evidence uses independent fresh samples, not a slow descent plateau."""

from datetime import timedelta

import pytest

from app.services.flight_events.detector import advance_detection
from app.services.flight_events.models import DetectionPolicy, DetectionState
from tests.unit.test_flight_events import START, observation


@pytest.mark.parametrize("trend", [-2, 2])
def test_sustained_altitude_trend_is_not_a_landing(trend):
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    for second in range(60):
        result = advance_detection(
            state,
            observation(second, speed=25, altitude=500 + second * trend),
            DetectionPolicy(),
        )
        state = result.state
        assert not result.emitted_events
    assert state.movement == "airborne"
    assert state.uncertain


def test_repeated_altitude_timestamp_cannot_earn_landing_dwell():
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    # A trace freezes just before confirmation. Repeating a still-fresh
    # altitude must not supply the final independent observation.
    for second in range(60):
        sampled = START + timedelta(seconds=min(second, 19))
        result = advance_detection(
            state,
            observation(second, speed=25, altitude_observed_at=sampled),
            DetectionPolicy(),
        )
        state = result.state
        assert not result.emitted_events
    assert state.movement == "airborne"


def test_noisy_sloping_runway_keeps_occurrence_and_confirmation_separate():
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    events = []
    for second in range(40):
        result = advance_detection(
            state,
            observation(
                second,
                speed=25,
                altitude=500 + 0.3 * second + (5 if second % 2 else -5),
            ),
            DetectionPolicy(),
        )
        state = result.state
        events.extend(result.emitted_events)
    assert [event.kind for event in events] == ["landed"]
    assert events[0].occurred_at == START
    assert events[0].detected_at == START + timedelta(seconds=20)
    assert events[0].source == "inferred"


def test_landing_candidate_uses_total_altitude_range():
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    for second in range(60):
        altitude = 500 if second % 3 == 0 else 560 if second % 3 == 1 else 440
        result = advance_detection(
            state, observation(second, speed=25, altitude=altitude), DetectionPolicy()
        )
        state = result.state
        assert not result.emitted_events


@pytest.mark.parametrize("discontinuity", ["acceleration", "outside_destination"])
def test_repeated_altitude_does_not_hide_go_around(discontinuity):
    state = DetectionState(movement="airborne", max_airborne_altitude=10000)
    for second in range(19):
        state = advance_detection(
            state, observation(second, speed=25), DetectionPolicy()
        ).state
    disrupted = observation(
        19,
        speed=100 if discontinuity == "acceleration" else 25,
        distance=50000 if discontinuity == "outside_destination" else 1000,
        altitude_observed_at=START + timedelta(seconds=18),
    )
    state = advance_detection(state, disrupted, DetectionPolicy()).state
    result = advance_detection(state, observation(20, speed=25), DetectionPolicy())
    assert not result.emitted_events
    assert result.state.candidate.since == START + timedelta(seconds=20)
