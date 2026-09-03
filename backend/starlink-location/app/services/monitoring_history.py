"""Bounded Prometheus history adapter with server-owned queries."""

import asyncio
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.models.dashboard import (
    METRIC_ORDER,
    HistoryResponse,
    HistorySample,
    HistorySeries,
    MetricName,
)
from app.services.monitoring_history_parser import count_values_items

_PROMETHEUS_URL = "http://prometheus:9090/api/v1/query_range"
_MAX_BODY_BYTES = 2_000_000
_MAX_AGGREGATE_BYTES = 4_000_000
_MAX_POINTS = 1801
_MAX_AGGREGATE_POINTS = len(METRIC_ORDER) * _MAX_POINTS
_QUERIES: dict[MetricName, str] = {
    "latitude_degrees": "starlink_dish_latitude_degrees",
    "longitude_degrees": "starlink_dish_longitude_degrees",
    "latency_ms": "starlink_network_latency_ms_current",
    "throughput_down_mbps": "starlink_network_throughput_down_mbps_current",
    "throughput_up_mbps": "starlink_network_throughput_up_mbps_current",
    "packet_loss_percent": "starlink_network_packet_loss_percent",
}


class HistoryUnavailable(RuntimeError):
    """A safe history failure suitable for route-level translation."""


@dataclass
class _Budget:
    bytes: int = 0
    points: int = 0


class HistoryClient:
    """Fetch fixed monitoring series within aggregate request bounds."""

    metric_order = METRIC_ORDER

    def __init__(
        self,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._timeout = timeout_seconds

    async def fetch(self, range_seconds: int, step_seconds: int) -> HistoryResponse:
        if not 60 <= range_seconds <= 1800 or not 1 <= step_seconds <= 30:
            raise ValueError("history bounds are invalid")
        end = self._clock().astimezone(timezone.utc)
        start = end - timedelta(seconds=range_seconds)
        params = {
            "start": start.timestamp(),
            "end": end.timestamp(),
            "step": step_seconds,
        }
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=httpx.Timeout(self._timeout)
            ) as client:
                series = await asyncio.wait_for(
                    self._fetch_all(client, params), timeout=self._timeout
                )
        except asyncio.CancelledError:
            raise
        except (httpx.HTTPError, asyncio.TimeoutError, ValueError, TypeError) as exc:
            raise HistoryUnavailable("monitoring history unavailable") from exc
        return HistoryResponse(
            generated_at=end,
            window_start=start,
            window_end=end,
            range_seconds=range_seconds,
            step_seconds=step_seconds,
            series=series,
        )

    async def _fetch_all(
        self,
        client: httpx.AsyncClient,
        params: dict[str, float | int],
    ) -> list[HistorySeries]:
        series: list[HistorySeries] = []
        budget = _Budget()
        for metric, expression in _QUERIES.items():
            series.append(
                await self._fetch_series(client, metric, expression, params, budget)
            )
        return series

    async def _fetch_series(
        self,
        client: httpx.AsyncClient,
        metric: MetricName,
        expression: str,
        shared_params: dict[str, float | int],
        budget: _Budget,
    ) -> HistorySeries:
        body = bytearray()
        async with client.stream(
            "GET",
            _PROMETHEUS_URL,
            params={"query": expression, **shared_params},
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                next_series_bytes = len(body) + len(chunk)
                next_total_bytes = budget.bytes + len(chunk)
                if (
                    next_series_bytes > _MAX_BODY_BYTES
                    or next_total_bytes > _MAX_AGGREGATE_BYTES
                ):
                    raise ValueError("history response too large")
                body.extend(chunk)
                budget.bytes = next_total_bytes
        remaining = _MAX_AGGREGATE_POINTS - budget.points
        point_count = count_values_items(bytes(body), min(_MAX_POINTS, remaining))
        budget.points += point_count
        payload = json.loads(body)
        values = _matrix_values(payload)
        if len(values) != point_count:
            raise ValueError("history point count mismatch")
        samples = _validated_samples(values, shared_params)
        return HistorySeries(metric=metric, samples=samples)


def _validated_samples(
    values: list[Any], params: dict[str, float | int]
) -> list[HistorySample]:
    samples: list[HistorySample] = []
    previous: float | None = None
    start = float(params["start"])
    end = float(params["end"])
    for item in values:
        if not isinstance(item, list) or len(item) != 2:
            raise TypeError("invalid history sample")
        timestamp = float(item[0])
        value = float(item[1])
        if not math.isfinite(timestamp) or not math.isfinite(value):
            raise ValueError("nonfinite history sample")
        if timestamp < start or timestamp > end:
            raise ValueError("history sample outside requested window")
        if previous is not None and timestamp <= previous:
            raise ValueError("history samples must be strictly ascending")
        previous = timestamp
        samples.append(
            HistorySample(
                timestamp=datetime.fromtimestamp(timestamp, timezone.utc), value=value
            )
        )
    return samples


def _matrix_values(payload: Any) -> list[Any]:
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ValueError("invalid history response")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "matrix":
        raise ValueError("invalid history result")
    result = data.get("result")
    if not isinstance(result, list) or len(result) != 1:
        raise ValueError("history result must contain exactly one series")
    first = result[0]
    values = first.get("values") if isinstance(first, dict) else None
    if not isinstance(values, list):
        raise TypeError("invalid history samples")
    return values
