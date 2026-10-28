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
    from app.core.metrics.metric_updater import update_mission_active_metric

    update_mission_active_metric("previous-mission", "previous-route")
    previous_mission = metrics.REGISTRY.get_sample_value(
        "mission_active_info",
        {"mission_id": "previous-mission", "route_id": "previous-route"},
    )

    def callback(telemetry, tick):
        frames.append(prepare(telemetry, tick))
        assert metrics.FRAME_STORE.read() is old
        assert (
            metrics.REGISTRY.get_sample_value(
                "mission_phase_state", {"mission_id": tick.plan.mission_id}
            )
            is None
        )
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
        assert (
            metrics.REGISTRY.get_sample_value(
                "mission_active_info",
                {"mission_id": "previous-mission", "route_id": "previous-route"},
            )
            == previous_mission
        )
        assert metrics.FRAME_STORE.read().frame is old.frame
        assert isnan(
            metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees")
        )
    else:
        assert response.status_code == 200
        assert metrics.FRAME_STORE.read().frame is frames[0]
        assert frames[0].identity.replay_revision == str(service.status().revision)
        assert (
            metrics.REGISTRY.get_sample_value(
                "mission_active_info",
                {
                    "mission_id": service.status().run.mission_id,
                    "route_id": service.status().run.route_id,
                },
            )
            == 1
        )
        assert (
            metrics.REGISTRY.get_sample_value(
                "mission_active_info",
                {"mission_id": "previous-mission", "route_id": "previous-route"},
            )
            is None
        )


def test_replay_cancellation_removes_all_mission_children(timing):
    service, _clocks, coordinator, publish = timing
    service.collect(coordinator, publish)
    assert (
        metrics.REGISTRY.get_sample_value(
            "mission_phase_state", {"mission_id": "mission-1"}
        )
        == 1
    )
    service.runtime.cancel("Lifecycle test")
    assert all(
        not family.samples
        for family in metrics.REGISTRY.collect()
        if family.name.startswith("mission_")
    )


@pytest.mark.parametrize("terminal", ["cancel", "fail"])
def test_reconciliation_cannot_resurrect_terminal_replay(timed_api, terminal):
    from app.mission.active_context_owner import ActiveContextOwner
    from app.mission.storage import load_mission_v2

    client, service, _clocks = timed_api
    assert start(client).status_code == 200
    assert load_mission_v2("mission-1").legs[0].is_active
    if terminal == "cancel":
        service.runtime.cancel("Lifecycle test")
    else:
        service.runtime.fail("test", "Lifecycle test")
    owner = ActiveContextOwner(
        service.route_manager, lambda: "simulation", service.status
    )
    owner._reconcile()
    assert all(
        not family.samples
        for family in metrics.REGISTRY.collect()
        if family.name.startswith("mission_")
    )


@pytest.mark.parametrize("initial_state", ["running", "failed"])
async def test_mode_round_trip_clears_live_owner_for_terminal_replay(
    timed_api, monkeypatch, initial_state
):
    import json

    from app.mission import active_context_cache, storage
    from app.mission.active_context_owner import ActiveContextOwner

    client, service, _clocks = timed_api
    assert start(client).status_code == 200
    if initial_state == "failed":
        service.runtime.fail("test", "Failed before switching modes")
    reconciliation_clock = [0.0]
    monkeypatch.setattr(
        active_context_cache, "monotonic", lambda: reconciliation_clock[0]
    )
    owner = ActiveContextOwner(
        service.route_manager, lambda: service.status().service_mode, service.status
    )
    labels = {"mission_id": "mission-1", "route_id": "replay"}
    service.runtime.set_service_mode("live")
    assert service.status().state == (
        "cancelled" if initial_state == "running" else "failed"
    )
    assert metrics.REGISTRY.get_sample_value("mission_active_info", labels) is None
    await owner.refresh()
    assert metrics.REGISTRY.get_sample_value("mission_active_info", labels) == 1

    service.runtime.set_service_mode("simulation")
    await owner.refresh()
    assert all(
        not family.samples
        for family in metrics.REGISTRY.collect()
        if family.name.startswith("mission_")
    )

    # Simulate a durable edit by another process, without local notifications.
    path = storage.get_mission_leg_file_path("mission-1", "leg-1")
    payload = json.loads(path.read_text())
    payload["is_active"] = False
    path.write_text(json.dumps(payload))
    reconciliation_clock[0] += 2
    snapshot = await owner.refresh()
    assert snapshot.state == "no_active_mission"
    assert all(
        not family.samples
        for family in metrics.REGISTRY.collect()
        if family.name.startswith("mission_")
    )


@pytest.mark.parametrize("complete", [False, True])
async def test_reconciliation_preserves_current_running_or_completed_replay(
    timed_api, complete
):
    from app.mission.active_context_owner import ActiveContextOwner

    client, service, clocks = timed_api
    assert start(client).status_code == 200
    if complete:
        clocks.advance(120)
        service.collect(service.coordinator, service.publish)
    assert service.status().state == ("completed" if complete else "running")
    before = [
        sample
        for family in metrics.REGISTRY.collect()
        if family.name.startswith("mission_")
        for sample in family.samples
    ]
    owner = ActiveContextOwner(
        service.route_manager, lambda: service.status().service_mode, service.status
    )
    await owner.refresh()
    assert (
        metrics.REGISTRY.get_sample_value(
            "mission_active_info", {"mission_id": "mission-1", "route_id": "replay"}
        )
        == 1
    )
    assert [
        sample
        for family in metrics.REGISTRY.collect()
        if family.name.startswith("mission_")
        for sample in family.samples
    ] == before


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
    from app.core.metrics.metric_updater import update_mission_active_metric

    update_mission_active_metric("previous-mission", "previous-route")
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
    assert (
        metrics.REGISTRY.get_sample_value(
            "mission_active_info",
            {"mission_id": "previous-mission", "route_id": "previous-route"},
        )
        is None
    )
    assert (
        metrics.REGISTRY.get_sample_value(
            "mission_active_info", {"mission_id": "mission-1", "route_id": "replay"}
        )
        == 1
    )
    assert (
        metrics.REGISTRY.get_sample_value(
            "mission_phase_state", {"mission_id": "mission-1"}
        )
        is None
    )


@pytest.mark.parametrize("activation", [True, False])
def test_precommit_replay_failure_preserves_independent_dish_clears(
    timed_api, monkeypatch, activation
):
    client, service, clocks = timed_api
    if not activation:
        assert start(client).status_code == 200
    gauges = [
        metrics.starlink_dish_uptime_seconds,
        metrics.starlink_dish_thermal_throttle,
        metrics.starlink_dish_outage_active,
    ]
    for gauge in gauges:
        gauge.set(7)

    def failed_commit(tick):
        raise RuntimeError("precommit failure")

    monkeypatch.setattr(service.runtime, "commit_tick", failed_commit)
    if activation:
        assert start(client).status_code == 500
    else:
        clocks.advance(1)
        with pytest.raises(RuntimeError):
            service.collect(service.coordinator, service.publish)
    for gauge in gauges:
        assert isnan(next(iter(gauge.collect())).samples[0].value)
