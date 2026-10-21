"""Initial activation and failures inside the actual replay commit path."""

from math import isnan

import pytest

from app.core.metrics import prometheus_metrics as metrics
from tests.integration.test_simulation_run_api import start
from tests.integration.test_simulation_run_time_apis import api, timed_api
from tests.unit.test_simulation_run_timing import timing

__all__ = ["api", "timed_api", "timing"]


@pytest.mark.parametrize("failure", [None, "before", "during"])
def test_activation_publishes_only_after_successful_commit(
    timed_api, monkeypatch, failure
):
    client, service, _clocks = timed_api
    old = metrics.FRAME_STORE.read()
    commit = service.runtime.commit_tick
    prepare = service.publish
    frames = []

    def callback(telemetry, tick):
        frames.append(prepare(telemetry, tick))
        assert metrics.FRAME_STORE.read() is old
        if failure == "before":
            raise RuntimeError("before commit")
        return frames[-1]

    def guarded_commit(tick):
        assert metrics.FRAME_STORE.read() is old
        if failure == "during":
            raise RuntimeError("during commit")
        return commit(tick)

    service.publish = callback
    monkeypatch.setattr(service.runtime, "commit_tick", guarded_commit)
    response = start(client)
    if failure:
        assert response.status_code == 500
        assert service.status().state == "idle"
        assert metrics.FRAME_STORE.read().frame is old.frame
        assert isnan(
            metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees")
        )
    else:
        assert response.status_code == 200
        assert metrics.FRAME_STORE.read().frame is frames[0]
        assert frames[0].identity.replay_revision == str(service.status().revision)


def test_failure_inside_real_runtime_commit_never_publishes(timing, monkeypatch):
    service, clocks, coordinator, prepare = timing
    old = metrics.FRAME_STORE.read()
    previous_clock = service.status().run.simulation_time
    clock = service.runtime._utc_now
    staged = []

    def callback(telemetry, tick):
        staged.append(prepare(telemetry, tick))
        calls = 0

        def failing_clock():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("runtime commit clock failed")
            return clock()

        monkeypatch.setattr(service.runtime, "_utc_now", failing_clock)
        return staged[0]

    clocks.advance(1)
    with pytest.raises(OSError, match="runtime commit clock failed"):
        service.collect(coordinator, callback)
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().frame is not staged[0]
    assert service.status().run.simulation_time == previous_clock
    assert service.status().state == "failed"


@pytest.mark.parametrize("initial", [True, False])
@pytest.mark.parametrize("complete", [False, True])
def test_postcommit_metric_failure_keeps_successful_runtime_and_domain_state(
    timed_api, monkeypatch, initial, complete
):
    import app.core.metrics.source_admission as admission
    from app.mission.storage import load_mission_v2
    from app.simulation import run_service

    client, service, clocks = timed_api
    if not initial:
        assert start(client).status_code == 200
        clocks.advance(120 if complete else 12)
    old = metrics.FRAME_STORE.read()
    original = admission.replay_input_identity
    calls = 0

    def source_check(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("postcommit identity read failed")
        return original(*args)

    monkeypatch.setattr(admission, "replay_input_identity", source_check)
    monkeypatch.setattr(run_service, "replay_input_identity", source_check)
    if initial:
        response = start(client)
        assert response.status_code == 200
    else:
        telemetry = service.collect(service.coordinator, service.publish)
        assert service.coordinator.get_current_telemetry() is telemetry
    assert service.status().state == (
        "completed" if complete and not initial else "running"
    )
    assert load_mission_v2("mission-1").legs[0].is_active
    assert service.route_manager.get_active_route_id() == "replay"
    position = service.runtime.frame().position
    assert (
        service.coordinator.get_current_telemetry().position.longitude
        == position.longitude
    )
    assert metrics.FRAME_STORE.read().status == "failed"
    assert metrics.FRAME_STORE.read().frame is old.frame
