"""Tests for weather radar API routes."""

from __future__ import annotations

from dataclasses import dataclass
from tempfile import SpooledTemporaryFile

import pytest
from app.services.weather_radar import (
    InvalidRadarTileError,
    RadarTile,
    RainViewerRadarServiceError,
    RainViewerRadarTimeoutError,
)
from main import app


def _tile(body: bytes = b"\x89PNG\r\n\x1a\npayload") -> RadarTile:
    spool = SpooledTemporaryFile(max_size=1024)  # noqa: SIM115
    spool.write(body)
    spool.seek(0)
    return RadarTile(spool=spool, size_bytes=len(body), frame_timestamp=12345)


@dataclass
class FakeRainViewerService:
    result: RadarTile | BaseException
    disconnected_seen: bool = False

    async def fetch_tile(self, z, x, y, cancel_check):
        self.disconnected_seen = await cancel_check()
        if isinstance(self.result, BaseException):
            raise self.result
        return self.result


def _install_service(service: FakeRainViewerService) -> None:
    app.state.rainviewer_radar_service = service


def test_rainviewer_radar_tile_endpoint_returns_validated_png_bytes(client) -> None:
    service = FakeRainViewerService(_tile())
    _install_service(service)

    response = client.get(
        "/api/weather/radar/rainviewer/3/4/5.png?refresh=202606171200",
        follow_redirects=False,
    )

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\npayload"
    assert "location" not in response.headers
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "public, max-age=60"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-radar-frame-timestamp"] == "12345"
    assert service.disconnected_seen is False


def test_rainviewer_radar_tile_endpoint_maps_invalid_xyz_to_400(client) -> None:
    _install_service(FakeRainViewerService(InvalidRadarTileError()))

    response = client.get("/api/weather/radar/rainviewer/8/0/0.png")

    assert response.status_code == 400
    assert response.json() == {"detail": {"code": "invalid_radar_tile"}}


def test_rainviewer_radar_tile_endpoint_maps_timeout_to_504(client) -> None:
    _install_service(FakeRainViewerService(RainViewerRadarTimeoutError()))

    response = client.get("/api/weather/radar/rainviewer/3/4/5.png")

    assert response.status_code == 504
    assert response.json() == {"detail": {"code": "rainviewer_timeout"}}


def test_rainviewer_radar_tile_endpoint_maps_upstream_failures_to_502(client) -> None:
    _install_service(FakeRainViewerService(RainViewerRadarServiceError()))

    response = client.get("/api/weather/radar/rainviewer/3/4/5.png")

    assert response.status_code == 502
    assert response.json() == {"detail": {"code": "rainviewer_unavailable"}}


@pytest.mark.asyncio
async def test_rainviewer_radar_tile_endpoint_passes_disconnect_check(monkeypatch):
    service = FakeRainViewerService(_tile())
    monkeypatch.setitem(app.state._state, "rainviewer_radar_service", service)

    from app.api.weather import rainviewer_radar_tile

    class Request:
        app = app

        async def is_disconnected(self) -> bool:
            return True

    response = await rainviewer_radar_tile(1, 1, 1, Request())
    assert response.body.startswith(b"\x89PNG")
    assert service.disconnected_seen is True
