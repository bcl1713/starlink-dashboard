"""Bound preview CPU admission without consuming waiting worker threads."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass

from .deadlines import PlanningDeadlineError


@dataclass
class _Admission:
    semaphore: asyncio.Semaphore
    users: int = 0


_admissions: dict[asyncio.AbstractEventLoop, _Admission] = {}


@asynccontextmanager
async def preview_slot(seconds):
    loop = asyncio.get_running_loop()
    admission = _admissions.setdefault(loop, _Admission(asyncio.Semaphore(1)))
    admission.users += 1
    acquired = False
    try:
        try:
            await asyncio.wait_for(admission.semaphore.acquire(), timeout=seconds)
        except TimeoutError as exc:
            raise PlanningDeadlineError(
                "Preview queue exceeded its deadline; retry"
            ) from exc
        acquired = True
        yield
    finally:
        if acquired:
            admission.semaphore.release()
        admission.users -= 1
        if admission.users == 0:
            _admissions.pop(loop)


async def run_owned_preview(awaitable):
    task = asyncio.create_task(awaitable, name="planning-preview")
    try:
        return await asyncio.shield(task)
    finally:
        if not task.done():
            # Cancellation cannot release admission while its thread is running.
            completion = asyncio.gather(task, return_exceptions=True)
            while not completion.done():
                try:
                    await asyncio.shield(completion)
                except asyncio.CancelledError:
                    continue
