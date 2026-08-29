"""Tests for weather radar API routes."""

# Ruff 0.16.5 classifies these imports differently from repo and backend roots.
# ruff: noqa: I001, RUF100
from __future__ import annotations

from dataclasses import dataclass
from tempfile import SpooledTemporaryFile

import httpcore
import httpx
import pytest

from app.api.weather import get_rainviewer_radar_service
from app.services.rainviewer_transport import (
    PinnedAsyncHTTPTransport,
    RainViewerPinningError,
)
from app.services.weather_radar import (
    InvalidRadarTileError,
    RadarTile,
    RainViewerRadarService,
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


class StaticResolver:
    async def resolve(self, host: str) -> tuple[str, ...]:
        return ("8.8.8.8",)


class FailingBackend(httpcore.AsyncNetworkBackend):
    def __init__(
        self,
        exc: BaseException | None = None,
        streams: list[RawHTTPStream | BaseException] | None = None,
    ) -> None:
        self.exc = exc
        self.streams = streams or []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        if self.exc is not None:
            raise self.exc
        if not self.streams:
            raise AssertionError("unexpected connection")
        stream = self.streams.pop(0)
        if isinstance(stream, BaseException):
            raise stream
        return stream

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options=None
    ):
        raise AssertionError("unix sockets are not used")


class RawHTTPStream:
    def __init__(
        self,
        output: bytes,
        *,
        tls_exc: BaseException | None = None,
        read_exc: BaseException | None = None,
    ) -> None:
        self.output = output
        self.tls_exc = tls_exc
        self.read_exc = read_exc
        self.reads = 0

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        if not self.output and self.read_exc is not None:
            raise self.read_exc
        self.reads += 1
        chunk, self.output = self.output[:max_bytes], self.output[max_bytes:]
        return chunk

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        return None

    async def aclose(self) -> None:
        return None

    async def start_tls(
        self,
        ssl_context,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ):
        if self.tls_exc is not None:
            raise self.tls_exc
        return self

    def get_extra_info(self, info: str):
        return None


def _install_service(service: FakeRainViewerService) -> None:
    app.state.rainviewer_radar_service = service


def _install_pinned_weather_service(
    backend: FailingBackend, resolver: StaticResolver | None = None
) -> RainViewerRadarService:
    resolver = resolver or StaticResolver()
    client = httpx.AsyncClient(
        transport=PinnedAsyncHTTPTransport(resolver=resolver, network_backend=backend),
        follow_redirects=False,
        trust_env=False,
    )
    service = RainViewerRadarService(
        client=client,
        metadata_body_limit_bytes=512,
        tile_body_limit_bytes=64,
        cancel_poll_interval_seconds=0.001,
    )
    app.state.rainviewer_radar_service = service
    return service


def _metadata_http_response() -> bytes:
    body = (
        b'{"host":"https://tilecache.rainviewer.com","radar":{"past":'
        b'[{"time":1710001600,"path":"/v2/radar/1710001600"}]}}'
    )
    return (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Connection: close\r\n\r\n"
        + body
    )


def _tile_http_response_then_read_error(exc: BaseException) -> RawHTTPStream:
    headers = (
        b"HTTP/1.1 200 OK\r\nContent-Type: image/png\r\n"
        b"Content-Length: 13\r\nConnection: close\r\n\r\n"
    )
    return RawHTTPStream(headers, read_exc=exc)


def _assert_stable_weather_failure(response, caplog, status_code: int) -> None:
    assert response.status_code == status_code
    expected = (
        {"detail": {"code": "rainviewer_timeout"}}
        if status_code == 504
        else {"detail": {"code": "rainviewer_unavailable"}}
    )
    assert response.json() == expected
    forbidden = [
        "SECRET",
        "sensitive",
        "api.rainviewer.com",
        "tilecache.rainviewer.com",
        "8.8.8.8",
        "weather-maps.json",
        "ProxyError",
        "UnsupportedProtocol",
        "Traceback",
        "Unhandled exception",
    ]
    log_text = caplog.text
    body_text = response.text
    for value in forbidden:
        assert value not in body_text
        assert value not in log_text


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


@pytest.mark.parametrize(
    ("exc", "status_code"),
    [
        (httpcore.ConnectTimeout("SECRET timeout api.rainviewer.com 8.8.8.8"), 504),
        (httpcore.ConnectError("SECRET connect tilecache.rainviewer.com"), 502),
        (httpcore.ProxyError("SECRET proxy tilecache.rainviewer.com 8.8.8.8"), 502),
        (
            httpcore.UnsupportedProtocol(
                "SECRET protocol tilecache.rainviewer.com 8.8.8.8"
            ),
            502,
        ),
    ],
)
def test_rainviewer_api_maps_pinned_connect_failures_without_leaks(
    client, caplog, exc: BaseException, status_code: int
) -> None:
    service = _install_pinned_weather_service(FailingBackend(exc=exc))
    try:
        response = client.get("/api/weather/radar/rainviewer/3/4/5.png")
    finally:
        client.portal.call(service.aclose)

    _assert_stable_weather_failure(response, caplog, status_code)


def test_rainviewer_api_maps_pinning_dns_failures_without_leaks(client, caplog) -> None:
    class RejectedResolver:
        async def resolve(self, host: str) -> tuple[str, ...]:
            raise RainViewerPinningError("SECRET resolver body 8.8.8.8")

    service = _install_pinned_weather_service(
        FailingBackend(), resolver=RejectedResolver()
    )
    try:
        response = client.get("/api/weather/radar/rainviewer/3/4/5.png")
    finally:
        client.portal.call(service.aclose)

    _assert_stable_weather_failure(response, caplog, 502)


@pytest.mark.parametrize(
    "exc",
    [
        httpcore.ProxyError("SECRET tile proxy tilecache.rainviewer.com 8.8.8.8"),
        httpcore.UnsupportedProtocol(
            "SECRET tile protocol tilecache.rainviewer.com 8.8.8.8"
        ),
    ],
)
def test_rainviewer_api_maps_pinned_tile_connect_failures_without_leaks(
    client, caplog, exc: BaseException
) -> None:
    service = _install_pinned_weather_service(
        FailingBackend(streams=[RawHTTPStream(_metadata_http_response()), exc])
    )
    try:
        response = client.get("/api/weather/radar/rainviewer/3/4/5.png")
    finally:
        client.portal.call(service.aclose)

    _assert_stable_weather_failure(response, caplog, 502)


@pytest.mark.parametrize(
    "stream",
    [
        RawHTTPStream(b"", tls_exc=httpcore.ConnectError("SECRET tls host 8.8.8.8")),
        RawHTTPStream(b"", read_exc=httpcore.RemoteProtocolError("SECRET protocol")),
        RawHTTPStream(b"", read_exc=httpcore.ProxyError("SECRET proxy stream")),
        RawHTTPStream(
            b"",
            read_exc=httpcore.UnsupportedProtocol("SECRET unsupported stream"),
        ),
    ],
)
def test_rainviewer_api_maps_pinned_tls_and_protocol_without_leaks(
    client, caplog, stream: RawHTTPStream
) -> None:
    service = _install_pinned_weather_service(FailingBackend(streams=[stream]))
    try:
        response = client.get("/api/weather/radar/rainviewer/3/4/5.png")
    finally:
        client.portal.call(service.aclose)

    _assert_stable_weather_failure(response, caplog, 502)


@pytest.mark.parametrize(
    "exc",
    [
        httpcore.ReadError("SECRET body read"),
        httpcore.ProxyError("SECRET proxy body tilecache.rainviewer.com 8.8.8.8"),
        httpcore.UnsupportedProtocol(
            "SECRET unsupported body tilecache.rainviewer.com 8.8.8.8"
        ),
    ],
)
def test_rainviewer_api_maps_pinned_body_read_failure_without_leaks(
    client, caplog, exc: BaseException
) -> None:
    service = _install_pinned_weather_service(
        FailingBackend(
            streams=[
                RawHTTPStream(_metadata_http_response()),
                _tile_http_response_then_read_error(exc),
            ]
        )
    )
    try:
        response = client.get("/api/weather/radar/rainviewer/3/4/5.png")
    finally:
        client.portal.call(service.aclose)

    _assert_stable_weather_failure(response, caplog, 502)


def test_rainviewer_radar_tile_endpoint_uses_dependency_override(client) -> None:
    service = FakeRainViewerService(_tile(b"\x89PNG\r\n\x1a\noverride"))
    app.dependency_overrides[get_rainviewer_radar_service] = lambda: service
    try:
        response = client.get("/api/weather/radar/rainviewer/3/4/5.png")
    finally:
        app.dependency_overrides.pop(get_rainviewer_radar_service, None)

    assert response.status_code == 200
    assert response.content == b"\x89PNG\r\n\x1a\noverride"


@pytest.mark.asyncio
async def test_rainviewer_radar_tile_endpoint_passes_disconnect_check(monkeypatch):
    service = FakeRainViewerService(_tile())
    monkeypatch.setitem(app.state._state, "rainviewer_radar_service", service)

    from app.api.weather import rainviewer_radar_tile

    class Request:
        app = app

        async def is_disconnected(self) -> bool:
            return True

    response = await rainviewer_radar_tile(1, 1, 1, Request(), service)
    assert response.body.startswith(b"\x89PNG")
    assert service.disconnected_seen is True
