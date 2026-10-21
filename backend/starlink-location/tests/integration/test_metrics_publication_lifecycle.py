"""Lifecycle changes invalidate immediately and refresh without observations."""

import asyncio
from math import isnan

import pytest

import main
from app.core.metrics import prometheus_metrics as metrics
from app.models.flight_status import FlightPhase
from app.models.poi import POICreate, POIUpdate
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_startup_has_complete_frame_without_counting_an_observation(
    background_runtime,
):
    assert metrics.FRAME_STORE.read().status == "ready"
    assert metrics.FRAME_STORE.read().frame.identity.coordinator_id is not None
    assert hasattr(main.app.state, "metrics_refresh_owner")


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize(
    "change",
    [
        "route",
        "remove",
        "reload",
        "phase",
        "timing",
        "reset",
        "config",
        "poi",
        "poi-update",
        "poi-delete",
        "poi-restore",
        "projection",
    ],
)
async def test_completed_change_masks_old_frame_before_refresh(
    background_runtime, change
):
    runtime = background_runtime
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    owner = getattr(main.app.state, "metrics_refresh_owner", None)
    assert owner is not None, "Lifecycle refresh owner is missing"
    await owner.refresh_without_collection()
    manager = main.app.state.poi_manager
    poi = manager.create_poi(POICreate(name="Test", latitude=1, longitude=1))
    checkpoint = manager.checkpoint()
    await owner.refresh_without_collection()
    before_count = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    before = metrics.FRAME_STORE.read().frame
    if change == "route":
        runtime.route_manager.activate_route("first")
    elif change == "remove":
        runtime.route_manager.activate_route("first")
        runtime.route_manager._remove_route("first")
    elif change == "reload":
        runtime.route_manager.reload_all_routes()
    elif change == "phase":
        runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
    elif change == "timing":
        runtime.flight_state.trigger_departure(runtime.origin)
    elif change == "reset":
        main._coordinator.reset()
    elif change == "config":
        main._coordinator.update_config(main._coordinator.get_config().model_copy())
    elif change == "poi":
        manager.create_poi(POICreate(name="Second", latitude=2, longitude=2))
    elif change == "poi-update":
        manager.update_poi(poi.id, POIUpdate(name="Updated"))
    elif change == "poi-delete":
        manager.delete_poi(poi.id)
    elif change == "poi-restore":
        manager.restore_checkpoint(checkpoint)
    else:
        manager.clear_poi_projections()
    assert metrics.FRAME_STORE.read().status == "pending"
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert (
        metrics.FRAME_STORE.read().frame.last_observation_publication_time
        == before.last_observation_publication_time
    )
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before_count


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_bulk_notifications_coalesce_and_shutdown_detaches(
    background_runtime, monkeypatch
):
    owner = getattr(main.app.state, "metrics_refresh_owner", None)
    assert owner is not None
    from app.core.metrics import frame_builder
    from app.mission.storage import get_active_leg_lock

    prepare = frame_builder.prepare_frame
    preparations = []

    def counted(*args, **kwargs):
        preparations.append(1)
        return prepare(*args, **kwargs)

    monkeypatch.setattr(frame_builder, "prepare_frame", counted)
    with get_active_leg_lock():
        for index in range(10):
            main.app.state.poi_manager.create_poi(
                POICreate(name=f"Bulk {index}", latitude=1, longitude=1)
            )
    await owner.refresh_without_collection()
    assert len(preparations) == 1
    await owner.close()
    head = metrics.FRAME_STORE.read()
    background_runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
    await asyncio.sleep(0)
    assert metrics.FRAME_STORE.read() is head
    assert owner.task is None


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_observation_that_changes_phase_publishes_once(
    background_runtime, monkeypatch
):
    from app.core.metrics import metric_updater

    observe = metric_updater._observe_flight_status

    def transition(*args, **kwargs):
        background_runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
        return observe(*args, **kwargs)

    monkeypatch.setattr(metric_updater, "_observe_flight_status", transition)
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    assert metrics.FRAME_STORE.read().status == "ready"
    assert metrics.REGISTRY.get_sample_value("starlink_flight_phase") == 1
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before + 1


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_refresh_detaches_pois_once_and_revalidates_without_another_copy(
    background_runtime, monkeypatch
):
    owner = main.app.state.metrics_refresh_owner
    manager = main.app.state.poi_manager
    manager.create_poi(POICreate(name="Once", latitude=1, longitude=1))
    listing = manager.list_pois
    copies = []

    def listed(*args, **kwargs):
        copies.append(1)
        return listing(*args, **kwargs)

    monkeypatch.setattr(manager, "list_pois", listed)
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert len(copies) == 1
