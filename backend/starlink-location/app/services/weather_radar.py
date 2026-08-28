"""RainViewer weather radar tile URL resolution."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

RAINVIEWER_METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
RAINVIEWER_MAX_ZOOM = 7
RAINVIEWER_TILE_SIZE = 512
RAINVIEWER_COLOR_SCHEME = 2
RAINVIEWER_OPTIONS = "1_1"

MetadataFetcher = Callable[[], dict[str, Any]]


def fetch_rainviewer_metadata() -> dict[str, Any]:
    """Fetch RainViewer's weather map frame metadata."""
    request = Request(
        RAINVIEWER_METADATA_URL,
        headers={"User-Agent": "starlink-dashboard/0.2 weather-radar"},
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


class RainViewerRadarService:
    """Build RainViewer radar tile URLs from cached metadata."""

    def __init__(
        self,
        metadata_fetcher: MetadataFetcher = fetch_rainviewer_metadata,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._metadata_fetcher = metadata_fetcher
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_metadata: dict[str, Any] | None = None
        self._cached_at_monotonic = 0.0

    def tile_url(self, z: int, x: int, y: int) -> str:
        """Return a redirect target for the latest available radar tile."""
        if z < 0 or z > RAINVIEWER_MAX_ZOOM:
            raise ValueError(f"RainViewer radar zoom must be 0-{RAINVIEWER_MAX_ZOOM}")
        if x < 0 or y < 0:
            raise ValueError("RainViewer radar tile coordinates must be non-negative")

        metadata = self._metadata()
        host = metadata.get("host")
        frame = self._latest_frame(metadata)
        path = frame.get("path")
        if not isinstance(host, str) or not isinstance(path, str):
            raise TypeError("RainViewer metadata unavailable")

        return (
            f"{host}{path}/{RAINVIEWER_TILE_SIZE}/{z}/{x}/{y}/"
            f"{RAINVIEWER_COLOR_SCHEME}/{RAINVIEWER_OPTIONS}.png"
        )

    def _metadata(self) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._cached_metadata is not None
            and now - self._cached_at_monotonic < self._cache_ttl_seconds
        ):
            return self._cached_metadata

        try:
            metadata = self._metadata_fetcher()
        except (OSError, URLError, json.JSONDecodeError) as exc:
            raise RuntimeError("RainViewer metadata unavailable") from exc

        self._cached_metadata = metadata
        self._cached_at_monotonic = now
        return metadata

    @staticmethod
    def _latest_frame(metadata: dict[str, Any]) -> dict[str, Any]:
        radar = metadata.get("radar")
        if not isinstance(radar, dict):
            raise TypeError("RainViewer metadata unavailable")

        nowcast = radar.get("nowcast") or []
        past = radar.get("past") or []
        frames = nowcast if nowcast else past
        if not frames:
            raise TypeError("RainViewer metadata unavailable")

        latest = max(frames, key=lambda frame: frame.get("time", 0))
        if not isinstance(latest, dict):
            raise TypeError("RainViewer metadata unavailable")
        return latest
