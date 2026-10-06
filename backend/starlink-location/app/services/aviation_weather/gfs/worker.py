"""Optional worker owns HTTP and one reaped scientific process group."""

import asyncio
import fcntl
import logging
import os
import signal
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

import httpx
from app.models.aviation_grid import GridCandidate, GridDescriptor
from app.services.aviation_weather.settings import AviationSettingsStore

from .ipc import GfsMailbox
from .quota import GfsQuota
from .store import GfsProductStore, atomic_json
from .transport import GfsTransport

LOGGER = logging.getLogger(__name__)
DECODE_SECONDS = 120
TERM_SECONDS = 10


async def stop_child(process):
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            async with asyncio.timeout(TERM_SECONDS):
                await process.wait()
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
    else:
        await process.wait()


class GfsWorker:
    def __init__(
        self, mailbox, store, transport, *, clock=time.time, decoder_command=None
    ):
        self.mailbox, self.store, self.transport = mailbox, store, transport
        self.store.demand_check = mailbox.current_locked
        self.clock, self.decoder_command = clock, decoder_command
        self.owner = uuid.uuid4().hex
        self._stop = asyncio.Event()
        self._closed = asyncio.Event()
        self._running = False
        self._active = None
        self._lock = None
        self.child = None

    def stop(self):
        self._stop.set()

    async def _decode(self, stage, bundle, settings):
        manifest = {
            **{
                key: value
                for key, value in asdict(bundle).items()
                if key not in {"paths", "ranges"}
            },
            "paths": [str(path.relative_to(stage)) for path in bundle.paths],
            "ranges": [asdict(ref) for ref in bundle.ranges],
            "selection": settings.gfs_selection.model_dump(),
        }
        atomic_json(stage / "bundle.json", manifest)
        command = [
            *(
                self.decoder_command
                or [
                    sys.executable,
                    "-m",
                    "app.services.aviation_weather.gfs.decoder_runner",
                ]
            ),
            str(stage / "bundle.json"),
            str(stage / "candidate"),
            str(os.getpid()),
            str(int(self.clock() * 1000)),
        ]
        atomic_json(
            stage / "owner.json",
            {"command": command, "worker": self.owner, "state": "starting"},
        )
        environment = {
            **os.environ,
            "PYTHONPATH": str(Path(__file__).resolve().parents[4]),
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
        # Shield creation only, so a cancellation between spawn and receiving
        # the handle still obtains and reaps the exact process it created.
        spawning = asyncio.create_task(
            asyncio.create_subprocess_exec(
                *command,
                env=environment,
                start_new_session=True,
                pass_fds=(self._lock.fileno(),)
            )
        )
        try:
            self.child = await asyncio.shield(spawning)
        except asyncio.CancelledError:
            self.child = await spawning
            await stop_child(self.child)
            self.child = None
            raise
        process = self.child
        try:
            atomic_json(
                stage / "owner.json",
                {
                    "command": command,
                    "worker": self.owner,
                    "pid": process.pid,
                    "pgid": process.pid,
                },
            )
            async with asyncio.timeout(DECODE_SECONDS):
                code = await process.wait()
            if code != 0:
                raise ValueError("Scientific child rejected source fields")
            descriptor = GridDescriptor.model_validate_json(
                (stage / "candidate/grid.json").read_bytes()
            )
            return GridCandidate(descriptor, stage / "candidate")
        finally:
            await stop_child(process)
            self.child = None

    async def _ingest(self, settings):
        self.store.prune(int(self.clock() * 1000))
        with self.store.staging() as stage:
            bundle = await self.transport.acquire(
                settings.gfs_selection, stage / "source"
            )
            candidate = await self._decode(stage, bundle, settings)
            self.store.publish(candidate, settings.revision)
        self.store.prune(int(self.clock() * 1000))

    async def _cancel(self):
        if self._active:
            self._active.cancel()
            await asyncio.gather(self._active, return_exceptions=True)
            self._active = None

    async def run(self):
        self._lock = (self.mailbox.root / "worker.lock").open("a")
        try:
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._lock.close()
            self._lock = None
            await self.transport.aclose()
            self._closed.set()
            raise RuntimeError("Scientific worker already has an owner") from None
        key, retry_at, heartbeat_at, last_utc = None, 0, 0, 0
        self._running = True
        try:
            self.mailbox.worker_started(self.owner, int(self.clock() * 1000))
            while not self._stop.is_set():
                now = int(self.clock() * 1000)
                settings = self.mailbox.settings.get()
                if now < last_utc:
                    self.mailbox.invalidate(settings.revision)
                last_utc = max(now, last_utc)
                demand = self.mailbox.current(now)
                desired = (
                    (
                        demand.revision,
                        demand.gfs_selection,
                        demand.winds,
                        demand.temperature,
                    )
                    if demand
                    else None
                )
                if desired != key:
                    await self._cancel()
                    key, retry_at, heartbeat_at = desired, 0, 0
                if self._active and self._active.done():
                    try:
                        self._active.result()
                    except (
                        OSError,
                        ValueError,
                        TimeoutError,
                        httpx.HTTPError,
                    ) as error:
                        LOGGER.warning(
                            "GFS selection unavailable: %s", type(error).__name__
                        )
                        retry_at = time.monotonic() + 60
                    else:
                        retry_at = time.monotonic() + 600
                    self._active = None
                if time.monotonic() >= heartbeat_at:
                    self.mailbox.heartbeat(settings.revision, self.owner, now)
                    heartbeat_at = time.monotonic() + 5
                if demand and self._active is None and time.monotonic() >= retry_at:
                    self._active = asyncio.create_task(self._ingest(demand))
                try:
                    async with asyncio.timeout(1):
                        await self._stop.wait()
                except TimeoutError:
                    pass
        finally:
            try:
                await self._cancel()
                await self.transport.aclose()
            finally:
                if self._lock:
                    self._lock.close()
                    self._lock = None
                self._running = False
                self._closed.set()

    async def aclose(self):
        self.stop()
        if self._running:
            await self._closed.wait()
        else:
            await self.transport.aclose()


async def main():
    logging.basicConfig(level=logging.INFO)
    mailbox_path = Path(os.environ.get("GFS_MAILBOX_PATH", "/app/data/gfs-mailbox"))
    root = Path(os.environ.get("GFS_ARTIFACT_PATH", "/app/data/gfs"))
    settings = AviationSettingsStore(
        Path(
            os.environ.get(
                "AVIATION_SETTINGS_PATH", "/app/data/settings/aviation-weather.json"
            )
        ),
        readonly=True,
    )
    mailbox = GfsMailbox(mailbox_path, settings)
    store = GfsProductStore(root, mailbox_path, settings, require_demand=True)
    with GfsQuota(mailbox_path) as quota:
        worker = GfsWorker(mailbox, store, GfsTransport(quota))
        loop = asyncio.get_running_loop()
        for signum in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(signum, worker.stop)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
