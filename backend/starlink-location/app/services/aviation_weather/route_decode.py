"""Bounded subprocess I/O and an explicitly app-owned, latest-input scheduler."""

import asyncio
import json
import logging
import os
import signal
import sys
from dataclasses import dataclass, field

from app.models.route_sigmets import (
    MAX_ADVISORIES,
    MAX_RESULT_BYTES,
    GeometryResult,
    RouteContext,
)
from app.services.overview_weather.protocol import WeatherUnavailable

from .decode import await_owned

MAX_INPUT_BYTES = 32 * 1024**2
MAX_COLLECTION_BYTES = 16 * 1024**2
logger = logging.getLogger(__name__)
WORKER_COMMAND = (sys.executable, "-m", "app.services.aviation_weather.route_worker")
WALL_SECONDS = 5
TERM_GRACE_SECONDS = 1
CHUNK_BYTES = 64 * 1024


def _encode(context, collection):
    try:
        if (
            not isinstance(collection, dict)
            or not isinstance(collection.get("features"), list)
            or len(collection["features"]) > MAX_ADVISORIES
        ):
            raise ValueError("advisory input limit")
        encoder = json.JSONEncoder(separators=(",", ":"), allow_nan=False)
        body = bytearray(b'{"points":')

        def append(value, limit):
            initial = len(body)
            for chunk in encoder.iterencode(value):
                encoded = chunk.encode()
                if (
                    len(body) + len(encoded) > MAX_INPUT_BYTES
                    or len(body) - initial + len(encoded) > limit
                ):
                    raise ValueError("worker input limit")
                body.extend(encoded)

        append(context.points, MAX_INPUT_BYTES)
        body.extend(b',"collection":')
        append(collection, MAX_COLLECTION_BYTES)
        body.extend(b"}")
        if len(body) > MAX_INPUT_BYTES:
            raise ValueError("worker input limit")
        return bytes(body)
    except (ValueError, TypeError, OverflowError) as error:
        raise WeatherUnavailable() from error


async def _read(process):
    output = bytearray()
    while chunk := await process.stdout.read(CHUNK_BYTES):
        if len(output) + len(chunk) > MAX_RESULT_BYTES:
            raise WeatherUnavailable()
        output.extend(chunk)
    return output


async def _write(process, body):
    try:
        for offset in range(0, len(body), CHUNK_BYTES):
            process.stdin.write(body[offset : offset + CHUNK_BYTES])
            await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        process.stdin.close()


async def _cleanup(process, io_tasks):
    # The child starts a new session. Only its verified PID/session is signalled.
    def send(sig):
        try:
            if os.getpgid(process.pid) == process.pid:
                os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    process.stdin.close()
    for task in io_tasks:
        task.cancel()
    await asyncio.gather(*io_tasks, return_exceptions=True)

    async def discard():
        while await process.stdout.read(CHUNK_BYTES):
            pass

    # asyncio's process.wait() can wait for a paused stdout pipe even after
    # waitpid has reaped the child. Drain concurrently with TERM/grace/KILL.
    drain = asyncio.create_task(discard())
    try:
        if process.returncode is None:
            send(signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), TERM_GRACE_SECONDS)
            except TimeoutError:
                send(signal.SIGKILL)
        await process.wait()
        await drain
        try:
            await process.stdin.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass
    finally:
        if not drain.done():
            drain.cancel()
        await asyncio.gather(drain, return_exceptions=True)


async def _evaluate_body(body):
    process = None
    io_tasks = []
    # Shield creation too: cancellation between spawn and receiving its handle
    # must not orphan a process. Ownership transfers before cancellation escapes.
    creation = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *WORKER_COMMAND,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"},
            limit=CHUNK_BYTES,
        )
    )
    try:
        async with asyncio.timeout(WALL_SECONDS):
            process = await asyncio.shield(creation)
            writer = asyncio.create_task(_write(process, body))
            reader = asyncio.create_task(_read(process))
            io_tasks.extend((writer, reader))
            output = await reader
            await writer
            await process.wait()
            if process.returncode != 0:
                raise WeatherUnavailable()
            return GeometryResult.model_validate_json(output)
    except (TimeoutError, ValueError, OSError) as error:
        raise WeatherUnavailable() from error
    finally:

        async def finish():
            try:
                owned = process if process is not None else await creation
            except OSError:
                return  # Spawn failed; the outer handler maps it to unavailable.
            await _cleanup(owned, io_tasks)

        await await_owned(asyncio.create_task(finish()))


async def evaluate_in_worker(context: RouteContext, collection: dict) -> GeometryResult:
    """One disposable worker; cancellation returns only after process/pipe cleanup."""
    # Serialization is bounded work too; wait for its thread on cancellation so
    # replacement cannot accumulate detached serializers. No geometry runs here.
    encoding = asyncio.create_task(asyncio.to_thread(_encode, context, collection))
    try:
        body = await asyncio.shield(encoding)
    finally:
        await await_owned(encoding)
    return await _evaluate_body(body)


@dataclass
class _Job:
    key: tuple[str, int]
    context: RouteContext
    collection: dict
    future: asyncio.Future
    readers: int = 0
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    execution: asyncio.Task | None = None


class GeometryWorker:
    """One app owner, one live process, one replaceable pending input; no cache."""

    def __init__(self):
        self._active = None
        self._pending = None
        self._driver = None
        self._closed = False

    def _reject(self, job):
        if job is not None:
            if not job.future.done():
                job.future.set_exception(WeatherUnavailable())
                # A superseded caller may already have cancelled its lease.
                job.future.exception()
            job.finished.set()

    async def _drive(self):
        while self._pending is not None and not self._closed:
            job, self._pending = self._pending, None
            self._active = job
            job.execution = asyncio.create_task(
                evaluate_in_worker(job.context, job.collection)
            )
            try:
                result = await job.execution
                if not job.future.done():
                    job.future.set_result(result)
            except (asyncio.CancelledError, WeatherUnavailable):
                self._reject(job)
            except Exception:
                logger.exception("Unexpected route geometry worker failure")
                self._reject(job)
            finally:
                job.finished.set()
                self._active = None

    async def evaluate(self, context: RouteContext, collection: dict) -> GeometryResult:
        if self._closed:
            raise WeatherUnavailable()
        # Caller must retain an immutable collection per admitted source instance.
        # This identity coalesces concurrent readers; it is not a content cache.
        key = (context.context_key, id(collection))
        latest = self._pending or self._active
        if (
            latest is not None
            and latest.key == key
            and not latest.finished.is_set()
            and (latest.execution is None or not latest.execution.cancelling())
        ):
            job = latest
        else:
            self._reject(self._pending)
            job = _Job(
                key, context, collection, asyncio.get_running_loop().create_future()
            )
            self._pending = job
            if (
                self._active is not None
                and self._active.execution is not None
                and not self._active.execution.cancelling()
            ):
                self._active.execution.cancel()
            if self._driver is None or self._driver.done():
                self._driver = asyncio.create_task(self._drive())
        job.readers += 1
        try:
            return await asyncio.shield(job.future)
        finally:
            job.readers -= 1
            if job.readers == 0:
                if self._pending is job:
                    self._pending = None
                    self._reject(job)
                if self._active is job and job.execution is not None:
                    if not job.execution.done() and not job.execution.cancelling():
                        job.execution.cancel()
                    await await_owned(asyncio.create_task(job.finished.wait()))

    async def aclose(self) -> None:
        """Reject future demand and await termination/reaping of owned work."""
        self._closed = True
        self._reject(self._pending)
        self._pending = None
        if (
            self._active is not None
            and self._active.execution is not None
            and not self._active.execution.done()
            and not self._active.execution.cancelling()
        ):
            self._active.execution.cancel()
        if self._driver is not None:
            await await_owned(self._driver)
