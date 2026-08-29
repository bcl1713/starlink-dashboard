"""Allow-listed Prometheus history client for monitoring metrics."""

from __future__ import annotations

import asyncio
import json
import math
import os
import time
import weakref
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import ClassVar, TypeVar

import httpx
from app.models.monitoring import (
    MonitoringHistoryRequest,
    MonitoringHistoryResponse,
    MonitoringMetric,
    MonitoringSample,
    MonitoringSeries,
)
from pydantic import ValidationError

T = TypeVar("T")

PROMETHEUS_EXPRESSIONS: tuple[tuple[MonitoringMetric, str], ...] = (
    ("latitude_degrees", "starlink_dish_latitude_degrees"),
    ("longitude_degrees", "starlink_dish_longitude_degrees"),
    ("latency_ms", "starlink_network_latency_ms_current"),
    ("throughput_down_mbps", "starlink_network_throughput_down_mbps_current"),
    ("throughput_up_mbps", "starlink_network_throughput_up_mbps_current"),
    ("packet_loss_percent", "starlink_network_packet_loss_percent"),
)


class MonitoringPrometheusError(Exception):
    """Safe monitoring client error suitable for API mapping."""

    def __init__(self, code: str, message: str = "monitoring upstream unavailable"):
        super().__init__(message)
        self.code = code


class MonitoringRateLimitError(MonitoringPrometheusError):
    """Raised when a server-owned client identity exceeds its request budget."""

    def __init__(self, retry_after_seconds: int):
        super().__init__("rate_limited", "monitoring rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class MonitoringUnavailableError(MonitoringPrometheusError):
    """Raised when upstream admission is full."""

    def __init__(self) -> None:
        super().__init__("unavailable", "monitoring upstream capacity unavailable")


@dataclass
class _Flight:
    task: asyncio.Task[MonitoringHistoryResponse]
    waiters: int = 0


@dataclass
class _PointBudget:
    remaining: int

    def reserve(self, count: int) -> None:
        if count > self.remaining:
            raise MonitoringPrometheusError("too_many_points")
        self.remaining -= count


class MonitoringPrometheusClient:
    """Prometheus history client with fixed queries and bounded load.

    The public history method accepts only server-owned request parameters:
    history bounds, opaque client identity, and an optional server-owned
    cancellation event/callback. Client identity is used only for the local
    rolling rate limit and never affects upstream URL, headers, or query text.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        byte_limit: int = 256_000,
        timeout_seconds: float = 5.0,
        admission_timeout_seconds: float = 0.25,
        rate_limit_count: int = 12,
        rate_limit_window_seconds: int = 60,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._base_url = self._normalize_base_url(
            base_url or os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
        )
        self._byte_limit = byte_limit
        self._timeout = httpx.Timeout(timeout_seconds)
        self._admission_timeout_seconds = admission_timeout_seconds
        self._rate_limit_count = rate_limit_count
        self._rate_limit_window_seconds = rate_limit_window_seconds
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=transport,
        )
        self._rate_lock = asyncio.Lock()
        self._flight_lock = asyncio.Lock()
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._flights: dict[tuple[int, int, int], _Flight] = {}
        self._cancel_poll_seconds = 0.01

    _upstream_limiters: ClassVar[
        weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]
    ] = weakref.WeakKeyDictionary()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get_history(
        self,
        *,
        range_seconds: int,
        step_seconds: int,
        client_id: str,
        cancel_event: asyncio.Event | None = None,
        cancel_callback: Callable[[], bool | Awaitable[bool]] | None = None,
    ) -> MonitoringHistoryResponse:
        try:
            request = MonitoringHistoryRequest(
                range_seconds=range_seconds,
                step_seconds=step_seconds,
            )
        except ValidationError as exc:
            raise MonitoringPrometheusError(
                "bad_request",
                "invalid monitoring history bounds",
            ) from exc
        self._check_cancel(cancel_event)
        await self._check_cancel_callback(cancel_callback)
        await self._await_with_disconnect(
            self._enforce_rate_limit(client_id),
            cancel_event,
            cancel_callback,
        )
        end = self._utc_now()
        key = (
            request.range_seconds,
            request.step_seconds,
            int(end.timestamp()) // 10,
        )
        flight = await self._join_or_start_flight(key, request, end)
        try:
            self._check_cancel(cancel_event)
            await self._check_cancel_callback(cancel_callback)
            return await self._await_with_disconnect(
                asyncio.shield(flight.task),
                cancel_event,
                cancel_callback,
                cancel_operation=False,
            )
        finally:
            await self._release_waiter(key, flight)

    async def _join_or_start_flight(
        self,
        key: tuple[int, int, int],
        request: MonitoringHistoryRequest,
        end: datetime,
    ) -> _Flight:
        async with self._flight_lock:
            flight = self._flights.get(key)
            if flight is not None and flight.task.done():
                self._retrieve_task_exception(flight.task)
                self._flights.pop(key, None)
                flight = None
            if flight is None:
                task = asyncio.create_task(self._fetch_history(request, end))
                flight = _Flight(task=task)
                self._flights[key] = flight
                task.add_done_callback(
                    lambda task, flight_key=key, current_flight=flight: (
                        asyncio.create_task(
                            self._cleanup_flight(flight_key, current_flight, task)
                        )
                    )
                )
            flight.waiters += 1
            return flight

    async def _cleanup_flight(
        self,
        key: tuple[int, int, int],
        flight: _Flight,
        task: asyncio.Task[MonitoringHistoryResponse],
    ) -> None:
        async with self._flight_lock:
            current = self._flights.get(key)
            if current is flight and current.task is task and task.done():
                self._flights.pop(key, None)

    async def _release_waiter(self, key: tuple[int, int, int], flight: _Flight) -> None:
        async with self._flight_lock:
            current = self._flights.get(key)
            if current is not flight:
                return
            flight.waiters -= 1
            if flight.waiters <= 0 and not flight.task.done():
                flight.task.cancel()
                self._flights.pop(key, None)
            elif flight.waiters <= 0 and flight.task.done():
                self._retrieve_task_exception(flight.task)
                self._flights.pop(key, None)

    async def _fetch_history(
        self,
        request: MonitoringHistoryRequest,
        end: datetime,
    ) -> MonitoringHistoryResponse:
        start = end - timedelta(seconds=request.range_seconds)
        max_points = len(PROMETHEUS_EXPRESSIONS) * (
            request.range_seconds // request.step_seconds + 1
        )
        point_budget = _PointBudget(max_points)
        tasks = [
            self._fetch_series(
                metric, expr, start, end, request.step_seconds, point_budget
            )
            for metric, expr in PROMETHEUS_EXPRESSIONS
        ]
        series = await asyncio.gather(*tasks)
        if sum(len(item.samples) for item in series) > max_points:
            raise MonitoringPrometheusError("too_many_points")
        return MonitoringHistoryResponse(
            generated_at=end,
            window_start=start,
            window_end=end,
            range_seconds=request.range_seconds,
            step_seconds=request.step_seconds,
            series=series,
        )

    async def _fetch_series(
        self,
        metric: MonitoringMetric,
        expr: str,
        start: datetime,
        end: datetime,
        step_seconds: int,
        point_budget: _PointBudget,
    ) -> MonitoringSeries:
        await self._acquire_upstream_slot()
        try:
            body = await self._query_range(expr, start, end, step_seconds)
        finally:
            self._upstream_limiter().release()
        decoded = self._decode_json(body)
        samples = self._parse_prometheus_response(decoded, expr, point_budget)
        return MonitoringSeries(metric=metric, samples=samples)

    async def _acquire_upstream_slot(self) -> None:
        try:
            await asyncio.wait_for(
                self._upstream_limiter().acquire(),
                timeout=self._admission_timeout_seconds,
            )
        except TimeoutError as exc:
            raise MonitoringUnavailableError() from exc

    def _upstream_limiter(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        limiter = self._upstream_limiters.get(loop)
        if limiter is None:
            limiter = asyncio.Semaphore(4)
            self._upstream_limiters[loop] = limiter
        return limiter

    async def _query_range(
        self,
        expr: str,
        start: datetime,
        end: datetime,
        step_seconds: int,
    ) -> bytes:
        params = {
            "query": expr,
            "start": str(start.timestamp()),
            "end": str(end.timestamp()),
            "step": str(step_seconds),
        }
        try:
            async with self._client.stream(
                "GET",
                "/api/v1/query_range",
                params=params,
            ) as response:
                if response.status_code != 200:
                    raise MonitoringPrometheusError("upstream_http_error")
                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > self._byte_limit:
                        raise MonitoringPrometheusError("response_too_large")
                    chunks.append(chunk)
                return b"".join(chunks)
        except asyncio.CancelledError:
            raise
        except httpx.TimeoutException as exc:
            raise MonitoringPrometheusError("upstream_timeout") from exc
        except httpx.HTTPError as exc:
            raise MonitoringPrometheusError("upstream_transport_error") from exc

    def _decode_json(self, body: bytes) -> object:
        try:
            return json.loads(body, parse_constant=self._reject_json_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MonitoringPrometheusError("malformed_json") from exc

    def _reject_json_constant(self, _value: str) -> object:
        raise MonitoringPrometheusError("malformed_json")

    def _parse_prometheus_response(
        self,
        payload: object,
        expr: str,
        point_budget: _PointBudget,
    ) -> list[MonitoringSample]:
        if not isinstance(payload, dict) or set(payload) != {"status", "data"}:
            raise MonitoringPrometheusError("bad_shape")
        if payload["status"] != "success":
            raise MonitoringPrometheusError("upstream_status_error")
        data = payload["data"]
        if not isinstance(data, dict) or set(data) != {"resultType", "result"}:
            raise MonitoringPrometheusError("bad_shape")
        if data["resultType"] != "matrix" or not isinstance(data["result"], list):
            raise MonitoringPrometheusError("bad_shape")
        result = data["result"]
        if len(result) > 1:
            raise MonitoringPrometheusError("multiple_series")
        if len(result) == 0:
            return []
        series = result[0]
        if not isinstance(series, dict) or set(series) != {"metric", "values"}:
            raise MonitoringPrometheusError("bad_shape")
        if not self._is_expected_metric_identity(series["metric"], expr):
            raise MonitoringPrometheusError("bad_identity")
        if not isinstance(series["values"], list):
            raise MonitoringPrometheusError("bad_shape")
        point_budget.reserve(len(series["values"]))

        samples: list[MonitoringSample] = []
        previous: float | None = None
        for point in series["values"]:
            if not isinstance(point, list) or len(point) != 2:
                raise MonitoringPrometheusError("bad_point")
            timestamp = self._parse_timestamp(point[0])
            current = timestamp.timestamp()
            if previous is not None and current <= previous:
                raise MonitoringPrometheusError("non_monotonic_points")
            previous = current
            samples.append(
                MonitoringSample(
                    timestamp=timestamp,
                    value=self._parse_value(point[1]),
                )
            )
        return samples

    def _is_expected_metric_identity(self, metric: object, expr: str) -> bool:
        if not isinstance(metric, Mapping):
            return False
        for name, value in metric.items():
            if not isinstance(name, str) or not isinstance(value, str):
                return False
        return metric.get("__name__") == expr

    def _parse_timestamp(self, value: object) -> datetime:
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise MonitoringPrometheusError("bad_point")
        try:
            timestamp = float(value)
            if not math.isfinite(timestamp):
                raise MonitoringPrometheusError("bad_point")
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except MonitoringPrometheusError:
            raise
        except (ValueError, OverflowError, OSError) as exc:
            raise MonitoringPrometheusError("bad_point") from exc

    def _parse_value(self, value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, int | float | str):
            raise MonitoringPrometheusError("bad_point")
        try:
            parsed = float(value)
        except ValueError as exc:
            raise MonitoringPrometheusError("bad_point") from exc
        if not math.isfinite(parsed):
            return None
        return parsed

    async def _enforce_rate_limit(self, client_id: str) -> None:
        now = time.monotonic()
        async with self._rate_lock:
            entries = self._requests[client_id]
            while entries and now - entries[0] >= self._rate_limit_window_seconds:
                entries.popleft()
            if len(entries) >= self._rate_limit_count:
                retry_after = max(
                    1, math.ceil(self._rate_limit_window_seconds - (now - entries[0]))
                )
                raise MonitoringRateLimitError(retry_after)
            entries.append(now)

    def _utc_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise MonitoringPrometheusError("bad_clock")
        return value.astimezone(timezone.utc)

    async def _await_with_disconnect(
        self,
        awaitable: Awaitable[T],
        cancel_event: asyncio.Event | None,
        cancel_callback: Callable[[], bool | Awaitable[bool]] | None,
        *,
        cancel_operation: bool = True,
    ) -> T:
        operation = asyncio.ensure_future(awaitable)
        watchers = self._cancel_watchers(cancel_event, cancel_callback)
        if not watchers:
            return await operation
        try:
            done, _pending = await asyncio.wait(
                [operation, *watchers],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if operation in done:
                return await operation
            for watcher in watchers:
                if watcher in done:
                    await watcher
            raise asyncio.CancelledError
        finally:
            for watcher in watchers:
                watcher.cancel()
            await asyncio.gather(*watchers, return_exceptions=True)
            if cancel_operation and not operation.done():
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)

    def _check_cancel(self, cancel_event: asyncio.Event | None) -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise asyncio.CancelledError

    async def _check_cancel_callback(
        self,
        cancel_callback: Callable[[], bool | Awaitable[bool]] | None,
    ) -> None:
        if cancel_callback is None:
            return
        result = cancel_callback()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            raise asyncio.CancelledError

    def _cancel_watchers(
        self,
        cancel_event: asyncio.Event | None,
        cancel_callback: Callable[[], bool | Awaitable[bool]] | None,
    ) -> list[asyncio.Task[None]]:
        watchers: list[asyncio.Task[None]] = []
        if cancel_event is not None:
            watchers.append(asyncio.create_task(self._watch_cancel_event(cancel_event)))
        if cancel_callback is not None:
            watchers.append(
                asyncio.create_task(self._watch_cancel_callback(cancel_callback))
            )
        return watchers

    async def _watch_cancel_event(self, cancel_event: asyncio.Event) -> None:
        await cancel_event.wait()

    async def _watch_cancel_callback(
        self,
        cancel_callback: Callable[[], bool | Awaitable[bool]],
    ) -> None:
        while True:
            await self._check_cancel_callback(cancel_callback)
            await asyncio.sleep(self._cancel_poll_seconds)

    def _retrieve_task_exception(
        self,
        task: asyncio.Task[MonitoringHistoryResponse],
    ) -> None:
        if task.cancelled():
            return
        try:
            task.exception()
        except asyncio.CancelledError:
            return

    def _normalize_base_url(self, value: str) -> str:
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host:
            raise ValueError("invalid prometheus base URL")
        return str(url)
