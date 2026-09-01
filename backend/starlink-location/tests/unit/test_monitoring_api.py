"""Route-level tests for typed monitoring endpoints."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from app.api import monitoring
from app.models.monitoring import (
    GroundEntryPointResponse,
    MonitoringHistoryResponse,
    MonitoringSample,
    MonitoringSeries,
)
from app.services.prometheus_client import (
    MonitoringPrometheusClient,
    MonitoringPrometheusError,
    MonitoringRateLimitError,
    MonitoringUnavailableError,
)
from fastapi.testclient import TestClient
from main import app
from starlette.responses import Response

UTC_NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


class FakeMonitoringClient:
    def __init__(self, response: MonitoringHistoryResponse | None = None) -> None:
        self.response = response or _history_response(1800, 1)
        self.calls: list[dict[str, Any]] = []
        self.release = asyncio.Event()

    async def get_history(self, **kwargs: Any) -> MonitoringHistoryResponse:
        self.calls.append(kwargs)
        await self.release.wait()
        return self.response


def _history_response(
    range_seconds: int, step_seconds: int
) -> MonitoringHistoryResponse:
    return MonitoringHistoryResponse(
        generated_at=UTC_NOW,
        window_start=UTC_NOW - timedelta(seconds=range_seconds),
        window_end=UTC_NOW,
        range_seconds=range_seconds,
        step_seconds=step_seconds,
        series=[
            MonitoringSeries(
                metric=metric,
                samples=[
                    MonitoringSample(
                        timestamp=UTC_NOW - timedelta(seconds=step_seconds),
                        value=1.0,
                    )
                ],
            )
            for metric in MonitoringHistoryResponse.metric_order()
        ],
    )


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def override_monitoring_client(fake: Any) -> None:
    app.dependency_overrides[monitoring.get_monitoring_client] = lambda: fake


def _prometheus_matrix_response(expr: str) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"__name__": expr},
                    "values": [[1788004799.0, "1"]],
                }
            ],
        },
    }


def test_history_defaults_success_headers_body_and_safe_upstream_controls(
    client: TestClient,
) -> None:
    fake = FakeMonitoringClient(_history_response(1800, 1))
    fake.release.set()
    override_monitoring_client(fake)

    response = client.get(
        "/api/monitoring/history",
        params={
            "query": "up",
            "url": "http://evil",
            "headers": "secret",
            "credentials": "secret",
        },
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "generated_at": "2026-08-29T12:00:00Z",
        "window_start": "2026-08-29T11:30:00Z",
        "window_end": "2026-08-29T12:00:00Z",
        "range_seconds": 1800,
        "step_seconds": 1,
        "series": [
            {
                "metric": metric,
                "samples": [
                    {
                        "timestamp": "2026-08-29T11:59:59Z",
                        "value": 1.0,
                    }
                ],
            }
            for metric in MonitoringHistoryResponse.metric_order()
        ],
    }
    assert fake.calls == [
        {
            "range_seconds": 1800,
            "step_seconds": 1,
            "client_id": "monitoring-history",
            "cancel_callback": fake.calls[0]["cancel_callback"],
        }
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"range_seconds": 60, "step_seconds": 1},
        {"range_seconds": 3600, "step_seconds": 60},
    ],
)
def test_history_accepts_bounds(client: TestClient, params: dict[str, int]) -> None:
    fake = FakeMonitoringClient(
        _history_response(params["range_seconds"], params["step_seconds"])
    )
    fake.release.set()
    override_monitoring_client(fake)

    response = client.get("/api/monitoring/history", params=params)

    assert response.status_code == 200
    assert response.json()["range_seconds"] == params["range_seconds"]
    assert response.json()["step_seconds"] == params["step_seconds"]


@pytest.mark.parametrize(
    "params",
    [
        {"range_seconds": 59},
        {"range_seconds": 3601},
        {"step_seconds": 0},
        {"step_seconds": 61},
    ],
)
def test_history_rejects_bounds_with_422(
    client: TestClient, params: dict[str, int]
) -> None:
    fake = FakeMonitoringClient()
    fake.release.set()
    override_monitoring_client(fake)

    response = client.get("/api/monitoring/history", params=params)

    assert response.status_code == 422
    assert fake.calls == []


def test_history_empty_series_are_returned(client: TestClient) -> None:
    fake = FakeMonitoringClient(
        MonitoringHistoryResponse(
            generated_at=UTC_NOW,
            window_start=UTC_NOW - timedelta(seconds=60),
            window_end=UTC_NOW,
            range_seconds=60,
            step_seconds=10,
            series=[
                MonitoringSeries(metric=metric, samples=[])
                for metric in MonitoringHistoryResponse.metric_order()
            ],
        )
    )
    fake.release.set()
    override_monitoring_client(fake)

    response = client.get(
        "/api/monitoring/history",
        params={"range_seconds": 60, "step_seconds": 10},
    )

    assert response.status_code == 200
    assert all(series["samples"] == [] for series in response.json()["series"])


@pytest.mark.parametrize(
    ("error", "status_code", "detail", "headers"),
    [
        (
            MonitoringPrometheusError("malformed_json", "secret http://prometheus"),
            502,
            {"code": "monitoring_upstream_error"},
            {},
        ),
        (
            MonitoringPrometheusError("upstream_timeout", "secret body"),
            504,
            {"code": "monitoring_upstream_timeout"},
            {},
        ),
        (
            MonitoringRateLimitError(7),
            429,
            {"code": "monitoring_rate_limited"},
            {"retry-after": "7"},
        ),
        (
            MonitoringUnavailableError(),
            503,
            {"code": "monitoring_capacity_unavailable"},
            {},
        ),
    ],
)
def test_history_maps_safe_errors_without_leaking_details(
    client: TestClient,
    error: Exception,
    status_code: int,
    detail: dict[str, str],
    headers: dict[str, str],
) -> None:
    class FailingClient:
        async def get_history(self, **kwargs: Any) -> MonitoringHistoryResponse:
            raise error

    override_monitoring_client(FailingClient())

    response = client.get("/api/monitoring/history")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    for key, value in headers.items():
        assert response.headers[key] == value
    assert "prometheus" not in response.text
    assert "secret" not in response.text


@pytest.mark.asyncio
async def test_history_total_deadline_returns_structured_json_504() -> None:
    class TrickleStream(httpx.AsyncByteStream):
        async def __aiter__(self) -> AsyncIterator[bytes]:
            for _ in range(20):
                await asyncio.sleep(0.01)
                yield b" "

        async def aclose(self) -> None:
            return None

    async def upstream_handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, stream=TrickleStream())

    prometheus = MonitoringPrometheusClient(
        base_url="http://prometheus:9090",
        timeout_seconds=1,
        total_history_timeout_seconds=0.04,
        transport=httpx.MockTransport(upstream_handler),
        clock=lambda: UTC_NOW,
    )
    app.dependency_overrides[monitoring.get_monitoring_client] = lambda: prometheus
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as route_client:
            response = await route_client.get("/api/monitoring/history")
        assert response.status_code == 504
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": {"code": "monitoring_upstream_timeout"}}
    finally:
        app.dependency_overrides.clear()
        await prometheus.aclose()


@pytest.mark.asyncio
async def test_history_stalled_cleanup_still_returns_structured_json_504_promptly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    prometheus = MonitoringPrometheusClient(
        base_url="http://prometheus:9090",
        total_history_timeout_seconds=0.04,
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, content=b"unused")
        ),
        clock=lambda: UTC_NOW,
    )

    async def cancellation_resistant_series(*_args: Any) -> Any:
        await prometheus._acquire_upstream_slot()
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            await release.wait()
            raise
        finally:
            prometheus._upstream_gate.release()

    monkeypatch.setattr(prometheus, "_fetch_series", cancellation_resistant_series)
    app.dependency_overrides[monitoring.get_monitoring_client] = lambda: prometheus
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as route_client:
            request = asyncio.create_task(route_client.get("/api/monitoring/history"))
            await asyncio.wait_for(started.wait(), timeout=1)
            response = await asyncio.wait_for(request, timeout=0.2)
        assert response.status_code == 504
        assert response.headers["content-type"].startswith("application/json")
        assert response.json() == {"detail": {"code": "monitoring_upstream_timeout"}}
    finally:
        release.set()
        app.dependency_overrides.clear()
        await asyncio.sleep(0)
        await prometheus.aclose()


@pytest.mark.asyncio
async def test_history_non_deadline_timeout_error_is_not_a_504() -> None:
    class FailingClient:
        async def get_history(self, **_kwargs: Any) -> MonitoringHistoryResponse:
            raise TimeoutError("not a monitoring deadline")

    app.dependency_overrides[monitoring.get_monitoring_client] = FailingClient
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as route_client:
            response = await route_client.get("/api/monitoring/history")
        assert response.status_code != 504
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_history_uses_request_disconnect_as_live_cancellation() -> None:
    class DisconnectedRequest:
        app = app

        async def is_disconnected(self) -> bool:
            return True

    class CancelAwareClient:
        async def get_history(self, **kwargs: Any) -> MonitoringHistoryResponse:
            assert await kwargs["cancel_callback"]() is True
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await monitoring.get_monitoring_history(
            request=DisconnectedRequest(),
            response=Response(),
            range_seconds=1800,
            step_seconds=1,
            prometheus=CancelAwareClient(),
        )


@pytest.mark.asyncio
async def test_history_route_preserves_client_single_flight_coalescing() -> None:
    fake = FakeMonitoringClient()
    first = asyncio.create_task(
        monitoring.get_monitoring_history(
            request=type("Request", (), {"is_disconnected": lambda self: False})(),
            response=Response(),
            range_seconds=1800,
            step_seconds=1,
            prometheus=fake,
        )
    )
    second = asyncio.create_task(
        monitoring.get_monitoring_history(
            request=type("Request", (), {"is_disconnected": lambda self: False})(),
            response=Response(),
            range_seconds=1800,
            step_seconds=1,
            prometheus=fake,
        )
    )
    await asyncio.sleep(0)
    assert len(fake.calls) == 2
    assert fake.calls[0]["range_seconds"] == fake.calls[1]["range_seconds"]
    fake.release.set()

    first_response, second_response = await asyncio.gather(first, second)
    assert first_response == second_response


@pytest.mark.asyncio
async def test_history_route_coalesces_real_prometheus_client_upstream_requests() -> (
    None
):
    upstream_seen: list[str] = []
    first_upstream_request = asyncio.Event()
    release_upstream = asyncio.Event()
    loop_errors: list[dict[str, Any]] = []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: loop_errors.append(context))

    async def upstream_handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        upstream_seen.append(expr)
        first_upstream_request.set()
        await release_upstream.wait()
        return httpx.Response(200, json=_prometheus_matrix_response(expr))

    prometheus = MonitoringPrometheusClient(
        base_url="http://prometheus:9090",
        transport=httpx.MockTransport(upstream_handler),
        clock=lambda: UTC_NOW,
    )
    app.dependency_overrides[monitoring.get_monitoring_client] = lambda: prometheus

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as route_client:
            first = asyncio.create_task(route_client.get("/api/monitoring/history"))
            await asyncio.wait_for(first_upstream_request.wait(), timeout=1)
            second = asyncio.create_task(route_client.get("/api/monitoring/history"))
            release_upstream.set()
            first_response, second_response = await asyncio.gather(first, second)

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.json() == second_response.json()
        assert len(upstream_seen) == 6
        assert sorted(upstream_seen) == sorted(
            [
                "starlink_dish_latitude_degrees",
                "starlink_dish_longitude_degrees",
                "starlink_network_latency_ms_current",
                "starlink_network_throughput_down_mbps_current",
                "starlink_network_throughput_up_mbps_current",
                "starlink_network_packet_loss_percent",
            ]
        )
        await asyncio.sleep(0)
        assert _monitoring_internal_pending_tasks() == []
        assert loop_errors == []
    finally:
        app.dependency_overrides.clear()
        await prometheus.aclose()
        loop.set_exception_handler(previous_handler)


@pytest.mark.asyncio
async def test_history_route_waiter_cancellation_does_not_cancel_shared_flight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream_seen: list[str] = []
    first_upstream_request = asyncio.Event()
    two_waiters = asyncio.Event()
    release_upstream = asyncio.Event()
    loop_errors: list[dict[str, Any]] = []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: loop_errors.append(context))

    async def upstream_handler(request: httpx.Request) -> httpx.Response:
        expr = request.url.params["query"]
        upstream_seen.append(expr)
        first_upstream_request.set()
        await release_upstream.wait()
        return httpx.Response(200, json=_prometheus_matrix_response(expr))

    prometheus = MonitoringPrometheusClient(
        base_url="http://prometheus:9090",
        transport=httpx.MockTransport(upstream_handler),
        clock=lambda: UTC_NOW,
    )
    original_join = prometheus._join_or_start_flight

    async def observed_join(*args: Any, **kwargs: Any) -> Any:
        flight = await original_join(*args, **kwargs)
        if flight.waiters == 2:
            two_waiters.set()
        return flight

    monkeypatch.setattr(prometheus, "_join_or_start_flight", observed_join)
    app.dependency_overrides[monitoring.get_monitoring_client] = lambda: prometheus

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as route_client:
            survivor = asyncio.create_task(route_client.get("/api/monitoring/history"))
            await asyncio.wait_for(first_upstream_request.wait(), timeout=1)
            cancelled = asyncio.create_task(route_client.get("/api/monitoring/history"))
            await asyncio.wait_for(two_waiters.wait(), timeout=1)
            cancelled.cancel()
            release_upstream.set()

            survivor_response = await survivor
            with pytest.raises(asyncio.CancelledError):
                await cancelled

        assert survivor_response.status_code == 200
        assert len(upstream_seen) == 6
        await asyncio.sleep(0)
        assert _monitoring_internal_pending_tasks() == []
        assert loop_errors == []
    finally:
        app.dependency_overrides.clear()
        await prometheus.aclose()
        loop.set_exception_handler(previous_handler)


def test_ground_entry_point_returns_unavailable_without_discovery(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(monitoring, "get_cached_ground_entry_point", lambda: None)
    monkeypatch.setattr(monitoring, "_utc_now", lambda: UTC_NOW)

    response = client.get("/api/monitoring/ground-entry-point")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "observed_at": None,
        "generated_at": "2026-08-29T12:00:00Z",
        "display": None,
        "city": None,
        "region": None,
        "country": None,
        "latitude": None,
        "longitude": None,
    }


def test_ground_entry_point_returns_safe_available_body_without_ip_leakage(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    observed_at = datetime(2026, 8, 29, 11, 45, tzinfo=timezone.utc)
    entry = monitoring.GroundEntryPoint(
        ip="203.0.113.10",
        city="Omaha",
        region="Nebraska",
        country="US",
        latitude=41.2565,
        longitude=-95.9345,
        observed_at=observed_at,
    )
    monkeypatch.setattr(monitoring, "get_cached_ground_entry_point", lambda: entry)
    monkeypatch.setattr(monitoring, "_utc_now", lambda: UTC_NOW)

    response = client.get("/api/monitoring/ground-entry-point")

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "observed_at": "2026-08-29T11:45:00Z",
        "generated_at": "2026-08-29T12:00:00Z",
        "display": "Omaha, Nebraska",
        "city": "Omaha",
        "region": "Nebraska",
        "country": "US",
        "latitude": 41.2565,
        "longitude": -95.9345,
    }
    assert "203.0.113.10" not in response.text
    assert "ip" not in response.json()


def _monitoring_internal_pending_tasks() -> list[asyncio.Task[Any]]:
    current = asyncio.current_task()
    names = (
        "_fetch_history",
        "_fetch_series",
        "_acquire_upstream_slot",
        "_await_with_disconnect",
        "_watch_cancel_event",
        "_watch_cancel_callback",
        "_cleanup_flight",
    )
    return [
        task
        for task in asyncio.all_tasks()
        if task is not current
        and not task.done()
        and any(name in task.get_coro().__qualname__ for name in names)
    ]


def test_monitoring_openapi_uses_exact_response_models(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    history = schema["paths"]["/api/monitoring/history"]["get"]
    gep = schema["paths"]["/api/monitoring/ground-entry-point"]["get"]

    assert (
        history["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/MonitoringHistoryResponse"
    )
    assert (
        gep["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/GroundEntryPointResponse"
    )
    assert "ip" not in GroundEntryPointResponse.model_fields
