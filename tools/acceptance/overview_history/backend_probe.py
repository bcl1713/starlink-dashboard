"""Acceptance-only entrypoint; production image and public API stay unchanged."""

from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import main
from app.api import overview_history
from app.services.overview_history_prometheus import (
    OverviewHistoryBundleSingleFlight,
    query_overview_history_bundle,
)

from .trace import QueryTrace

app = main.app
original_lifespan = app.router.lifespan_context
trace: QueryTrace | None = None
read_count = 0


@asynccontextmanager
async def measured_lifespan(application):
    global trace
    async with original_lifespan(application):
        client = main._overview_history_client
        store = main._overview_history_settings_store
        if client is None or store is None:
            raise RuntimeError("Production history runtime did not initialize")
        trace = QueryTrace(
            client._transport, Path("/data/overview-history-queries.jsonl")
        )
        client._transport = trace
        reader = application.state.overview_history_reader
        full = OverviewHistoryBundleSingleFlight(
            lambda **kwargs: query_overview_history_bundle(client, **kwargs)
        )

        async def measured_read():
            global read_count
            began = time.perf_counter()
            read_count += 1
            try:
                if os.environ.get("OVERVIEW_PROFILE_MODE") == "full":
                    return await full.get(
                        end_timestamp_seconds=int(time.time()),
                        window_seconds=store.get_window_seconds(),
                    )
                return await reader.read()
            finally:
                await trace.write_record(
                    {
                        "kind": "backend_read",
                        "monotonic_seconds": time.monotonic(),
                        "elapsed_ms": (time.perf_counter() - began) * 1000,
                        "active_upstream": trace.active,
                    },
                    Path("/data/overview-history-reads.jsonl"),
                )

        overview_history.set_overview_history_reader(measured_read, reader.invalidate)
        yield


app.router.lifespan_context = measured_lifespan


@app.get("/api/_acceptance/history-profile")
async def profile_counters():
    reader = app.state.overview_history_reader
    public = reader._public
    return {
        "reads": read_count,
        "queries": trace.queries if trace else 0,
        "evaluation_points": trace.evaluation_points if trace else 0,
        "active_upstream": trace.active if trace else 0,
        "max_upstream_concurrency": trace.max_active if trace else 0,
        "query_spans": dict(trace.spans) if trace else {},
        "snapshot_end": public["end_timestamp_seconds"] if public else None,
        "snapshot_points": (
            sum(len(v) for v in public["series"].values())
            + sum(
                len(entry[s])
                for entry in public["rolling_5m"].values()
                for s in ("min", "avg", "max")
            )
            if public
            else 0
        ),
        "active_refresh": reader._flight is not None,
    }
