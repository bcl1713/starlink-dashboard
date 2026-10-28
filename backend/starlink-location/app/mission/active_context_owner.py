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

    def __init__(self, manager, mode_provider, replay_provider=lambda: None):
        self.manager = manager
        self.mode_provider = mode_provider
        self.replay_provider = replay_provider
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
        worker = asyncio.create_task(asyncio.to_thread(self._reconcile))
        return await _drain(worker)

    def _reconcile(self):
        from app.core.metrics.prometheus_metrics import MISSION_METRICS
        from app.mission.active_context_cache import active_mission_snapshot_is_current
        from app.mission.storage import get_active_leg_lock

        snapshot = get_active_mission_snapshot(self.manager)
        with get_active_leg_lock():
            replay = self.replay_provider()
            replay_owns_selection = (
                self.mode_provider() == "simulation"
                and replay is not None
                and replay.run is not None
            )
            if replay_owns_selection:
                # Live reconciliation may have published an owner since replay
                # cancellation. Re-entering terminal replay must clear it too.
                if replay.state in ("cancelled", "failed"):
                    MISSION_METRICS.clear_current()
            elif active_mission_snapshot_is_current(self.manager, snapshot):
                if snapshot.binding is not None:
                    binding = snapshot.binding
                    MISSION_METRICS.activate(
                        binding.parent_mission_id, binding.route_id
                    )
                else:
                    MISSION_METRICS.clear_current()
            return snapshot

    async def _run(self):
        while not self.stopping.is_set():
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
