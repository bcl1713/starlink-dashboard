"""One lifespan-owned archive worker, independent of live telemetry acquisition."""

import asyncio
import logging

from app.core.metrics.lifecycle import drain_work

logger = logging.getLogger(__name__)


class FlightMaintenanceOwner:
    def __init__(self, maintain, *, interval=1.0):
        self.maintain = maintain
        self.interval = interval
        self.stopping = asyncio.Event()
        self.task = None

    async def start(self):
        if self.task is None and not self.stopping.is_set():
            self.task = asyncio.create_task(
                self._run(), name="flight-archive-maintenance"
            )

    async def _run(self):
        while not self.stopping.is_set():
            worker = asyncio.create_task(asyncio.to_thread(self.maintain))
            try:
                await drain_work(worker)
            except Exception:
                logger.exception("Flight archive maintenance failed")
            try:
                await asyncio.wait_for(self.stopping.wait(), timeout=self.interval)
            except TimeoutError:
                pass

    async def close(self):
        self.stopping.set()
        if self.task is not None:
            await drain_work(self.task)
