"""Opt-in bounded acceptance counters. Uninstrumented controls use fixture:app."""

import asyncio
import cProfile
import sqlite3
import threading
import time
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager

lock = threading.Lock()
counts = Counter()
armed_profiles = set()
timings = defaultdict(lambda: deque(maxlen=4096))
connect = sqlite3.connect


def statement(sql):
    # Never retain SQL text, parameters, or database contents.
    operation = sql.lstrip().split(None, 1)[0].upper() if sql.strip() else ""
    with lock:
        counts["statements"] += 1
        if operation in ("BEGIN", "COMMIT", "ROLLBACK", "INSERT", "UPDATE", "DELETE"):
            counts[operation.lower()] += 1


def measured_connect(*args, **kwargs):
    connection = connect(*args, **kwargs)
    connection.set_trace_callback(statement)
    with lock:
        counts["opens"] += 1
    return connection


sqlite3.connect = measured_connect
from overview_history.trace import QueryTrace
from performance.fixture import app, main

original_tick = main._background_update_tick


def tick(*args, **kwargs):
    began, cpu = time.perf_counter(), time.thread_time()
    profile = cProfile.Profile() if "tick" in armed_profiles else None
    if profile:
        armed_profiles.discard("tick")
        profile.enable()
    try:
        return original_tick(*args, **kwargs)
    finally:
        if profile:
            profile.disable()
            profile.dump_stats("/data/perf-tick.prof")
        with lock:
            timings["tick_wall_ms"].append((time.perf_counter() - began) * 1000)
            timings["tick_thread_cpu_ms"].append((time.thread_time() - cpu) * 1000)
            counts["ticks"] += 1


main._background_update_tick = tick
from app.api import metrics_export

original_prepare = metrics_export._prepare_metrics


def prepare_metrics(*args, **kwargs):
    began, cpu = time.perf_counter(), time.thread_time()
    profile = cProfile.Profile() if "metrics" in armed_profiles else None
    if profile:
        armed_profiles.discard("metrics")
        profile.enable()
    try:
        return original_prepare(*args, **kwargs)
    finally:
        if profile:
            profile.disable()
            profile.dump_stats("/data/perf-metrics.prof")
        with lock:
            timings["metrics_prepare_wall_ms"].append(
                (time.perf_counter() - began) * 1000
            )
            timings["metrics_prepare_thread_cpu_ms"].append(
                (time.thread_time() - cpu) * 1000
            )


metrics_export._prepare_metrics = prepare_metrics


class Timing:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        selected = path in (
            "/metrics",
            "/api/status",
            "/api/overview-history",
        ) or path.startswith("/api/v2/operator/")
        began = time.perf_counter()
        try:
            return await self.app(scope, receive, send)
        finally:
            if selected and scope["type"] == "http":
                key = (
                    path
                    if not path.startswith("/api/v2/operator/")
                    else "operator_read_or_write"
                )
                with lock:
                    counts["http_requests"] += 1
                    timings[key].append((time.perf_counter() - began) * 1000)


app.add_middleware(Timing)
original_lifespan = app.router.lifespan_context
trace = None


@asynccontextmanager
async def lifespan(application):
    global trace
    async with original_lifespan(application):
        client = main._overview_history_client
        trace = QueryTrace(client._transport)
        client._transport = trace

        async def event_loop():
            while True:
                began = time.monotonic()
                await asyncio.sleep(1)
                with lock:
                    timings["event_loop_delay_ms"].append(
                        max(0, time.monotonic() - began - 1) * 1000
                    )

        task = asyncio.create_task(event_loop())
        try:
            yield
        finally:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app.router.lifespan_context = lifespan


@app.post("/api/_acceptance/arm-profile")
def arm_profile():
    armed_profiles.update(("tick", "metrics"))
    return {"diagnostic_only": True}


@app.get("/api/_acceptance/performance")
def snapshot():
    with lock:
        result = {
            "counts": dict(counts),
            "timings": {key: list(value) for key, value in timings.items()},
        }
        # Drain timing batches: bounded independent samples, no double counting.
        for values in timings.values():
            values.clear()
    result["queries"] = (
        {
            "count": trace.queries,
            "evaluation_points": trace.evaluation_points,
            "active": trace.active,
            "max_active": trace.max_active,
            "spans": dict(trace.spans),
        }
        if trace
        else {}
    )
    return result
