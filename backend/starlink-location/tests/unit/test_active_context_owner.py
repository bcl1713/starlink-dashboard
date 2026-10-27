"""Reconciliation belongs to the lifespan, and drains its executor work."""

import asyncio
import threading

import pytest

from app.mission import active_context_owner
from app.mission.active_context_cache import get_active_mission_snapshot
from app.mission.storage import save_mission_v2
from tests.unit.test_active_mission_context import route_manager, v2_mission

__all__ = ["route_manager", "v2_mission"]


async def test_owner_scans_off_loop_and_drains_repeated_cancellation(
    monkeypatch, route_manager, v2_mission
):
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    owner = active_context_owner.ActiveContextOwner(route_manager, lambda: "live")
    await owner.start()
    accepted = get_active_mission_snapshot(route_manager, reconcile=False)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    loop_thread = threading.get_ident()

    def blocked(manager):
        assert threading.get_ident() != loop_thread
        entered.set()
        try:
            assert release.wait(5)
            return get_active_mission_snapshot(manager)
        finally:
            finished.set()

    monkeypatch.setattr(active_context_owner, "get_active_mission_snapshot", blocked)
    closing = None
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        # A reconciler waiting on work never makes the accepted context vanish.
        assert get_active_mission_snapshot(route_manager, reconcile=False) is accepted
        closing = asyncio.create_task(owner.close())
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        assert not closing.done()
    finally:
        release.set()
        if closing is not None:
            with pytest.raises(asyncio.CancelledError):
                await closing
        else:
            await owner.close()
        assert finished.is_set()
        assert owner.task.done()
        assert not hasattr(route_manager, "_active_mission_context_owner")


async def test_expired_overview_resolution_does_not_block_event_loop(
    monkeypatch, route_manager
):
    from types import SimpleNamespace
    import httpx
    import main
    from app.api import overview_upcoming_pois
    from app.mission.dependencies import get_poi_manager, get_route_manager

    entered, release = threading.Event(), threading.Event()

    def blocked_resolver(_):
        entered.set()
        assert release.wait(5)
        return SimpleNamespace(state="inconsistent_active_mission", context=None)

    monkeypatch.setattr(
        overview_upcoming_pois, "resolve_active_mission_leg_context", blocked_resolver
    )
    monkeypatch.setitem(
        main.app.dependency_overrides, get_route_manager, lambda: route_manager
    )
    monkeypatch.setitem(main.app.dependency_overrides, get_poi_manager, lambda: None)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        pending = asyncio.create_task(client.get("/api/overview/upcoming-pois"))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            response = await asyncio.wait_for(client.get("/"), timeout=0.5)
            assert response.status_code == 200
            assert not pending.done()
        finally:
            release.set()
            response = await pending
            assert response.status_code == 200
