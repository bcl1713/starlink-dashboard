"""Bounded event ownership, failure recovery, and cancellation drain."""

import asyncio
from threading import Event

import pytest

from app.core.metrics.frames import FrameStore, GaugeDefinition


async def test_dirty_burst_owns_one_worker_and_failed_work_does_not_spin():
    from app.core.metrics import lifecycle

    store = FrameStore((GaugeDefinition("test", "test"),))
    attempts = []

    def refresh():
        attempts.append(1)
        store.fail(store.read(), "injected preparation failure")

    owner = lifecycle.MetricsRefreshOwner(
        refresh, background_enabled=False, store=store
    )
    try:
        for _ in range(100):
            owner.mark_dirty("bulk")
        await owner.refresh_without_collection()
        assert len(attempts) == 1
        assert store.read().status == "failed"
        await asyncio.sleep(0.02)
        assert len(attempts) == 1
        owner.mark_dirty("recovery")
        await owner.refresh_without_collection()
        assert len(attempts) == 2
    finally:
        await owner.close()


async def test_repeated_cancellation_drains_refresh_before_close_returns():
    from app.core.metrics import lifecycle

    entered, release, finished = Event(), Event(), Event()

    def refresh():
        entered.set()
        try:
            assert release.wait(3)
        finally:
            finished.set()

    owner = lifecycle.MetricsRefreshOwner(refresh, background_enabled=False)
    owner.mark_dirty("test")
    assert await asyncio.to_thread(entered.wait, 2)
    closing = asyncio.create_task(owner.close())
    try:
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        assert not finished.is_set()
    finally:
        release.set()
        await asyncio.gather(closing, return_exceptions=True)
        await owner.close()
    assert finished.is_set()
    assert owner.task is None


async def test_unexpected_refresh_exception_is_failed_and_does_not_escape_task():
    from app.core.metrics import lifecycle

    store = FrameStore((GaugeDefinition("test", "test"),))

    def broken_admission():
        raise OSError("repository admission unavailable")

    owner = lifecycle.MetricsRefreshOwner(
        broken_admission, background_enabled=False, store=store
    )
    try:
        owner.mark_dirty("test")
        await owner.refresh_without_collection()
        assert store.read().status == "failed"
    finally:
        await owner.close()


async def test_closed_owner_rejects_callback_registration():
    from app.core.metrics import lifecycle
    from app.services.metrics_changes import MetricsChangeSource

    owner = lifecycle.MetricsRefreshOwner(lambda: None, background_enabled=False)
    source = MetricsChangeSource()
    await owner.close()
    with pytest.raises(RuntimeError):
        owner.attach(source)
