"""Prometheus query planning for bounded overview telemetry history."""

from dataclasses import dataclass
from math import ceil

import httpx

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
    return OverviewHistoryQueryPlan(
        start_timestamp_seconds=end_timestamp_seconds - window_seconds,
        end_timestamp_seconds=end_timestamp_seconds,
        step_seconds=max(1, ceil(window_seconds / MAX_OVERVIEW_HISTORY_INTERVALS)),
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
