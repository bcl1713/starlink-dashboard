"""Archive recovery has one owned worker, independent of telemetry collection."""

import asyncio
from threading import Event

import pytest

from app.services.flight_events.maintenance import FlightMaintenanceOwner


async def test_close_drains_slow_maintenance_even_when_cancelled_repeatedly():
    entered, release, finished = Event(), Event(), Event()
    calls = []

    def maintain():
        calls.append(1)
        entered.set()
        try:
            assert release.wait(5)
        finally:
            finished.set()

    owner = FlightMaintenanceOwner(maintain)
    await owner.start()
    closing = None
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        # Repeated start cannot add a second worker.
        await owner.start()
        closing = asyncio.create_task(owner.close())
        await asyncio.sleep(0)
        closing.cancel()
        await asyncio.sleep(0)
        closing.cancel()
        done, _ = await asyncio.wait({closing}, timeout=0.05)
        assert not done
        assert calls == [1]
    finally:
        release.set()
        if closing is not None:
            with pytest.raises(asyncio.CancelledError):
                await closing
        else:
            await owner.close()
    assert finished.is_set()
    assert owner.task.done()


async def test_unexpected_maintenance_failure_is_retried(caplog):
    recovered = Event()
    attempts = []

    def maintain():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("maintenance failed")
        recovered.set()

    owner = FlightMaintenanceOwner(maintain, interval=0.01)
    await owner.start()
    try:
        assert await asyncio.to_thread(recovered.wait, 2)
        assert "Flight archive maintenance failed" in caplog.text
    finally:
        await owner.close()
    assert owner.task.done()
