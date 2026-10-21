"""Lifespan failure and repeated shutdown cancellation drain real resources."""

import asyncio
from threading import Event

import pytest

import main
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_cancelled_shutdown_finishes_detaching_and_closing_managers(
    background_runtime, monkeypatch
):
    owner = main.app.state.metrics_refresh_owner
    entered, release = Event(), Event()
    closing_entered = asyncio.Event()

    def blocked():
        entered.set()
        assert release.wait(3)

    owner._refresh = blocked
    close = owner.close

    async def closing():
        closing_entered.set()
        await close()

    monkeypatch.setattr(owner, "close", closing)
    owner.mark_dirty("shutdown drain")
    assert await asyncio.to_thread(entered.wait, 2)
    shutdown = asyncio.create_task(main.shutdown_event())
    try:
        await asyncio.wait_for(closing_entered.wait(), 2)
        shutdown.cancel()
        await asyncio.sleep(0)
        shutdown.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await shutdown
        assert not hasattr(main.app.state, "metrics_refresh_owner")
        assert main._route_manager is None
        assert main._background_task is None
        assert owner.task is None
    finally:
        release.set()
        await asyncio.gather(shutdown, return_exceptions=True)
        await main.shutdown_event()


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_failed_lifespan_startup_closes_installed_refresh_owner(
    background_runtime, monkeypatch
):
    async def failed_startup():
        raise RuntimeError("failure after resource initialization")

    monkeypatch.setattr(main, "startup_event", failed_startup)
    try:
        with pytest.raises(RuntimeError, match="resource initialization"):
            async with main.lifespan(main.app):
                pass
        assert not hasattr(main.app.state, "metrics_refresh_owner")
        assert main._route_manager is None
    finally:
        await main.shutdown_event()
