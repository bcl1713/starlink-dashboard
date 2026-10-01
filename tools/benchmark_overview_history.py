"""Measure cache orchestration with deterministic matrices, not real Prometheus CPU.

Run with the backend's httpx environment. --samples counts simulated polling
intervals; this is not a wall-clock resource soak or production acceptance.
"""

import argparse
import asyncio
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "backend/starlink-location")
)

from app.services.overview_history_cache import OverviewHistoryReader
from app.services.overview_history_prometheus import (
    OVERVIEW_HISTORY_METRICS,
    OverviewHistoryQueryPlan,
    query_overview_history_bundle,
)
from app.services.overview_history_rollups import ROLLUP_METRICS


def percentiles(values: list[float]) -> dict:
    """Report nearest-rank milliseconds, including p50, p95 and p99."""
    ordered = sorted(values)
    return {
        f"p{p}": ordered[min(len(ordered) - 1, (len(ordered) * p + 99) // 100 - 1)]
        for p in (50, 95, 99)
    }


async def measure(window: int, cadence: int, incremental: bool, samples: int) -> dict:
    """Compare one and two sequential readers, including completed-result reuse."""
    now = 1_782_000_000
    queries = 0
    evaluation_points = 0
    spans = []

    def handler(request):
        nonlocal queries, evaluation_points
        params = request.url.params
        start, end, step = (int(params[key]) for key in ("start", "end", "step"))
        metrics = (
            OVERVIEW_HISTORY_METRICS
            if params["query"].startswith("{")
            else [metric for metric in ROLLUP_METRICS if metric in params["query"]]
        )
        queries += 1
        evaluation_points += ((end - start) // step + 1) * len(metrics)
        spans.append(end - start)
        result = [
            {
                "metric": {"__name__": metric, "instance": "fixture"},
                "values": [[t, str(t % 73)] for t in range(start, end + 1, step)],
            }
            for metric in metrics
        ]
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"resultType": "matrix", "result": result},
            },
        )

    async with httpx.AsyncClient(
        base_url="http://prometheus", transport=httpx.MockTransport(handler)
    ) as client:
        reader = OverviewHistoryReader(
            client, get_window_seconds=lambda: window, time_source=lambda: now
        )

        async def read():
            if incremental:
                return await reader.read()
            return await query_overview_history_bundle(
                client,
                end_timestamp_seconds=now,
                window_seconds=window,
                plan=OverviewHistoryQueryPlan(
                    start_timestamp_seconds=now - window,
                    end_timestamp_seconds=now,
                    step_seconds=max(1, (window + 1799) // 1800),
                    metric_names=OVERVIEW_HISTORY_METRICS,
                ),
            )

        began = time.perf_counter()
        bundle = await read()
        cold_ms = (time.perf_counter() - began) * 1000
        cold_points = evaluation_points
        spans.clear()
        timings, serialization, parsing, counts = [], [], [], []
        before_queries = queries
        before_points = evaluation_points
        began_cpu = time.process_time()
        began_elapsed = time.perf_counter()
        for _ in range(samples):
            now += cadence
            began = time.perf_counter()
            bundle = await read()
            timings.append((time.perf_counter() - began) * 1000)
            before_second = queries
            await read()
            counts.append(queries - before_second)
            began = time.perf_counter()
            encoded = json.dumps(bundle, separators=(",", ":"))
            serialization.append((time.perf_counter() - began) * 1000)
            began = time.perf_counter()
            json.loads(encoded)
            parsing.append((time.perf_counter() - began) * 1000)
        cpu_seconds = time.process_time() - began_cpu
        elapsed_seconds = time.perf_counter() - began_elapsed
        assert reader._flight is None
        points = sum(len(trace) for trace in bundle["series"].values()) + sum(
            len(entry[statistic])
            for entry in bundle["rolling_5m"].values()
            for statistic in ("min", "avg", "max")
        )
        await reader.aclose()
    return {
        "window_seconds": window,
        "cadence_seconds": cadence,
        "incremental": incremental,
        "simulated_duration_seconds": samples * cadence,
        "samples": samples,
        "cold_ms": cold_ms,
        "cold_evaluation_points": cold_points,
        "warm_ms": percentiles(timings),
        "json_serialize_ms": percentiles(serialization),
        "python_json_parse_ms": percentiles(parsing),
        "response_bytes": len(encoded),
        "warm_queries_two_readers": queries - before_queries,
        "warm_evaluation_points_two_readers": evaluation_points - before_points,
        "query_span_median_seconds": statistics.median(spans),
        "query_span_max_seconds": max(spans),
        "second_reader_queries_max": max(counts),
        "retained_points": points,
        "fixture_cpu_seconds": cpu_seconds,
        "actual_elapsed_seconds": elapsed_seconds,
    }


async def main() -> None:
    """Write reproducible bounded fixture measurements with explicit limitations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    results = []
    for window in (300, 900, 1800, 3600, 3601):
        for cadence, incremental in ((5, False), (5, True), (1, True)):
            result = await measure(window, cadence, incremental, args.samples)
            results.append(result)
            print(
                f"window={window} cadence={cadence} incremental={incremental} p95={result['warm_ms']['p95']:.1f}ms",
                flush=True,
            )
    report = {
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        ),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "limitations": "MockTransport matrices: includes fixture generation; no real Prometheus, HTTP server, browser, GPU, production CPU/RSS or wall-clock 60-minute soak. Baseline uses original full-window moving grid. Cold excluded from warm distributions; periodic rehydrations included. Two sequential readers per interval; sample counts are equal, simulated durations differ with cadence.",
        "results": results,
    }
    args.output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    asyncio.run(main())
