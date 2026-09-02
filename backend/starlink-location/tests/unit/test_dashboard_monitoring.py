"""Contract tests for dashboard monitoring endpoints."""

from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api import monitoring, status
from app.services.monitoring_history import HistoryClient
from main import app

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def telemetry(**overrides: float) -> SimpleNamespace:
    values = {
        "latitude": 41.0,
        "longitude": -96.0,
        "altitude": 32000.0,
        "speed": 420.0,
        "heading": 90.0,
        "latency_ms": 32.0,
        "throughput_down_mbps": 110.0,
        "throughput_up_mbps": 18.0,
        "packet_loss_percent": 0.2,
        "obstruction_percent": 1.5,
        "signal_quality_percent": 98.0,
        "uptime_seconds": 60.0,
    } | overrides
    return SimpleNamespace(
        timestamp=NOW,
        position=SimpleNamespace(
            **{
                key: values[key]
                for key in ("latitude", "longitude", "altitude", "speed", "heading")
            }
        ),
        network=SimpleNamespace(
            **{
                key: values[key]
                for key in (
                    "latency_ms",
                    "throughput_down_mbps",
                    "throughput_up_mbps",
                    "packet_loss_percent",
                )
            }
        ),
        obstruction=SimpleNamespace(obstruction_percent=values["obstruction_percent"]),
        environmental=SimpleNamespace(
            signal_quality_percent=values["signal_quality_percent"],
            uptime_seconds=values["uptime_seconds"],
            temperature_celsius=None,
        ),
    )


class LiveCoordinator:
    def __init__(self, sample: SimpleNamespace) -> None:
        self.sample = sample

    def get_current_telemetry(self) -> SimpleNamespace:
        return self.sample


def test_status_is_typed_truthful_finite_and_cache_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = LiveCoordinator(telemetry())
    with TestClient(app) as client:
        monkeypatch.setattr(status, "_coordinator", coordinator)
        response = client.get("/api/status")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "live"
    assert body["observed_at"] == "2026-09-02T12:00:00Z"
    assert body["received_at"].endswith("Z")
    assert "ip" not in response.text.lower()


def test_status_rejects_nonfinite_data_without_leaking_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(app) as client:
        monkeypatch.setattr(
            status,
            "_coordinator",
            LiveCoordinator(telemetry(latency_ms=float("nan"))),
        )
        response = client.get("/api/status")

    assert response.status_code == 503
    assert response.json() == {"detail": {"code": "status_unavailable"}}
    assert "nan" not in response.text.lower()


@pytest.mark.asyncio
async def test_history_uses_only_fixed_queries_and_bounds_points() -> None:
    seen: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{"values": [[1756814399, "2.5"]]}],
                },
            },
        )

    client = HistoryClient(transport=httpx.MockTransport(handler), clock=lambda: NOW)
    result = await client.fetch(range_seconds=1800, step_seconds=1)

    assert [series.metric for series in result.series] == list(client.metric_order)
    assert len(seen) == 6
    assert all(request.url.host == "prometheus" for request in seen)
    assert all(len(series.samples) <= 1801 for series in result.series)


def test_history_route_rejects_arbitrary_upstream_parameters() -> None:
    class FakeHistory:
        async def fetch(self, **_: int):
            return await HistoryClient(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json={
                            "status": "success",
                            "data": {"resultType": "matrix", "result": []},
                        },
                    )
                ),
                clock=lambda: NOW,
            ).fetch(range_seconds=60, step_seconds=1)

    app.dependency_overrides[monitoring.get_history_client] = lambda: FakeHistory()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/api/monitoring/history?range_seconds=60&query=up&url=http://evil"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "evil" not in response.text


def test_ground_entry_point_never_exposes_public_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = SimpleNamespace(
        ip="203.0.113.8",
        label="Omaha, Nebraska",
        city="Omaha",
        region="Nebraska",
        country="US",
        latitude=41.25,
        longitude=-95.93,
        observed_at=NOW,
    )
    monkeypatch.setattr(monitoring, "get_cached_ground_entry_point", lambda: entry)

    with TestClient(app) as client:
        response = client.get("/api/monitoring/ground-entry-point")

    assert response.status_code == 200
    assert response.json()["display"] == "Omaha, Nebraska"
    assert "ip" not in response.json()
    assert "203.0.113.8" not in response.text
