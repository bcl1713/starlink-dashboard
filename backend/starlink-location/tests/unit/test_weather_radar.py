"""Tests for RainViewer weather radar tile helpers."""

from unittest.mock import Mock
from urllib.error import URLError

import pytest
from app.services.weather_radar import RainViewerRadarService

RAINVIEWER_METADATA = {
    "host": "https://tilecache.rainviewer.com",
    "radar": {
        "past": [
            {"time": 1000, "path": "/v2/radar/old"},
            {"time": 1600, "path": "/v2/radar/latest"},
        ],
        "nowcast": [],
    },
}


def test_rainviewer_service_builds_latest_radar_tile_url() -> None:
    service = RainViewerRadarService(metadata_fetcher=lambda: RAINVIEWER_METADATA)

    tile_url = service.tile_url(z=4, x=5, y=6)

    assert (
        tile_url
        == "https://tilecache.rainviewer.com/v2/radar/latest/512/4/5/6/2/1_1.png"
    )


def test_rainviewer_service_prefers_nowcast_frame_when_available() -> None:
    metadata = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {
            "past": [{"time": 1000, "path": "/v2/radar/past"}],
            "nowcast": [{"time": 2000, "path": "/v2/radar/nowcast"}],
        },
    }
    service = RainViewerRadarService(metadata_fetcher=lambda: metadata)

    assert service.tile_url(z=0, x=0, y=0).startswith(
        "https://tilecache.rainviewer.com/v2/radar/nowcast/"
    )


def test_rainviewer_service_caches_metadata_between_tile_requests() -> None:
    metadata_fetcher = Mock(return_value=RAINVIEWER_METADATA)
    service = RainViewerRadarService(
        metadata_fetcher=metadata_fetcher, cache_ttl_seconds=600
    )

    service.tile_url(z=1, x=2, y=3)
    service.tile_url(z=1, x=2, y=4)

    assert metadata_fetcher.call_count == 1


def test_rainviewer_service_rejects_zoom_levels_rainviewer_does_not_serve() -> None:
    service = RainViewerRadarService(metadata_fetcher=lambda: RAINVIEWER_METADATA)

    with pytest.raises(ValueError, match="zoom"):
        service.tile_url(z=8, x=0, y=0)


def test_rainviewer_service_reports_unavailable_metadata() -> None:
    service = RainViewerRadarService(
        metadata_fetcher=lambda: (_ for _ in ()).throw(URLError("nope"))
    )

    with pytest.raises(RuntimeError, match="RainViewer metadata unavailable"):
        service.tile_url(z=0, x=0, y=0)
