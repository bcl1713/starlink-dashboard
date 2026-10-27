"""Lifespan-owned reconciliation, separate from telemetry acquisition."""

import asyncio
import logging

from app.mission.active_context_cache import get_active_mission_snapshot

logger = logging.getLogger(__name__)


async def _drain(task):
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    result = task.result()
    if cancelled:
        raise asyncio.CancelledError
    return result


class ActiveContextOwner:
    """One serial executor job at a time; close drains every owned worker."""

    def __init__(self, manager, mode_provider):
        self.manager = manager
        self.mode_provider = mode_provider
        self.stopping = asyncio.Event()
        self.task = None
        self.failed = False

    def __bool__(self):
        return (
            self.task is not None
            and not self.task.done()
            and not self.stopping.is_set()
            and not self.failed
        )

    async def start(self):
        await self.refresh()
        self.manager._active_mission_context_owner = self
        self.task = asyncio.create_task(
            self._run(), name="active-mission-reconciliation"
        )

    async def refresh(self):
        worker = asyncio.create_task(
            asyncio.to_thread(get_active_mission_snapshot, self.manager)
        )
        return await _drain(worker)

    async def _run(self):
        while not self.stopping.is_set():
            if self.mode_provider() == "live":
                try:
                    await self.refresh()
                    self.failed = False
                except Exception:
                    if not self.failed:
                        logger.exception("Active mission reconciliation owner failed")
                    self.failed = True
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=0.25)
            except TimeoutError:
                pass

    async def close(self):
        self.stopping.set()
        try:
            if self.task is not None:
                await _drain(self.task)
        finally:
            if getattr(self.manager, "_active_mission_context_owner", None) is self:
                del self.manager._active_mission_context_owner
