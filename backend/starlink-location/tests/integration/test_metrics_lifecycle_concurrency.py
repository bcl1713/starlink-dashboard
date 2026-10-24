"""Refresh admission, deadlines, nested compensation, and read-only scrapes."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from math import isnan
from threading import Event

import httpx
import pytest

import main
from app.core.metrics import frame_builder
from app.core.metrics import prometheus_metrics as metrics
from app.mission.storage import get_active_leg_lock
from app.models.poi import POICreate
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_dirty_wakes_preserve_collection_deadline(
    background_runtime, monkeypatch
):
    owner = main.app.state.metrics_refresh_owner
    owner._background_enabled = True
    monkeypatch.setattr(main, "_background_updates_enabled", True)
    monkeypatch.setattr(main._simulation_config, "update_interval_seconds", 0.4)
    loop = asyncio.get_running_loop()
    collected = asyncio.Event()
    times = []
    tick = main._background_update_tick

    def timed(*args):
        times.append(loop.time())
        result = tick(*args)
        loop.call_soon_threadsafe(collected.set)
        return result

    monkeypatch.setattr(main, "_background_update_tick", timed)
    task = asyncio.create_task(main._background_update_loop(main.app.state.poi_manager))
    try:
        await asyncio.wait_for(collected.wait(), 2)
        collected.clear()
        before = metrics.REGISTRY.get_sample_value("simulation_updates_total")
        for _ in range(3):
            await asyncio.sleep(0.07)
            owner.mark_dirty("deadline test")
        assert len(times) == 1
        assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before
        await asyncio.wait_for(collected.wait(), 1)
        assert 0.35 <= times[1] - times[0] < 0.6
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_nested_rollback_never_publishes_intermediate_state(background_runtime):
    manager = main.app.state.poi_manager
    owner = main.app.state.metrics_refresh_owner
    before = metrics.FRAME_STORE.read().frame
    entered, release = Event(), Event()
    checkpoint = manager.checkpoint()

    def compensate():
        with get_active_leg_lock():
            background_runtime.route_manager.activate_route("first")
            for i in range(5):
                manager.create_poi(
                    POICreate(name=f"Temporary {i}", latitude=1, longitude=1)
                )
            entered.set()
            assert release.wait(4)
            manager.restore_checkpoint(checkpoint)
            background_runtime.route_manager.deactivate_route()

    with ThreadPoolExecutor(max_workers=1) as pool:
        writer = pool.submit(compensate)
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app), base_url="http://test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(20))), 2
                )
            assert all(r.status_code == 200 for r in responses)
            assert metrics.FRAME_STORE.read().status == "pending"
            assert metrics.FRAME_STORE.read().frame is before
            assert isnan(
                metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees")
            )
        finally:
            release.set()
            writer.result(timeout=3)
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert metrics.FRAME_STORE.read().frame.identity.poi_id == before.identity.poi_id
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_has_timing_data", {"route_name": "first"}
        )
        is None
    )


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize(
    "change", ["config", "route", "mission", "poi", "phase", "source"]
)
@pytest.mark.parametrize("newer", [False, True])
async def test_refresh_rejects_superseded_inputs_and_preserves_newer_head(
    background_runtime, monkeypatch, change, newer
):
    from app.models.flight_status import FlightPhase

    owner = main.app.state.metrics_refresh_owner
    owner._background_enabled = True  # The test owns each refresh barrier.
    prepare = frame_builder.prepare_frame
    changed = False
    newer_head = None

    def changed_inputs(*args, **kwargs):
        nonlocal changed, newer_head
        frame = prepare(*args, **kwargs)
        if not changed:
            changed = True
            if change == "source":
                main._coordinator.update()
            elif change == "config":
                main._coordinator.update_config(
                    main._coordinator.get_config().model_copy()
                )
            elif change == "route":
                background_runtime.route_manager.activate_route("first")
            elif change == "mission":
                main.app.state.simulation_run_service.runtime.clear_selection()
            elif change == "poi":
                main.app.state.poi_manager.create_poi(
                    POICreate(name="New", latitude=1, longitude=1)
                )
            else:
                background_runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
            if newer:
                main._refresh_metrics_without_collection()
                newer_head = metrics.FRAME_STORE.read()
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", changed_inputs)
    owner.mark_dirty("start barrier")
    await owner.refresh_without_collection()
    if newer:
        assert newer_head.status == "ready"
        assert metrics.FRAME_STORE.read() is newer_head
    else:
        if change == "source":
            assert metrics.FRAME_STORE.read().status == "failed"
            owner.mark_dirty("next source lifecycle")
        else:
            assert metrics.FRAME_STORE.read().status == "pending"
        await owner.refresh_without_collection()
        assert metrics.FRAME_STORE.read().status == "ready"


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_legacy_mutable_poi_alias_is_revalidated(background_runtime, monkeypatch):
    owner = main.app.state.metrics_refresh_owner
    owner._background_enabled = True
    manager = main.app.state.poi_manager
    manager.create_poi(POICreate(name="Original", latitude=1, longitude=1))
    prepare = frame_builder.prepare_frame

    def mutate_alias(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        manager.find_poi_by_name("Original").name = "Changed"
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", mutate_alias)
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "failed"


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("change", ["config", "route", "mission"])
async def test_production_refresh_and_source_writer_can_overlap_with_scrapes(
    background_runtime, monkeypatch, change
):
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    owner = main.app.state.metrics_refresh_owner
    prepare = frame_builder.prepare_frame
    entered, release = Event(), Event()
    paused = False
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")

    def pause_once(*args, **kwargs):
        nonlocal paused
        frame = prepare(*args, **kwargs)
        if not paused:
            paused = True
            entered.set()
            assert release.wait(4)
        return frame

    def change_source():
        with get_active_leg_lock():
            if change == "config":
                main._coordinator.update_config(
                    main._coordinator.get_config().model_copy()
                )
            elif change == "route":
                background_runtime.route_manager.activate_route("first")
            else:
                main.app.state.simulation_run_service.runtime.clear_selection()

    monkeypatch.setattr(frame_builder, "prepare_frame", pause_once)
    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(
            main._background_update_tick, main.app.state.poi_manager, 1, 1, 0
        )
        writer = None
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            owner.mark_dirty("refresh while source producer is busy")
            writer = pool.submit(change_source)
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app), base_url="http://test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(20))), 2
                )
            assert all(response.status_code == 200 for response in responses)
            assert metrics.FRAME_STORE.read().status == "pending"
        finally:
            release.set()
            producer.result(timeout=3)
            if writer is not None:
                writer.result(timeout=3)
    await owner.refresh_without_collection()
    assert metrics.FRAME_STORE.read().status == "ready"
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before + 1
