"""Profile history orchestration using real Prometheus and identical endpoints.

Historical endpoint replay is a diagnostic computation control, not a wall-clock
browser soak. The CLI writes cProfile separately from unprofiled timing results.
"""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import json
import platform
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "backend/starlink-location")
)

from acceptance.overview_history.report import quantiles
from acceptance.overview_history.trace import QueryTrace
from app.services.overview_history_cache import OverviewHistoryReader
from app.services.overview_history_prometheus import (
    OverviewHistoryBundleSingleFlight,
    plan_overview_history_query,
    query_overview_history_bundle,
)


async def measure(
    *,
    window: int,
    cadence: int,
    mode: str,
    samples: int,
    end: int,
    prometheus_url: str = "http://127.0.0.1:19224",
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict:
    """Measure completed-result reuse separately from each fresh update."""
    if (
        window <= 0
        or cadence not in (1, 5)
        or mode not in ("full", "incremental")
        or samples <= 0
    ):
        raise ValueError(
            "Positive window/samples, cadence 1/5 and full/incremental mode required"
        )
    now = end
    trace = QueryTrace(transport or httpx.AsyncHTTPTransport())
    result = {"status": "passed", "errors": []}
    timings, encoding, duplicate_queries = [], [], []
    bundle = None
    async with httpx.AsyncClient(
        base_url=prometheus_url, transport=trace, timeout=5, trust_env=False
    ) as client:
        reader = OverviewHistoryReader(
            client, get_window_seconds=lambda: window, time_source=lambda: now
        )
        full = OverviewHistoryBundleSingleFlight(
            lambda **kwargs: query_overview_history_bundle(client, **kwargs)
        )

        async def read():
            if mode == "incremental":
                return await reader.read()
            return await full.get(end_timestamp_seconds=now, window_seconds=window)

        cold_ms = None
        began_cpu = time.process_time()
        cold_queries = cold_points = 0
        warm_queries = warm_points = 0
        try:
            began = time.perf_counter()
            bundle = await read()
            cold_ms = (time.perf_counter() - began) * 1000
            cold_queries, cold_points = trace.queries, trace.evaluation_points
            trace.reset_spans()
            for _ in range(samples):
                now += cadence
                began = time.perf_counter()
                bundle = await read()
                timings.append((time.perf_counter() - began) * 1000)
                before = trace.queries
                await read()
                duplicate_queries.append(trace.queries - before)
                began = time.perf_counter()
                json.dumps(bundle, separators=(",", ":"), allow_nan=False)
                encoding.append((time.perf_counter() - began) * 1000)
            # Separate from reported warm sequential-query totals.
            warm_queries = trace.queries - cold_queries
            warm_points = trace.evaluation_points - cold_points
            before = trace.queries
            await asyncio.gather(read(), read())
            concurrent_extra = trace.queries - before
        except (httpx.HTTPError, ValueError, TimeoutError) as error:
            result["status"] = "failed"
            result["errors"].append(type(error).__name__ + ": " + str(error))
            concurrent_extra = 0
        finally:
            await reader.aclose()
        result.update(
            {
                "window_seconds": window,
                "cadence_seconds": cadence,
                "mode": mode,
                "samples": samples,
                "step_seconds": plan_overview_history_query(
                    end_timestamp_seconds=end, window_seconds=window
                ).step_seconds,
                "cold_ms": cold_ms,
                "cold_queries": cold_queries,
                "cold_evaluation_points": cold_points,
                "warm_ms": quantiles(timings),
                "json_serialize_ms": quantiles(encoding),
                "warm_queries": warm_queries,
                "warm_evaluation_points": warm_points,
                "query_span_max_seconds": max(trace.spans) if trace.spans else None,
                "query_spans": dict(trace.spans),
                "second_reader_queries_max": (
                    max(duplicate_queries) if duplicate_queries else None
                ),
                "concurrent_reader_queries": concurrent_extra,
                "max_upstream_concurrency": trace.max_active,
                "upstream_active_at_end": trace.active,
                "diagnostic_cpu_seconds": time.process_time() - began_cpu,
                "returned_points": (
                    sum(len(points) for points in bundle["series"].values())
                    + sum(
                        len(entry[s])
                        for entry in bundle["rolling_5m"].values()
                        for s in ("min", "avg", "max")
                    )
                    if bundle
                    else 0
                ),
            }
        )
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prometheus-url", required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--window", type=int, required=True)
    parser.add_argument("--cadence", type=int, choices=(1, 5), required=True)
    parser.add_argument("--mode", choices=("full", "incremental"), required=True)
    parser.add_argument("--samples", type=int, default=60)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    options = {
        "window": args.window,
        "cadence": args.cadence,
        "mode": args.mode,
        "samples": args.samples,
        "end": args.end,
        "prometheus_url": args.prometheus_url,
    }
    result = await measure(**options)
    git = await asyncio.create_subprocess_exec(
        "git", "rev-parse", "HEAD", stdout=asyncio.subprocess.PIPE
    )
    git_output, _ = await git.communicate()
    if git.returncode:
        raise RuntimeError("Cannot resolve candidate SHA")
    result.update(
        sha=git_output.decode().strip(),
        platform=platform.platform(),
        limitations="Real historical endpoint replay; no HTTP API/browser/soak. Timings unprofiled; cProfile collected in a separate repeated replay.",
    )
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    if result["status"] == "passed":
        profiler = cProfile.Profile()
        profiler.enable()
        await measure(**options)
        profiler.disable()
        profiler.dump_stats(str(args.output) + ".prof")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "cold_ms",
                    "warm_ms",
                    "warm_queries",
                    "warm_evaluation_points",
                    "query_span_max_seconds",
                )
            }
        ),
        flush=True,
    )
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
