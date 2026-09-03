"""Tests for same-origin weather radar API routes."""

import json

from app.api import weather


def test_rainviewer_radar_tile_endpoint_proxies_png_on_same_origin(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        weather.rainviewer_radar_service,
        "tile_bytes",
        lambda z, x, y: b"png-bytes",
    )

    response = client.get("/api/weather/radar/rainviewer/3/4/5.png")

    assert response.status_code == 200
    assert response.content == b"png-bytes"
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert "location" not in response.headers


def test_rainviewer_metadata_endpoint_returns_only_fixed_same_origin_template(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        weather.rainviewer_radar_service,
        "frame_token",
        lambda: "123",
    )

    response = client.get("/api/weather/radar/rainviewer/metadata")

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "tile_url": "/api/weather/radar/rainviewer/{z}/{x}/{y}.png?frame=123",
    }


def test_rainviewer_endpoints_sanitize_source_failure(client, monkeypatch) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> bytes:
        raise RuntimeError("upstream private 203.0.113.8 failed")

    monkeypatch.setattr(weather.rainviewer_radar_service, "tile_bytes", unavailable)

    response = client.get("/api/weather/radar/rainviewer/3/4/5.png")

    assert response.status_code == 503
    assert response.json() == {"detail": "Weather radar unavailable"}


def test_rainviewer_metadata_endpoint_sanitizes_invalid_metadata(
    client, monkeypatch
) -> None:
    def invalid_metadata() -> str:
        raise TypeError("upstream metadata was not an object")

    monkeypatch.setattr(
        weather.rainviewer_radar_service, "frame_token", invalid_metadata
    )

    response = client.get("/api/weather/radar/rainviewer/metadata")

    assert response.status_code == 503
    assert response.json() == {"detail": "Weather radar unavailable"}


def test_rainviewer_metadata_endpoint_sanitizes_malformed_frame_members(
    client, monkeypatch
) -> None:
    malformed_metadata = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {"past": ["not-a-frame"], "nowcast": []},
    }

    async def fetch_metadata(*_args: object, **_kwargs: object) -> bytes:
        return json.dumps(malformed_metadata).encode()

    monkeypatch.setattr(
        weather.rainviewer_radar_service._owner, "fetch", fetch_metadata
    )
    monkeypatch.setattr(weather.rainviewer_radar_service, "_cached_metadata", None)

    response = client.get("/api/weather/radar/rainviewer/metadata")

    assert response.status_code == 503
    assert response.json() == {"detail": "Weather radar unavailable"}


def test_rainviewer_metadata_endpoint_sanitizes_mixed_frame_members(
    client, monkeypatch
) -> None:
    malformed_metadata = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [{"time": 1, "path": "/v2/radar/valid"}, None],
            "nowcast": [],
        },
    }

    async def fetch_metadata(*_args: object, **_kwargs: object) -> bytes:
        return json.dumps(malformed_metadata).encode()

    monkeypatch.setattr(
        weather.rainviewer_radar_service._owner, "fetch", fetch_metadata
    )
    monkeypatch.setattr(weather.rainviewer_radar_service, "_cached_metadata", None)

    response = client.get("/api/weather/radar/rainviewer/metadata")

    assert response.status_code == 503
    assert response.json() == {"detail": "Weather radar unavailable"}
