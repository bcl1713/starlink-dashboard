"""Route identity stays bound to legacy simulation collection and progress."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

import main
from app.core.metrics import prometheus_metrics as metrics
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.fixture(autouse=True)
async def manual_publication_owner(background_runtime):
    # This suite explicitly controls all publication barriers. Lifecycle-owned
    # concurrency is exercised in test_metrics_publication_lifecycle.py.
    await main.app.state.metrics_refresh_owner.close()


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("change", ["activate", "remove", "timing"])
async def test_route_changed_after_collection_cannot_relabel_old_progress(
    background_runtime, monkeypatch, change
):
    from app.mission.storage import get_active_leg_lock
    from app.models.route import RouteTimingProfile

    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    coordinator = main._coordinator
    collect = coordinator.update
    collected, release = Event(), Event()
    old = metrics.FRAME_STORE.read()
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")

    def paused_after_collection():
        result = collect()
        collected.set()
        assert release.wait(5)
        return result

    monkeypatch.setattr(coordinator, "update", paused_after_collection)
    with ThreadPoolExecutor(max_workers=1) as pool:
        producer = pool.submit(
            main._background_update_tick, main.app.state.poi_manager, 1, 0, 0
        )
        try:
            assert await asyncio.to_thread(collected.wait, 3)
            with get_active_leg_lock():
                if change == "activate":
                    runtime.route_manager.activate_route("second")
                elif change == "remove":
                    runtime.route_manager.deactivate_route()
                else:
                    runtime.route.timing_profile = RouteTimingProfile(
                        has_timing_data=True
                    )
        finally:
            release.set()
            producer.result(timeout=5)
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status == "failed"
