"""Cold live startup restores timing without manufacturing ground history."""

from datetime import timedelta

import pytest

from app.models.flight_status import ETAMode, FlightPhase
from app.services.flight_events.detector import advance_detection
from app.services.flight_events.live_adapter import FlightEventRuntime
from app.services.flight_events.models import DetectionPolicy, DetectionState
from app.services.flight_state import get_flight_state_manager
from tests.unit.test_flight_events import START, observation


@pytest.mark.parametrize(
    "changes",
    [
        {"altitude_usable": False},
        {"altitude_observed_at": START - timedelta(minutes=1)},
        {"position_observed_at": START - timedelta(minutes=1)},
        {"speed_observed_at": START - timedelta(minutes=1)},
        {"source_mode": "simulation"},
        {"speed_knots": 25},
        {"speed_knots": 85, "altitude_feet": 0},
        {"speed_knots": 150, "altitude_feet": 100},
    ],
)
def test_recovery_requires_fresh_live_airborne_evidence(changes):
    state = DetectionState()
    for second in range(41):
        sample = observation(second, speed=150, altitude=5000).model_copy(
            update=changes
        )
        result = advance_detection(state, sample, DetectionPolicy())
        state = result.state
        assert state.movement == "unknown"
        assert not result.emitted_events


def test_recovery_rejects_repeated_altitude_and_restarts_after_gap():
    state = DetectionState()
    for second in range(21):
        result = advance_detection(
            state,
            observation(second, speed=150, altitude=5000, altitude_observed_at=START),
            DetectionPolicy(),
        )
        state = result.state
    assert state.movement == "unknown"
    for second in [30, 35, 40, 55, 60, 65, 70]:
        result = advance_detection(
            state, observation(second, speed=150, altitude=5000), DetectionPolicy()
        )
        state = result.state
        assert state.movement == "unknown"
    result = advance_detection(
        state, observation(75, speed=150, altitude=5000), DetectionPolicy()
    )
    assert result.state.movement == "airborne"
    assert not result.emitted_events


@pytest.mark.parametrize("movement", ["parked", "taxi_out", "parked_at_stop"])
def test_recovery_from_incomplete_saved_ground_state(movement):
    state = DetectionState(movement=movement)
    events = []
    for second in range(21):
        result = advance_detection(
            state, observation(second, speed=150, altitude=5000), DetectionPolicy()
        )
        state = result.state
        events.extend(result.emitted_events)
    assert state.movement == "airborne"
    assert not events


def test_observed_takeoff_at_high_elevation_keeps_its_event():
    state = DetectionState(
        movement="taxi_out",
        parked_altitude=6000,
        last_observed_at=START - timedelta(seconds=1),
    )
    events = []
    for second in range(21):
        result = advance_detection(
            state, observation(second, speed=150, altitude=6500), DetectionPolicy()
        )
        state = result.state
        events.extend(result.emitted_events)
    assert state.movement == "airborne"
    assert [event.kind for event in events] == ["takeoff"]


def test_old_ground_baseline_does_not_invent_takeoff_after_a_restart_gap():
    state = DetectionState(
        movement="taxi_out",
        parked_altitude=100,
        last_observed_at=START - timedelta(minutes=30),
    )
    events = []
    for second in range(21):
        result = advance_detection(
            state, observation(second, speed=150, altitude=5000), DetectionPolicy()
        )
        state = result.state
        events.extend(result.emitted_events)
    assert state.movement == "airborne"
    assert not events


def test_recovered_segment_after_intermediate_stop_remains_correctable(tmp_path):
    from app.services.flight_events.store import FlightEventStore

    store = FlightEventStore(tmp_path / "events.db")
    for minute, kind in enumerate(["off_blocks", "takeoff", "landed", "on_blocks"]):
        store.record_manual_event(
            "m",
            "l",
            kind,
            START - timedelta(minutes=10 - minute),
            "observed",
            "operator",
        )
    for second in range(21):
        store.apply_observation(observation(second, speed=150, altitude=5000))
    for second in range(21, 52):
        store.apply_observation(observation(second, speed=25, altitude=100))
    landed = store.events("m", "l")[-1]
    assert landed.kind == "landed"
    corrected = store.correct_event(
        landed.event_id,
        START + timedelta(seconds=22),
        "observed",
        "operator",
        landed.revision,
        "m",
        "l",
    )
    assert corrected.revision == 2
    assert len(store.events("m", "l")) == 5


@pytest.mark.parametrize("sync_after_off_blocks", [True, False])
def test_supplying_departure_history_during_recovered_cruise_keeps_live_timing(
    tmp_path, sync_after_off_blocks
):
    manager = get_flight_state_manager()
    manager.reset()
    runtime = FlightEventRuntime(tmp_path)
    try:
        for second in range(21):
            runtime.accept(observation(second, speed=150, altitude=5000))
        runtime.sync_legacy_phase(manager, "m", "l")
        runtime.events.record_manual_event(
            "m",
            "l",
            "off_blocks",
            START - timedelta(minutes=10),
            "observed",
            "operator",
        )
        if sync_after_off_blocks:
            runtime.sync_legacy_phase(manager, "m", "l")
            assert manager.get_status().phase == FlightPhase.IN_FLIGHT
        takeoff = START - timedelta(minutes=5)
        runtime.events.record_manual_event(
            "m", "l", "takeoff", takeoff, "observed", "operator"
        )
        runtime.sync_legacy_phase(manager, "m", "l")
        assert runtime.events.state("m", "l").movement == "airborne"
        assert manager.get_status().phase == FlightPhase.IN_FLIGHT
        assert manager.get_status().departure_time == takeoff
    finally:
        runtime.close()
        manager.reset()


def test_recovered_flight_can_land_and_correct_partial_history(tmp_path):
    from app.services.flight_events.store import FlightEventStore

    store = FlightEventStore(tmp_path / "events.db")
    for second in range(21):
        store.apply_observation(observation(second, speed=150, altitude=5000))
    for second in range(21, 52):
        store.apply_observation(observation(second, speed=25, altitude=100))
    landed = store.events("m", "l")[0]
    assert landed.kind == "landed"
    corrected = store.correct_event(
        landed.event_id,
        START + timedelta(seconds=22),
        "observed landing",
        "operator",
        landed.revision,
        "m",
        "l",
    )
    assert corrected.revision == 2
    assert store.state("m", "l").movement == "taxi_in"
    # Missing departure history may be supplied one event at a time later.
    store.record_manual_event(
        "m", "l", "off_blocks", START - timedelta(minutes=10), "observed", "operator"
    )
    store.record_manual_event(
        "m", "l", "takeoff", START - timedelta(minutes=5), "observed", "operator"
    )
    assert [event.kind for event in store.events("m", "l")] == [
        "off_blocks",
        "takeoff",
        "landed",
    ]


def test_cold_recovery_and_restart_restore_live_eta_without_takeoff_time(tmp_path):
    manager = get_flight_state_manager()
    manager.reset()
    runtime = FlightEventRuntime(tmp_path)
    try:
        for second in range(21):
            runtime.accept(observation(second, speed=150, altitude=5000))
        runtime.sync_legacy_phase(manager, "m", "l")
        status = manager.get_status()
        assert status.phase == FlightPhase.IN_FLIGHT
        assert status.eta_mode == ETAMode.ESTIMATED
        assert status.departure_time is None
        assert status.time_since_departure_seconds is None
        assert runtime.events.events("m", "l") == []
        assert runtime.events.pin_start("m", "l") is None
        runtime.close()
        runtime = FlightEventRuntime(tmp_path)
        manager.reset()
        runtime.sync_legacy_phase(manager, "m", "l")
        assert manager.get_status().phase == FlightPhase.IN_FLIGHT
        assert manager.get_status().departure_time is None
        assert runtime.event_status("m", "l")["takeoff_at"] is None
        # Another leg does not inherit the recovered movement.
        runtime.sync_legacy_phase(manager, "m", "next")
        assert manager.get_status().phase == FlightPhase.PRE_DEPARTURE
    finally:
        runtime.close()
        manager.reset()


def test_restart_restores_an_existing_takeoff_time(tmp_path):
    manager = get_flight_state_manager()
    manager.reset()
    runtime = FlightEventRuntime(tmp_path)
    try:
        runtime.events.record_manual_event(
            "m", "l", "off_blocks", START, "observed", "operator"
        )
        takeoff = START + timedelta(minutes=5)
        runtime.events.record_manual_event(
            "m", "l", "takeoff", takeoff, "observed", "operator"
        )
        runtime.sync_legacy_phase(manager, "m", "l")
        assert manager.get_status().phase == FlightPhase.IN_FLIGHT
        assert manager.get_status().departure_time == takeoff
    finally:
        runtime.close()
        manager.reset()
