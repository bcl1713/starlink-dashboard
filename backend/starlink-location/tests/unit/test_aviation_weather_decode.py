"""Cancellation storms must wait for the one owned decoder to be reaped."""

import asyncio

from app.services.aviation_weather import decode


class Process:
    def __init__(self):
        self.returncode = None
        self.started = asyncio.Event()
        self.terminated = asyncio.Event()
        self.reaped = asyncio.Event()
        self.killed = False
        self.released = asyncio.Event()

    async def communicate(self, body):
        self.started.set()
        await asyncio.Event().wait()

    def terminate(self):
        self.terminated.set()

    def kill(self):
        self.killed = True
        self.released.set()

    async def wait(self):
        await self.released.wait()
        self.returncode = -15
        self.reaped.set()
        return self.returncode


async def test_repeated_cancellation_cannot_escape_worker_cleanup(monkeypatch):
    process = Process()

    async def create(*args, **kwargs):
        return process

    monkeypatch.setattr(decode.asyncio, "create_subprocess_exec", create)
    task = asyncio.create_task(decode.normalize_in_worker("metar", b"x", 1791244800000))
    await process.started.wait()
    task.cancel()
    await process.terminated.wait()
    task.cancel()
    # A second cancellation may interrupt the wait but cannot finish the owner
    # until the verified worker has terminated and been reaped.
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert not task.done()
    process.released.set()
    result = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(result[0], asyncio.CancelledError)
    assert process.reaped.is_set()
