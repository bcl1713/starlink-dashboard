"""Prometheus query planning for bounded overview telemetry history."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import isfinite

import httpx

from app.services.overview_history_cache import OverviewHistoryReader  # noqa: F401

MAX_OVERVIEW_HISTORY_SAMPLES = 1801
MAX_OVERVIEW_HISTORY_INTERVALS = MAX_OVERVIEW_HISTORY_SAMPLES - 1
OVERVIEW_HISTORY_METRICS = (
    "starlink_dish_latitude_degrees",
    "starlink_dish_longitude_degrees",
    "starlink_dish_altitude_feet",
    "starlink_dish_speed_knots",
    "starlink_dish_heading_degrees",
    "starlink_network_latency_ms_current",
    "starlink_network_throughput_down_mbps_current",
    "starlink_network_throughput_up_mbps_current",
    "starlink_network_packet_loss_percent",
    "starlink_dish_obstruction_percent",
    "starlink_signal_quality_percent",
)
DEFAULT_OVERVIEW_HISTORY_PROMETHEUS_URL = "http://prometheus:9090"


def resolve_overview_history_prometheus_url() -> str:
    """Resolve the Prometheus base URL for overview history queries."""
    return os.getenv(
        "STARLINK_PROMETHEUS_URL",
        DEFAULT_OVERVIEW_HISTORY_PROMETHEUS_URL,
    )


class OverviewHistoryPrometheusResponseError(ValueError):
    """Raised when Prometheus does not return a successful history matrix."""


class OverviewHistoryBundleSingleFlight:
    """Share one in-flight bundle query for each identical query window."""

    def __init__(
        self,
        fetch_bundle: Callable[..., Awaitable[dict]],
    ) -> None:
        self._fetch_bundle = fetch_bundle
        self._flights: dict[tuple[int, int], asyncio.Future[dict]] = {}

    async def get(
        self,
        *,
        end_timestamp_seconds: int,
        window_seconds: int,
    ) -> dict:
        """Return the shared in-flight result for one bounded history window."""
        key = (end_timestamp_seconds, window_seconds)
        flight = self._flights.get(key)
        if flight is None:
            flight = asyncio.ensure_future(
                self._fetch_bundle(
                    end_timestamp_seconds=end_timestamp_seconds,
                    window_seconds=window_seconds,
                )
            )
            self._flights[key] = flight
            flight.add_done_callback(
                lambda completed: self._discard_completed_flight(key, completed)
            )
        return await asyncio.shield(flight)

    def _discard_completed_flight(
        self,
        key: tuple[int, int],
        completed: asyncio.Future[dict],
    ) -> None:
        """Remove only the completed flight that still owns its key."""
        if self._flights.get(key) is completed:
            del self._flights[key]


@dataclass(frozen=True)
class OverviewHistoryQueryPlan:
    """A bounded Prometheus range-query window for overview telemetry."""

    start_timestamp_seconds: int
    end_timestamp_seconds: int
    step_seconds: int
    metric_names: tuple[str, ...]


def plan_overview_history_query(
    *,
    end_timestamp_seconds: int,
    window_seconds: int,
) -> OverviewHistoryQueryPlan:
    """Plan a query with no more than 1,801 requested samples per series."""
    if window_seconds <= 0:
        raise ValueError("History window must be positive")
    step = max(
        1,
        (window_seconds + MAX_OVERVIEW_HISTORY_INTERVALS - 1)
        // MAX_OVERVIEW_HISTORY_INTERVALS,
    )
    end = end_timestamp_seconds // step * step
    start = end - window_seconds
    return OverviewHistoryQueryPlan(
        start_timestamp_seconds=((start + step - 1) // step) * step,
        end_timestamp_seconds=end,
        step_seconds=step,
        metric_names=OVERVIEW_HISTORY_METRICS,
    )


def build_overview_history_promql(plan: OverviewHistoryQueryPlan) -> str:
    """Build one PromQL name matcher for the planned overview metric bundle."""
    metric_names = "|".join(plan.metric_names)
    return f'{{__name__=~"{metric_names}"}}'


def build_overview_history_prometheus_params(
    plan: OverviewHistoryQueryPlan,
) -> dict[str, str]:
    """Build query_range parameters for one bounded overview telemetry request."""
    return {
        "query": build_overview_history_promql(plan),
        "start": str(plan.start_timestamp_seconds),
        "end": str(plan.end_timestamp_seconds),
        "step": str(plan.step_seconds),
    }


async def fetch_overview_history_from_prometheus(
    client: httpx.AsyncClient,
    plan: OverviewHistoryQueryPlan,
) -> dict:
    """Fetch the complete overview telemetry bundle in one range request."""
    response = await client.get(
        "/api/v1/query_range",
        params=build_overview_history_prometheus_params(plan),
    )
    response.raise_for_status()
    return response.json()


def project_overview_history_matrix(
    payload: dict, plan: OverviewHistoryQueryPlan | None = None
) -> dict[str, list[list[float]]]:
    """Project finite raw traces; omit metrics with multiple usable series."""
    if payload.get("status") != "success":
        error = str(payload.get("error", "unknown Prometheus error"))
        raise OverviewHistoryPrometheusResponseError(
            f"Prometheus history query failed: {error}"
        )
    data = payload.get("data")
    if (
        not isinstance(data, dict)
        or data.get("resultType") != "matrix"
        or not isinstance(data.get("result"), list)
    ):
        raise OverviewHistoryPrometheusResponseError(
            "Prometheus history query did not return a matrix"
        )
    projected: dict[str, list[list[float]]] = {}
    ambiguous: set[str] = set()
    for series in data["result"]:
        if not isinstance(series, dict) or not isinstance(series.get("metric"), dict):
            continue
        metric_name = series["metric"].get("__name__")
        if metric_name not in OVERVIEW_HISTORY_METRICS or metric_name in ambiguous:
            continue
        values = series.get("values")
        if not isinstance(values, list):
            continue
        samples_by_timestamp: dict[float, float] = {}
        for pair in values:
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                continue
            timestamp, value = pair
            try:
                numeric_timestamp = float(timestamp)
                numeric_value = float(value)
            except (TypeError, ValueError, OverflowError):
                continue
            if not isfinite(numeric_timestamp) or not isfinite(numeric_value):
                continue
            if plan is not None and not (
                plan.start_timestamp_seconds
                <= numeric_timestamp
                <= plan.end_timestamp_seconds
            ):
                continue
            samples_by_timestamp.setdefault(numeric_timestamp, numeric_value)
        if samples_by_timestamp:
            if metric_name in projected:
                del projected[metric_name]
                ambiguous.add(metric_name)
            else:
                newest = sorted(samples_by_timestamp)[-MAX_OVERVIEW_HISTORY_SAMPLES:]
                projected[metric_name] = [
                    [timestamp, samples_by_timestamp[timestamp]] for timestamp in newest
                ]
    return projected


async def query_overview_history_bundle(
    client: httpx.AsyncClient,
    *,
    end_timestamp_seconds: int,
    window_seconds: int,
    plan: OverviewHistoryQueryPlan | None = None,
    include_identity: bool = False,
    rollup_deadline: float | None = None,
) -> dict:
    """Query and project one bounded overview telemetry-history bundle."""
    plan = plan or plan_overview_history_query(
        end_timestamp_seconds=end_timestamp_seconds,
        window_seconds=window_seconds,
    )
    payload = await fetch_overview_history_from_prometheus(client, plan)
    raw = project_overview_history_matrix(payload, plan)
    # Imported here because the rollup projector shares this module's query plan.
    from app.services.overview_history_rollups import query_overview_history_rollups

    rollup_ambiguity: set[str] = set()
    rollups = await query_overview_history_rollups(
        client, plan, deadline=rollup_deadline, ambiguity=rollup_ambiguity
    )
    # Trailing statistics can remain finite after current telemetry disappears.
    # Require a finite raw point at the same evaluation step, without claiming
    # that query_range timestamps prove source-observation freshness.
    for metric, entry in rollups.items():
        observed_steps = {point[0] for point in raw.get(metric, [])}
        for statistic in ("min", "avg", "max"):
            entry[statistic] = [
                point for point in entry[statistic] if point[0] in observed_steps
            ]
    bundle = {
        "window_seconds": window_seconds,
        "start_timestamp_seconds": plan.end_timestamp_seconds - window_seconds,
        "end_timestamp_seconds": plan.end_timestamp_seconds,
        "step_seconds": plan.step_seconds,
        "series": raw,
        "rolling_5m": rollups,
    }

    if include_identity:
        from app.services.overview_history_identity import raw_source_identity

        bundle["_identity"] = raw_source_identity(payload, plan)
        bundle["_rollup_ambiguity"] = rollup_ambiguity
    return bundle
