"""Bounded Prometheus history adapter with server-owned queries."""

import asyncio
import math
from collections.abc import Callable
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

_PROMETHEUS_URL = "http://prometheus:9090/api/v1/query_range"
_MAX_BODY_BYTES = 2_000_000
_MAX_POINTS = 1801
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
        timeout = httpx.Timeout(self._timeout)
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=timeout
            ) as client:
                series = await asyncio.wait_for(
                    asyncio.gather(
                        *(
                            self._fetch_series(client, metric, expression, params)
                            for metric, expression in _QUERIES.items()
                        )
                    ),
                    timeout=self._timeout,
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

    async def _fetch_series(
        self,
        client: httpx.AsyncClient,
        metric: MetricName,
        expression: str,
        shared_params: dict[str, float | int],
    ) -> HistorySeries:
        response = await client.get(
            _PROMETHEUS_URL,
            params={"query": expression, **shared_params},
        )
        response.raise_for_status()
        if len(response.content) > _MAX_BODY_BYTES:
            raise ValueError("history response too large")
        payload = response.json()
        values = _matrix_values(payload)
        samples: list[HistorySample] = []
        for raw_timestamp, raw_value in values[-_MAX_POINTS:]:
            timestamp = float(raw_timestamp)
            value = float(raw_value)
            if not math.isfinite(timestamp) or not math.isfinite(value):
                continue
            samples.append(
                HistorySample(
                    timestamp=datetime.fromtimestamp(timestamp, timezone.utc),
                    value=value,
                )
            )
        return HistorySeries(metric=metric, samples=samples)


def _matrix_values(payload: Any) -> list[list[Any]]:
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ValueError("invalid history response")
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("resultType") != "matrix":
        raise ValueError("invalid history result")
    result = data.get("result")
    if not isinstance(result, list):
        raise TypeError("invalid history result")
    if not result:
        return []
    first = result[0]
    values = first.get("values") if isinstance(first, dict) else None
    if not isinstance(values, list):
        raise TypeError("invalid history samples")
    return [item for item in values if isinstance(item, list) and len(item) == 2]
