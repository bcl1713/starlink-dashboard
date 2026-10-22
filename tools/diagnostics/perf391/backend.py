# ruff: noqa: I001
# Fixture initialization must precede application instrumentation imports.
"""Disposable ASGI timing wrapper. Only mounted by the diagnostic runner.

PERF391_DIAGNOSTICS=1 and PERF_SYNTHETIC=1 are required. Never import from app.
"""

import asyncio
import contextlib
import functools
import itertools
import os
import time
from pathlib import Path

from trace391 import Trace, model_token, operation, token

if (
    os.environ.get("PERF391_DIAGNOSTICS") != "1"
    or os.environ.get("PERF_SYNTHETIC") != "1"
):
    raise RuntimeError("Requires explicit isolated synthetic diagnostics")

from performance.fixture import app as application, main
from performance.state import capture
from app.core.metrics import prometheus_metrics as metrics
from app.mission import storage
from app.simulation.coordinator import SimulationCoordinator
import fastapi.routing
import starlette.concurrency

trace = Trace()
counter = itertools.count()
fault = {"boundary": None, "seconds": 0}


def inject(boundary):
    if fault["boundary"] == boundary:
        seconds = fault["seconds"]
        fault["boundary"] = None
        trace.event("injection", boundary=boundary, duration_ns=int(seconds * 1e9))
        time.sleep(seconds)


# CPU and duration bracket the injected delay as well as the real operation.
for attribute, boundary in [("update", "collection")]:
    trace.wrap(
        SimulationCoordinator,
        attribute,
        boundary,
        before=lambda: inject("collection"),
        after=lambda result: trace.event(
            "acquisition", identity=token(getattr(result, "timestamp", None))
        ),
    )
trace.wrap(main, "_background_update_tick", "tick", before=lambda: inject("tick"))
trace.wrap(storage, "get_active_leg_lock", "gate_lookup")

# Instrument the actual admission class, preserving its return protocol and nesting.
gate_class = type(storage.get_active_leg_lock())
original_acquire, original_release = gate_class.acquire, gate_class.release
held = {}


@functools.wraps(original_acquire)
def acquire(self, *args, **kwargs):
    key = (id(self), __import__("threading").get_native_id())
    depth = len(held.get(key, []))
    with trace.span("admission", owner=token(id(self)), depth=depth):
        inject("admission")
        result = original_acquire(self, *args, **kwargs)
    held.setdefault(key, []).append(
        (time.monotonic_ns(), time.thread_time_ns(), operation.get())
    )
    trace.event("lock.acquired", owner=token(id(self)), depth=depth)
    return result


@functools.wraps(original_release)
def release(self, *args, **kwargs):
    key = (id(self), __import__("threading").get_native_id())
    try:
        return original_release(self, *args, **kwargs)
    finally:
        stack = held.get(key, [])
        if stack:
            began, cpu, owner = stack.pop()
            trace.event(
                "lock.released",
                owner=owner,
                depth=len(stack),
                wall_ns=time.monotonic_ns() - began,
                cpu_ns=time.thread_time_ns() - cpu,
            )
            if not stack:
                held.pop(key, None)


gate_class.acquire, gate_class.release = acquire, release
trace.restores.extend(
    [
        (gate_class, "acquire", original_acquire),
        (gate_class, "release", original_release),
    ]
)

# Candidate-only boundaries are explicitly absent on legacy original.
try:
    from app.core.metrics import frame_builder, source_admission
    from app.core.metrics.frames import FrameStore

    trace.wrap(
        frame_builder,
        "prepare_frame",
        "frame_prepare",
        before=lambda: inject("frame_prepare"),
        after=lambda frame: trace.event(
            "frame.identity",
            identity=token(frame.identity),
            route=token(frame.identity.route_id),
            input=token(frame.identity.input_revision),
            replay=token(
                (
                    frame.identity.replay_runtime_id,
                    frame.identity.replay_run_id,
                    frame.identity.replay_revision,
                )
            ),
        ),
    )
    trace.wrap(
        source_admission,
        "frame_inputs_are_current",
        "source_validation",
        before=lambda: inject("source_validation"),
        after=lambda result: trace.event(
            "source_validation.result", result=bool(result)
        ),
    )
    trace.wrap(
        FrameStore,
        "publish",
        "publication",
        before=lambda: inject("publication"),
        after=lambda result: trace.event("publication.result", result=bool(result)),
    )
    original_detach = frame_builder.FrameInputs.__post_init__

    def detach(inputs):
        with trace.span("input_detach"):
            original_detach(inputs)
            trace.event(
                "config.identity",
                config=model_token(inputs.config),
            )

    frame_builder.FrameInputs.__post_init__ = detach
    trace.restores.append((frame_builder.FrameInputs, "__post_init__", original_detach))
    from app.core.metrics import metric_updater

    trace.wrap(metric_updater, "prepare_metrics_from_telemetry", "producer_prepare")
    from app.core import metrics as metrics_package

    original_update_metrics = metrics_package.update_metrics_from_telemetry

    @functools.wraps(original_update_metrics)
    def update_metrics(*args, **kwargs):
        current = kwargs.get("source_is_current")
        if current is not None:

            def checked():
                with trace.span("source_binding_validation"):
                    return current()

            kwargs["source_is_current"] = checked
        return original_update_metrics(*args, **kwargs)

    metrics_package.update_metrics_from_telemetry = update_metrics
    trace.restores.append(
        (metrics_package, "update_metrics_from_telemetry", original_update_metrics)
    )

except ImportError:
    trace.event("legacy_frame_boundaries", available=False)

# Dispatch is measured before executor admission, worker entry in the worker.
original_pool = starlette.concurrency.run_in_threadpool


async def pool(func, *args, **kwargs):
    with trace.span("worker_dispatch"):
        if fault["boundary"] == "dispatch":
            seconds = fault["seconds"]
            fault["boundary"] = None
            trace.event(
                "injection", boundary="dispatch", duration_ns=int(seconds * 1e9)
            )
            await asyncio.sleep(seconds)

        def worker():
            with trace.span("worker_execution"):
                inject("worker")
                return func(*args, **kwargs)

        return await original_pool(worker)


for module in (starlette.concurrency, fastapi.routing):
    trace.restores.append((module, "run_in_threadpool", module.run_in_threadpool))
    module.run_in_threadpool = pool

original_to_thread = asyncio.to_thread


async def to_thread(func, *args, **kwargs):
    if getattr(func, "__name__", "") != "_background_update_tick":
        return await original_to_thread(func, *args, **kwargs)
    ident = operation.set(f"tick-{next(counter)}")
    trace.event("tick.dispatch")
    try:
        return await original_to_thread(func, *args, **kwargs)
    finally:
        operation.reset(ident)


asyncio.to_thread = to_thread
trace.restores.append((asyncio, "to_thread", original_to_thread))


@application.get("/api/_diagnostic/state")
def state():
    # Same frozen capture, instrumented gate, no payload retained by diagnostics.
    with storage.get_active_leg_lock(), trace.span("source_capture"):
        result = capture(main, metrics)
        result["diagnostic_capture_ns"] = time.monotonic_ns()
        return result


@application.post("/api/_diagnostic/fault/{boundary}")
def arm(boundary: str):
    allowed = {
        "collection",
        "dispatch",
        "tick",
        "admission",
        "worker",
        "frame_prepare",
        "source_validation",
        "publication",
        "backend_loop",
        "lock_hold",
        "response",
    }
    if boundary not in allowed:
        raise ValueError("Unknown diagnostic boundary")
    fault.update(boundary=boundary, seconds=0.7)
    return {"armed": boundary}


def numeric_file(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, PermissionError):
        return None


async def heartbeat():
    deadline = time.monotonic_ns()
    last_host = 0
    while True:
        deadline += 50_000_000
        await asyncio.sleep(max(0, (deadline - time.monotonic_ns()) / 1e9))
        now = time.monotonic_ns()
        trace.event("loop.wake", scheduled_ns=deadline, delay_ns=max(0, now - deadline))
        if fault["boundary"] == "backend_loop":
            inject("backend_loop")
        if fault["boundary"] == "lock_hold":

            def hold():
                with storage.get_active_leg_lock():
                    inject("lock_hold")

            await asyncio.to_thread(hold)
        if now - last_host >= 1_000_000_000:
            last_host = now
            sched = {
                p.name: numeric_file(p / "schedstat")
                for p in Path("/proc/self/task").iterdir()
            }
            trace.event(
                "host.sample",
                schedstat=sched,
                pressure=numeric_file("/proc/pressure/cpu"),
                cpu_stat=numeric_file("/sys/fs/cgroup/cpu.stat"),
                load=numeric_file("/proc/loadavg"),
                host_cpu=(numeric_file("/proc/stat") or "").splitlines()[:1],
            )
        # Do not emit catch-up bursts after a stall.
        if now - deadline >= 50_000_000:
            deadline = now


original_lifespan = application.router.lifespan_context


@contextlib.asynccontextmanager
async def lifespan(app):
    async with original_lifespan(app):
        task = asyncio.create_task(heartbeat())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    trace.flush(Path("/diagnostic-output/backend.json"))
    trace.close()


application.router.lifespan_context = lifespan


class Boundary:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # Accept only bounded generated request IDs; never log arbitrary headers/paths.
        headers = dict(scope.get("headers", []))
        raw = headers.get(b"x-diagnostic-id", b"").decode("ascii", errors="ignore")
        ident = (
            raw
            if raw.startswith("diag-") and raw[5:].isdigit() and len(raw) < 40
            else f"backend-{next(counter)}"
        )
        ctx = operation.set(ident)
        trace.event("asgi.arrival")

        async def timed_send(message):
            if message["type"] == "http.response.start":
                inject("response")
                trace.event("asgi.headers", status=message["status"])
            elif message["type"] == "http.response.body" and not message.get(
                "more_body", False
            ):
                trace.event("asgi.body")
            await send(message)

        try:
            await self.app(scope, receive, timed_send)
        finally:
            trace.event("asgi.end")
            operation.reset(ctx)


app = Boundary(application)
