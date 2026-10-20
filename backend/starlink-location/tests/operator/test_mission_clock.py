"""Mission scheduling and observation age use separate clocks."""

from datetime import timedelta

from app.operator.clock import MissionClock, observation_now
from tests.operator.service_helpers import create


def test_mission_clock_keeps_observation_and_expiry_on_real_time(clock):
    mission_time = clock.now() + timedelta(days=5)
    mission_clock = MissionClock(lambda: mission_time, observation_clock=clock)
    assert mission_clock.now() == mission_time
    assert observation_now(mission_clock) == clock.now()
    from app.operator.schema import timestamp

    assert timestamp(mission_clock) == timestamp(clock)
    clock.advance(11)
    assert mission_clock.now() == mission_time
    assert mission_clock.monotonic() == 11
    assert observation_now(mission_clock) == clock.now()


def test_replay_reset_does_not_regress_durable_recording_clock(
    service, record_data, clock
):
    mission_time = clock.now() + timedelta(days=5)
    mission_clock = MissionClock(lambda: mission_time, observation_clock=clock)
    service.clock = service.store.clock = mission_clock
    saved = create(service, record_data)
    assert saved.recorded_at == clock.now()
    mission_time -= timedelta(days=10)
    assert not service.store.health().clock_regression


def test_unpaced_clock_falls_back_to_wall_time(clock):
    assert MissionClock(lambda: None, observation_clock=clock).now() == clock.now()


def test_simulated_schedule_time_does_not_age_physical_telemetry(production, clock):
    import pytest

    from app.operator.errors import OperatorError
    from app.operator.production_event_inputs import capture_current

    adapter, *_ = production
    mission_time = clock.now() + timedelta(days=5)
    adapter.clock = MissionClock(lambda: mission_time, observation_clock=clock)
    captured = capture_current(adapter, "demo-mission", as_of=adapter.clock.now())
    assert captured.position.observed_at == clock.now()
    clock.advance(60)
    with pytest.raises(OperatorError, match="event_source_unavailable"):
        capture_current(adapter, "demo-mission", as_of=adapter.clock.now())
