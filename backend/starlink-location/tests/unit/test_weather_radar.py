"""Tests for RainViewer weather radar tile helpers."""

from io import BytesIO
from typing import Self
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from app.services.weather_radar import (
    PinnedHttpsTransport,
    RainViewerRadarService,
    RainViewerUnavailable,
    _public_ips,
)

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


def test_public_ips_returns_unique_public_ipv4_and_ipv6_answers(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.weather_radar.socket.getaddrinfo",
        lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (10, 1, 6, "", ("2001:4860:4860::8888", 443, 0, 0)),
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (2, 1, 6, "", ("127.0.0.1", 443)),
        ],
    )

    assert _public_ips("tilecache.rainviewer.com") == [
        "8.8.8.8",
        "2001:4860:4860::8888",
    ]


class _FakeSocket:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.closed = 0
        self.sent = b""
        self.timeouts: list[float] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.closed += 1

    def makefile(self, *_args: object, **_kwargs: object) -> BytesIO:
        return BytesIO(self.payload)

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)


class _FakeContext:
    def __init__(self) -> None:
        self.server_names: list[str] = []

    def wrap_socket(self, sock: _FakeSocket, *, server_hostname: str) -> _FakeSocket:
        self.server_names.append(server_hostname)
        return sock


def test_pinned_transport_falls_back_to_later_public_address_with_original_sni() -> (
    None
):
    socket = _FakeSocket(
        b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 2\r\n\r\nOK"
    )
    attempts: list[tuple[str, int]] = []
    context = _FakeContext()

    def connector(address: tuple[str, int], _timeout: float) -> _FakeSocket:
        attempts.append(address)
        if len(attempts) == 1:
            raise OSError("first address failed")
        return socket

    transport = PinnedHttpsTransport(
        resolver=lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (10, 1, 6, "", ("2001:4860:4860::8888", 443, 0, 0)),
        ],
        connector=connector,
        context_factory=lambda: context,
    )

    result = transport.fetch(
        "https://tilecache.rainviewer.com/v2/radar/latest/512/0/0/0/2/1_1.png",
        max_bytes=16,
        expected_type="image/png",
    )

    assert result == b"OK"
    assert attempts == [("8.8.8.8", 443), ("2001:4860:4860::8888", 443)]
    assert context.server_names == ["tilecache.rainviewer.com"]
    assert socket.closed == 2


def test_pinned_transport_sanitizes_all_address_failures() -> None:
    attempts: list[tuple[str, int]] = []

    def connector(address: tuple[str, int], _timeout: float) -> _FakeSocket:
        attempts.append(address)
        raise OSError("unreachable")

    transport = PinnedHttpsTransport(
        resolver=lambda *_args, **_kwargs: [
            (2, 1, 6, "", ("8.8.8.8", 443)),
            (10, 1, 6, "", ("2001:4860:4860::8888", 443, 0, 0)),
        ],
        connector=connector,
    )

    with pytest.raises(RainViewerUnavailable, match="source unavailable"):
        transport.fetch(
            "https://tilecache.rainviewer.com/v2/radar/latest/512/0/0/0/2/1_1.png",
            max_bytes=16,
            expected_type="image/png",
        )

    assert attempts == [("8.8.8.8", 443), ("2001:4860:4860::8888", 443)]


def test_pinned_transport_rejects_short_content_length_body() -> None:
    socket = _FakeSocket(
        b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\nContent-Length: 3\r\n\r\nOK"
    )
    transport = PinnedHttpsTransport(
        resolver=lambda *_args, **_kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))],
        connector=lambda *_args: socket,
        context_factory=_FakeContext,
    )

    with pytest.raises(RainViewerUnavailable, match="source unavailable"):
        transport.fetch(
            "https://tilecache.rainviewer.com/v2/radar/latest/512/0/0/0/2/1_1.png",
            max_bytes=16,
            expected_type="image/png",
        )
