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
Resolver = Callable[..., list[tuple[Any, Any, Any, Any, Any]]]
Connector = Callable[[tuple[str, int], float], socket.socket]


class RainViewerUnavailable(RuntimeError):
    """Internal source failure which may safely cross the weather boundary."""


def _public_ips(host: str) -> list[str]:
    """Return each unique global DNS answer in resolver order."""
    try:
        addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise RainViewerUnavailable("RainViewer source unavailable") from exc

    candidates: list[str] = []
    for _, _, _, _, address in addresses:
        try:
            candidate = str(address[0])
            parsed = ipaddress.ip_address(candidate)
        except (ValueError, IndexError, TypeError):
            continue
        if parsed.is_global and candidate not in candidates:
            candidates.append(candidate)
    if not candidates:
        raise RainViewerUnavailable("RainViewer source unavailable")
    return candidates


class PinnedHttpsTransport:
    """Own a bounded, DNS-pinned HTTPS exchange and close every resource."""

    def __init__(
        self,
        resolver: Resolver = socket.getaddrinfo,
        connector: Connector = socket.create_connection,
        context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._resolver = resolver
        self._connector = connector
        self._context_factory = context_factory
        self._monotonic = monotonic

    def fetch(self, url: str, max_bytes: int, expected_type: str) -> bytes:
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in {"api.rainviewer.com", RAINVIEWER_TILE_HOST}
            or parsed.port not in {None, 443}
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise RainViewerUnavailable("RainViewer source unavailable")
        host = parsed.hostname
        assert host is not None
        candidates = self._resolve_public_ips(host)
        deadline = self._monotonic() + REQUEST_TIMEOUT_SECONDS
        request_path = parsed.path or "/"
        if parsed.query:
            request_path = f"{request_path}?{parsed.query}"

        for ip in candidates:
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                break
            try:
                return self._fetch_candidate(
                    ip,
                    host,
                    request_path,
                    max_bytes,
                    expected_type,
                    remaining,
                    deadline,
                )
            except ssl.SSLCertVerificationError as exc:
                raise RainViewerUnavailable("RainViewer source unavailable") from exc
            except (OSError, http.client.HTTPException) as exc:
                last_error = exc
                continue
        raise RainViewerUnavailable("RainViewer source unavailable") from locals().get(
            "last_error"
        )

    def _resolve_public_ips(self, host: str) -> list[str]:
        try:
            addresses = self._resolver(host, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise RainViewerUnavailable("RainViewer source unavailable") from exc
        candidates: list[str] = []
        for _, _, _, _, address in addresses:
            try:
                candidate = str(address[0])
                parsed = ipaddress.ip_address(candidate)
            except (ValueError, IndexError, TypeError):
                continue
            if parsed.is_global and candidate not in candidates:
                candidates.append(candidate)
        if not candidates:
            raise RainViewerUnavailable("RainViewer source unavailable")
        return candidates

    def _fetch_candidate(
        self,
        ip: str,
        host: str,
        request_path: str,
        max_bytes: int,
        expected_type: str,
        remaining: float,
        deadline: float,
    ) -> bytes:
        context = self._context_factory()
        with self._connector((ip, 443), remaining) as raw_socket:
            raw_socket.settimeout(remaining)
            with context.wrap_socket(raw_socket, server_hostname=host) as tls_socket:
                tls_socket.settimeout(max(0.001, deadline - self._monotonic()))
                tls_socket.sendall(
                    (
                        f"GET {request_path} HTTP/1.1\r\nHost: {host}\r\n"
                        "Accept: image/png, application/json\r\n"
                        "User-Agent: starlink-dashboard/0.2 weather-radar\r\n"
                        "Connection: close\r\n\r\n"
                    ).encode("ascii")
                )
                response = http.client.HTTPResponse(tls_socket)
                try:
                    response.begin()
                    content_type = response.getheader("Content-Type", "").split(";", 1)[
                        0
                    ]
                    content_length = response.getheader("Content-Length")
                    declared_size: int | None = None
                    if content_length is not None:
                        try:
                            declared_size = int(content_length)
                        except ValueError as exc:
                            raise RainViewerUnavailable(
                                "RainViewer source unavailable"
                            ) from exc
                        if declared_size < 0 or declared_size > max_bytes:
                            raise RainViewerUnavailable("RainViewer source unavailable")
                    if response.status != 200 or content_type != expected_type:
                        raise RainViewerUnavailable("RainViewer source unavailable")
                    tls_socket.settimeout(max(0.001, deadline - self._monotonic()))
                    body = response.read(max_bytes + 1)
                    if (
                        len(body) > max_bytes
                        or (declared_size is not None and len(body) != declared_size)
                        or self._monotonic() > deadline
                    ):
                        raise RainViewerUnavailable("RainViewer source unavailable")
                    return body
                finally:
                    response.close()


def _fetch_https(url: str, max_bytes: int, expected_type: str) -> bytes:
    return PinnedHttpsTransport().fetch(url, max_bytes, expected_type)


def fetch_rainviewer_metadata() -> dict[str, Any]:
    """Fetch bounded metadata through an allow-listed, DNS-pinned TLS socket."""
    try:
        return json.loads(
            _fetch_https(
                RAINVIEWER_METADATA_URL, MAX_METADATA_BYTES, "application/json"
            )
        )
    except (OSError, ValueError, json.JSONDecodeError, RainViewerUnavailable) as exc:
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
            raise TypeError("RainViewer metadata must be an object")
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
            raise RainViewerUnavailable("RainViewer metadata unavailable")
        past = radar.get("past")
        nowcast = radar.get("nowcast")
        if not isinstance(past, list) or not isinstance(nowcast, list):
            raise RainViewerUnavailable("RainViewer metadata unavailable")
        frames = [*past, *nowcast]
        if not frames or len(frames) > 512:
            raise RuntimeError("RainViewer metadata unavailable")
        validated: list[dict[str, Any]] = []
        for frame in frames:
            if not isinstance(frame, dict):
                raise RainViewerUnavailable("RainViewer metadata unavailable")
            token = frame.get("time")
            path = frame.get("path")
            if (
                not isinstance(token, int)
                or isinstance(token, bool)
                or token < 0
                or token > 4_102_444_800
                or not isinstance(path, str)
                or not _FRAME_PATH.fullmatch(path)
            ):
                raise RainViewerUnavailable("RainViewer metadata unavailable")
            validated.append(frame)
        preferred = nowcast if nowcast else past
        return max(preferred, key=lambda frame: int(frame["time"]))
