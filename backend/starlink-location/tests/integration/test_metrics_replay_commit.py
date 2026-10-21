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
