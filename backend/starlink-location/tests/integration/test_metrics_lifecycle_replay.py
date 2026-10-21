"""Committed replay frames and terminal lifecycle refresh stay separate."""

import pytest

from app.core.metrics import prometheus_metrics as metrics
from app.core.metrics.frame_builder import coordinator_identity
from app.core.metrics.lifecycle import MetricsRefreshOwner
from app.core.metrics.metric_updater import prepare_metrics_from_telemetry
from app.core.metrics.refresh_inputs import refresh_current_metrics
from app.models.poi import POICreate
from app.services.flight_state import get_flight_state_manager
from app.simulation.run_timing import mission_time_context
from tests.unit.test_simulation_run_timing import timing

__all__ = ["timing"]


@pytest.fixture
async def replay_owner(timing):
    service, clocks, coordinator, _publish = timing
    config = coordinator.get_config()

    def sources():
        return coordinator, config, service.route_manager, service.poi_manager, service

    owner = MetricsRefreshOwner(
        lambda: refresh_current_metrics(sources, now=clocks.utc),
        background_enabled=True,
    )
    owner.attach(
        service.route_manager,
        service.poi_manager,
        get_flight_state_manager(),
        coordinator,
        service.runtime,
    )

    def publish(telemetry, tick):
        return prepare_metrics_from_telemetry(
            telemetry,
            config,
            tick.plan.artifacts.route.model_copy(deep=True),
            service.poi_manager,
            mission_context=mission_time_context(tick.status),
            simulation_plan=tick.plan,
            simulation_frame=tick.frame,
            coordinator_id=coordinator_identity(coordinator),
        )

    service.route_manager.activate_route("replay")
    service.collect(coordinator, publish)
    try:
        yield owner, service, clocks, coordinator, publish
    finally:
        await owner.close()


async def test_derived_replay_refresh_preserves_both_clocks_and_counts(
    replay_owner, monkeypatch
):
    owner, service, _clocks, coordinator, _publish = replay_owner
    before = metrics.FRAME_STORE.read().frame
    run = service.status().run
    observation = coordinator.get_current_telemetry().model_copy(deep=True)
    count = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    revision = service.status().revision

    def forbidden(*args, **kwargs):
        raise AssertionError("Lifecycle refresh advanced replay")

    monkeypatch.setattr(service.runtime, "prepare_tick", forbidden)
    monkeypatch.setattr(coordinator, "update", forbidden)
    service.poi_manager.create_poi(POICreate(name="Lifecycle", latitude=0, longitude=1))
    await owner.refresh_without_collection()
    head = metrics.FRAME_STORE.read()
    assert head.status == "ready"
    assert head.frame.identity.mode == "replay"
    assert head.frame.identity.replay_mission_time == run.simulation_time.timestamp()
    assert head.frame.identity.replay_revision == str(revision)
    assert (
        head.frame.identity.observation_timestamp
        == before.identity.observation_timestamp
    )
    assert (
        head.frame.last_observation_publication_time
        == before.last_observation_publication_time
    )
    assert service.status().revision == revision
    assert service.status().run == run
    assert coordinator.get_current_telemetry() == observation
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == count


@pytest.mark.parametrize("terminal", ["cancel", "fail", "clear"])
async def test_replay_terminal_change_masks_old_frame_synchronously(
    replay_owner, terminal
):
    owner, service, _clocks, _coordinator, _publish = replay_owner
    before = metrics.FRAME_STORE.read().frame
    count = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    if terminal == "cancel":
        service.cancel_owned("mission-1", None, "test cancellation")
    elif terminal == "fail":
        service.runtime.fail("test", "test failure")
    else:
        service.runtime.clear_selection()
    assert metrics.FRAME_STORE.read().status == "pending"
    assert metrics.FRAME_STORE.read().frame is before
    await owner.refresh_without_collection()
    head = metrics.FRAME_STORE.read()
    assert head.status == "ready"
    assert head.frame.identity.mode == "simulation"
    assert head.frame.identity.replay_runtime_id is None
    assert head.frame.identity.observation_timestamp is None
    assert (
        head.frame.last_observation_publication_time
        == before.last_observation_publication_time
    )
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == count


async def test_failed_collection_never_refreshes_an_uncommitted_observation(
    replay_owner,
):
    owner, service, clocks, coordinator, _publish = replay_owner
    before = metrics.FRAME_STORE.read().frame
    clocks.advance(1)

    def failed(*args):
        raise ValueError("pre-commit replay failure")

    with pytest.raises(ValueError, match="pre-commit"):
        service.collect(coordinator, failed)
    assert service.status().state == "failed"
    assert metrics.FRAME_STORE.read().frame is before
    assert metrics.FRAME_STORE.read().status != "ready"
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert metrics.FRAME_STORE.read().frame.identity.observation_id is None
