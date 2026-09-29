"""Bounded trailing-five-minute Prometheus traces for Overview history."""

import asyncio
from math import isfinite

import httpx

from app.services.overview_history_prometheus import (
    MAX_OVERVIEW_HISTORY_SAMPLES,
    OverviewHistoryQueryPlan,
)

ROLLUP_METRICS = (
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
)
ROLLUP_FUNCTIONS = {
    "min": "min_over_time",
    "avg": "avg_over_time",
    "max": "max_over_time",
}


def rolling_promql(metric: str, statistic: str) -> str:
    """Build an allowlisted Prometheus five-minute trailing aggregate."""
    if metric not in ROLLUP_METRICS or statistic not in ROLLUP_FUNCTIONS:
        raise ValueError("Unsupported overview rollup")
    return f"{ROLLUP_FUNCTIONS[statistic]}({metric}[5m])"


def _project_rollup_matrix(
    payload: object, metric: str, plan: OverviewHistoryQueryPlan
) -> list[list[float]] | None:
    """Distinguish a valid empty trace from an invalid/ambiguous matrix."""
    if not isinstance(payload, dict) or payload.get("status") != "success":
        return None
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "matrix":
        return None
    series = data.get("result")
    if not isinstance(series, list) or len(series) > 1:
        return None
    if not series:
        return []
    entry = series[0]
    if not isinstance(entry, dict) or not isinstance(entry.get("metric"), dict):
        return None
    # PromQL functions generally strip __name__; if present, it must match.
    name = entry["metric"].get("__name__")
    if name is not None and name != metric:
        return None
    values = entry.get("values")
    if not isinstance(values, list):
        return None
    samples: list[list[float]] = []
    seen: set[float] = set()
    for pair in values:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        try:
            timestamp, value = float(pair[0]), float(pair[1])
        except (ValueError, TypeError, OverflowError):
            continue
        if (
            not isfinite(timestamp)
            or not isfinite(value)
            or not plan.start_timestamp_seconds
            <= timestamp
            <= plan.end_timestamp_seconds
            or timestamp in seen
        ):
            continue
        samples.append([timestamp, value])
        seen.add(timestamp)
        if len(samples) == MAX_OVERVIEW_HISTORY_SAMPLES:
            break
    return samples


async def query_overview_history_rollups(
    client: httpx.AsyncClient, plan: OverviewHistoryQueryPlan
) -> dict[str, dict]:
    """Query 15 traces with the shared window and at most three in flight."""
    semaphore = asyncio.Semaphore(3)
    result = {
        metric: {"state": "available", "min": [], "avg": [], "max": []}
        for metric in ROLLUP_METRICS
    }

    async def fetch(
        metric: str, statistic: str
    ) -> tuple[str, str, list[list[float]] | None]:
        async with semaphore:
            try:
                response = await client.get(
                    "/api/v1/query_range",
                    params={
                        "query": rolling_promql(metric, statistic),
                        "start": str(plan.start_timestamp_seconds),
                        "end": str(plan.end_timestamp_seconds),
                        "step": str(plan.step_seconds),
                    },
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError):
                return metric, statistic, None
        return metric, statistic, _project_rollup_matrix(payload, metric, plan)

    traces = await asyncio.gather(
        *(
            fetch(metric, statistic)
            for metric in ROLLUP_METRICS
            for statistic in ROLLUP_FUNCTIONS
        )
    )
    for metric, statistic, samples in traces:
        if samples is None:
            result[metric]["state"] = "unavailable"
        else:
            result[metric][statistic] = samples
    for entry in result.values():
        if entry["state"] == "unavailable":
            for statistic in ROLLUP_FUNCTIONS:
                entry[statistic] = []
    return result
