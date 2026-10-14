"""Preview CPU admission yields the event loop and retains worker ownership."""

import asyncio
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.mission.planning import routes


@pytest.mark.parametrize("cancel_active", [False, True])
def test_preview_work_is_serial_and_cancelled_owner_drains(cancel_active):
    entered, release, second_entered = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )

    def preview(mission, leg, request):
        if leg == "first":
            entered.set()
            assert release.wait(3)
        else:
            second_entered.set()
        return leg

    async def scenario():
        service = SimpleNamespace(preview=preview)
        first = asyncio.create_task(routes.preview_draft("m", "first", None, service))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            if cancel_active:
                first.cancel()
            second = asyncio.create_task(
                routes.preview_draft("m", "second", None, service)
            )
            await asyncio.sleep(0.05)
            assert (
                not second_entered.is_set()
            ), "Concurrent preview work escaped admission"
        finally:
            release.set()
            results = await asyncio.gather(
                first, *([second] if second else []), return_exceptions=True
            )
        assert results[-1] == "second"
        if cancel_active:
            assert isinstance(results[0], asyncio.CancelledError)
        else:
            assert results[0] == "first"

    asyncio.run(scenario())


def test_queued_preview_cancellation_does_not_run_or_strand_next():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def preview(mission, leg, request):
        calls.append(leg)
        if leg == "first":
            entered.set()
            assert release.wait(3)
        return leg

    async def scenario():
        service = SimpleNamespace(preview=preview)
        first = asyncio.create_task(routes.preview_draft("m", "first", None, service))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            second = asyncio.create_task(
                routes.preview_draft("m", "second", None, service)
            )
            await asyncio.sleep(0.03)
            second.cancel()
            await asyncio.gather(second, return_exceptions=True)
            assert calls == ["first"]
        finally:
            release.set()
            await asyncio.gather(first, return_exceptions=True)
        assert await routes.preview_draft("m", "third", None, service) == "third"
        assert calls == ["first", "third"]

    asyncio.run(scenario())


def test_preview_admission_deadline_is_retryable(monkeypatch):
    entered, release = threading.Event(), threading.Event()

    def preview(mission, leg, request):
        if leg == "first":
            entered.set()
            assert release.wait(3)
        return leg

    async def scenario():
        service = SimpleNamespace(preview=preview)
        first = asyncio.create_task(routes.preview_draft("m", "first", None, service))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            with pytest.raises(HTTPException) as error:
                await routes.preview_draft("m", "second", None, service)
            assert error.value.status_code == 503
            assert error.value.detail["retryable"]
        finally:
            release.set()
            await asyncio.gather(first, return_exceptions=True)

    monkeypatch.setattr(routes, "PREVIEW_QUEUE_SECONDS", 0.02, raising=False)
    asyncio.run(scenario())
