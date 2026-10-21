"""Coalesced refresh work owned by the existing loop or one bounded task."""

import asyncio
import logging
from threading import Lock

from app.core.metrics.prometheus_metrics import FRAME_STORE

logger = logging.getLogger(__name__)


async def drain_work(task):
    """Repeated cancellation must not abandon an executor worker or child task."""
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


class MetricsRefreshOwner:
    def __init__(self, refresh, *, background_enabled, store=FRAME_STORE):
        self._refresh = refresh
        self._background_enabled = background_enabled
        self._store = store
        self._loop = asyncio.get_running_loop()
        self._event = asyncio.Event()
        self._lock = Lock()
        self._closed = False
        self._scheduled = False
        self._attempted_revision = -1
        self._sources = []
        self.task = None
        self._work = None

    def attach(self, *sources):
        with self._lock:
            if self._closed:
                raise RuntimeError("Metric refresh owner is closed")
            for source in sources:
                source.set_metrics_change_callback(self.mark_dirty)
                self._sources.append(source)

    def mark_dirty(self, reason):
        with self._lock:
            if self._closed:
                return
            self._store.invalidate(reason)
            if not self._scheduled:
                self._scheduled = True
                self._loop.call_soon_threadsafe(self._wake)

    def _wake(self):
        with self._lock:
            self._scheduled = False
            if self._closed:
                return
            self._event.set()
            if not self._background_enabled and self.task is None:
                self.task = self._loop.create_task(self._one_shot())

    async def _one_shot(self):
        try:
            while not self._closed:
                revision = self._store.read().input_revision
                if (
                    self._store.read().status == "ready"
                    or revision == self._attempted_revision
                ):
                    break
                await self.refresh_without_collection()
        finally:
            self.task = None

    async def refresh_without_collection(self, *, force=False):
        if self._closed:
            return
        if self._work is not None:
            return await drain_work(self._work)
        head = self._store.read()
        if not force and (
            head.status == "ready" or head.input_revision == self._attempted_revision
        ):
            return
        self._attempted_revision = head.input_revision
        self._work = asyncio.create_task(self._run_refresh(head))
        return await drain_work(self._work)

    async def _run_refresh(self, expected):
        try:
            return await asyncio.to_thread(self._refresh)
        except Exception:
            self._store.fail(expected, "refresh owner failed")
            logger.exception("Metric refresh owner failed")
            return False
        finally:
            # Release the shared handle in its owner before waking waiters. A
            # cancelled waiter may resume after the one-shot; it cannot be
            # responsible for clearing completed work or clear a newer task.
            self._work = None
            head = self._store.read()
            if head.status == "failed":
                self._attempted_revision = head.input_revision

    async def wait(self, delay, replay_wakeup=None):
        """Return True only for a source deadline/replay wake, never a dirty wake."""
        dirty = asyncio.create_task(self._event.wait())
        replay = (
            asyncio.create_task(replay_wakeup.wait(delay)) if replay_wakeup else None
        )
        waiting = {dirty, replay} if replay else {dirty}
        try:
            done, _ = await asyncio.wait(
                waiting, timeout=max(0, delay), return_when=asyncio.FIRST_COMPLETED
            )
            self._event.clear()
            return not done or (replay is not None and replay in done)
        finally:
            for task in waiting:
                task.cancel()
            await asyncio.gather(*waiting, return_exceptions=True)

    async def close(self):
        with self._lock:
            self._closed = True
            sources, self._sources = self._sources, []
        for source in sources:
            source.set_metrics_change_callback(None)
        self._event.set()
        task = self.task or self._work
        if task is not None:
            await drain_work(task)
