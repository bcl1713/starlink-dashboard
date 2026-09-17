"""Prometheus query planning for bounded overview telemetry history."""

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from math import ceil, isfinite

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


class OverviewHistoryReader:
    """Read one shared bounded overview-history bundle from Prometheus."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        get_window_seconds: Callable[[], int],
        time_source: Callable[[], float],
    ) -> None:
        self._client = client
        self._get_window_seconds = get_window_seconds
        self._time_source = time_source
        self._single_flight = OverviewHistoryBundleSingleFlight(
            self._query_bundle,
        )

    async def read(self) -> dict:
        """Read the selected history window ending at the current whole second."""
        return await self._single_flight.get(
            end_timestamp_seconds=int(self._time_source()),
            window_seconds=self._get_window_seconds(),
        )

    async def _query_bundle(
        self,
        *,
        end_timestamp_seconds: int,
        window_seconds: int,
    ) -> dict:
        """Query one planned bundle through the lifecycle-managed client."""
        return await query_overview_history_bundle(
            self._client,
            end_timestamp_seconds=end_timestamp_seconds,
            window_seconds=window_seconds,
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


def project_overview_history_matrix(payload: dict) -> dict[str, list[list[float]]]:
    """Project approved finite Prometheus samples keyed by metric name."""
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
    for series in data["result"]:
        metric_name = series["metric"]["__name__"]
        if metric_name not in OVERVIEW_HISTORY_METRICS:
            continue
        samples = []
        for timestamp, value in series["values"]:
            try:
                numeric_timestamp = float(timestamp)
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if isfinite(numeric_timestamp) and isfinite(numeric_value):
                samples.append([numeric_timestamp, numeric_value])
        if samples:
            projected[metric_name] = samples
    return projected


async def query_overview_history_bundle(
    client: httpx.AsyncClient,
    *,
    end_timestamp_seconds: int,
    window_seconds: int,
) -> dict:
    """Query and project one bounded overview telemetry-history bundle."""
    plan = plan_overview_history_query(
        end_timestamp_seconds=end_timestamp_seconds,
        window_seconds=window_seconds,
    )
    payload = await fetch_overview_history_from_prometheus(client, plan)
    return {
        "window_seconds": window_seconds,
        "start_timestamp_seconds": plan.start_timestamp_seconds,
        "end_timestamp_seconds": plan.end_timestamp_seconds,
        "step_seconds": plan.step_seconds,
        "series": project_overview_history_matrix(payload),
    }
