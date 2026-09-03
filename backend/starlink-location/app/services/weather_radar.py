"""Bounded, pinned HTTPS access for RainViewer radar tiles."""

from __future__ import annotations

import http.client
import ipaddress
import json
import re
import socket
import ssl
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

RAINVIEWER_METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
RAINVIEWER_TILE_HOST = "tilecache.rainviewer.com"
RAINVIEWER_MAX_ZOOM = 7
RAINVIEWER_TILE_SIZE = 512
RAINVIEWER_COLOR_SCHEME = 2
RAINVIEWER_OPTIONS = "1_1"
MAX_METADATA_BYTES = 128 * 1024
MAX_TILE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 5
_FRAME_PATH = re.compile(r"^/v2/radar/(?:[a-z]+|\d+)$")

MetadataFetcher = Callable[[], dict[str, Any]]


def _public_ip(host: str) -> str:
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    for _, _, _, _, address in addresses:
        candidate = str(address[0])
        if ipaddress.ip_address(candidate).is_global:
            return candidate
    raise RuntimeError("RainViewer source unavailable")


def _fetch_https(url: str, max_bytes: int, expected_type: str) -> bytes:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"api.rainviewer.com", RAINVIEWER_TILE_HOST}
        or parsed.port not in {None, 443}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise RuntimeError("RainViewer source unavailable")
    host = parsed.hostname
    assert host is not None
    ip = _public_ip(host)
    context = ssl.create_default_context()
    with socket.create_connection((ip, 443), REQUEST_TIMEOUT_SECONDS) as raw_socket:
        with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:
            request_path = parsed.path or "/"
            if parsed.query:
                request_path = f"{request_path}?{parsed.query}"
            tls_socket.sendall(
                (
                    f"GET {request_path} HTTP/1.1\r\nHost: {host}\r\n"
                    "Accept: image/png, application/json\r\n"
                    "User-Agent: starlink-dashboard/0.2 weather-radar\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
            )
            response = http.client.HTTPResponse(tls_socket)
            response.begin()
            content_type = response.getheader("Content-Type", "").split(";", 1)[0]
            content_length = response.getheader("Content-Length")
            if (
                response.status != 200
                or content_type != expected_type
                or (content_length is not None and int(content_length) > max_bytes)
            ):
                raise RuntimeError("RainViewer source unavailable")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise RuntimeError("RainViewer source unavailable")
            return body


def fetch_rainviewer_metadata() -> dict[str, Any]:
    """Fetch bounded metadata through an allow-listed, DNS-pinned TLS socket."""
    try:
        return json.loads(
            _fetch_https(RAINVIEWER_METADATA_URL, MAX_METADATA_BYTES, "application/json")
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError("RainViewer metadata unavailable") from exc


class RainViewerRadarService:
    """Resolve and proxy latest RainViewer imagery without browser redirects."""

    def __init__(
        self,
        metadata_fetcher: MetadataFetcher = fetch_rainviewer_metadata,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._metadata_fetcher = metadata_fetcher
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_metadata: dict[str, Any] | None = None
        self._cached_at_monotonic = 0.0

    def frame_token(self) -> str:
        frame = self._latest_frame(self._metadata())
        token = frame.get("time")
        if not isinstance(token, int) or token < 0:
            raise RuntimeError("RainViewer metadata unavailable")
        return str(token)

    def tile_url(self, z: int, x: int, y: int) -> str:
        self._validate_tile_coordinates(z, x, y)
        metadata = self._metadata()
        host = metadata.get("host")
        path = self._latest_frame(metadata).get("path")
        if host != f"https://{RAINVIEWER_TILE_HOST}" or not isinstance(path, str):
            raise RuntimeError("RainViewer metadata unavailable")
        if not _FRAME_PATH.fullmatch(path):
            raise RuntimeError("RainViewer metadata unavailable")
        return (
            f"{host}{path}/{RAINVIEWER_TILE_SIZE}/{z}/{x}/{y}/"
            f"{RAINVIEWER_COLOR_SCHEME}/{RAINVIEWER_OPTIONS}.png"
        )

    def tile_bytes(self, z: int, x: int, y: int) -> bytes:
        try:
            return _fetch_https(self.tile_url(z, x, y), MAX_TILE_BYTES, "image/png")
        except (OSError, ValueError) as exc:
            raise RuntimeError("RainViewer source unavailable") from exc

    def _metadata(self) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._cached_metadata is not None
            and now - self._cached_at_monotonic < self._cache_ttl_seconds
        ):
            return self._cached_metadata
        try:
            metadata = self._metadata_fetcher()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError("RainViewer metadata unavailable") from exc
        if not isinstance(metadata, dict):
            raise RuntimeError("RainViewer metadata unavailable")
        self._cached_metadata = metadata
        self._cached_at_monotonic = now
        return metadata

    @staticmethod
    def _validate_tile_coordinates(z: int, x: int, y: int) -> None:
        if z < 0 or z > RAINVIEWER_MAX_ZOOM:
            raise ValueError(f"RainViewer radar zoom must be 0-{RAINVIEWER_MAX_ZOOM}")
        if x < 0 or y < 0:
            raise ValueError("RainViewer radar tile coordinates must be non-negative")

    @staticmethod
    def _latest_frame(metadata: dict[str, Any]) -> dict[str, Any]:
        radar = metadata.get("radar")
        if not isinstance(radar, dict):
            raise RuntimeError("RainViewer metadata unavailable")
        frames = radar.get("nowcast") or radar.get("past") or []
        if not isinstance(frames, list) or not frames:
            raise RuntimeError("RainViewer metadata unavailable")
        latest = max(frames, key=lambda frame: frame.get("time", 0))
        if not isinstance(latest, dict):
            raise RuntimeError("RainViewer metadata unavailable")
        return latest