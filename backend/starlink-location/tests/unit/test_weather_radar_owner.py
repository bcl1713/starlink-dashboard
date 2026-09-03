"""Adversarial deterministic tests for owned async RainViewer exchanges."""

import asyncio
from collections.abc import Awaitable

import pytest

from app.services.weather_radar import (
    MAX_TILE_BYTES,
    RAINVIEWER_TILE_HOST,
    RainViewerUnavailable,
)
from app.services.weather_radar_owner import (
    AsyncPinnedHttpsTransport,
    RadarRequestOwner,
)

_TILE_URL = "https://tilecache.rainviewer.com/v2/radar/latest/512/0/0/0/2/1_1.png"


class _FakeReader:
    def __init__(self, headers: bytes, chunks: list[bytes]) -> None:
        self._headers = headers
        self._chunks = iter(chunks)
        self.read_calls = 0

    async def readuntil(self, _separator: bytes) -> bytes:
        return self._headers

    def read(self, _size: int) -> Awaitable[bytes]:
        future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
        future.set_result(next(self._chunks, b""))
        return future


class _FakeWriter:
    def __init__(self) -> None:
        self.closed = 0
        self.wait_closed_calls = 0
        self.request = b""

    def write(self, data: bytes) -> None:
        self.request += data

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed += 1

    async def wait_closed(self) -> None:
        self.wait_closed_calls += 1


def _headers(
    status: str = "200 OK", content_type: str = "image/png", length: str | None = None
) -> bytes:
    content_length = "" if length is None else f"Content-Length: {length}\r\n"
    return f"HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\n{content_length}\r\n".encode()


def _transport(
    monkeypatch, reader: _FakeReader, writer: _FakeWriter
) -> AsyncPinnedHttpsTransport:
    async def open_connection(
        *_args: object, **_kwargs: object
    ) -> tuple[_FakeReader, _FakeWriter]:
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    return AsyncPinnedHttpsTransport(resolver=lambda *_args: _public_ip())


async def _public_ip() -> list[str]:
    return ["8.8.8.8"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "content_type", "length", "chunks"),
    [
        ("302 Found", "image/png", "2", [b"OK"]),
        ("500 Server Error", "image/png", "2", [b"OK"]),
        ("200 OK", "text/html", "2", [b"OK"]),
        ("200 OK", "image/png", "not-a-number", [b"OK"]),
        ("200 OK", "image/png", str(MAX_TILE_BYTES + 1), [b"OK"]),
        ("200 OK", "image/png", "3", [b"OK"]),
    ],
)
async def test_async_transport_rejects_hostile_headers_and_closes_exactly_once(
    monkeypatch,
    status: str,
    content_type: str,
    length: str,
    chunks: list[bytes],
) -> None:
    reader = _FakeReader(_headers(status, content_type, length), chunks)
    writer = _FakeWriter()
    transport = _transport(monkeypatch, reader, writer)

    with pytest.raises(RainViewerUnavailable, match="source unavailable"):
        await transport.fetch(_TILE_URL, MAX_TILE_BYTES, "image/png")

    assert writer.closed == 1
    assert writer.wait_closed_calls == 1


@pytest.mark.asyncio
async def test_async_transport_rejects_raw_oversize_body_and_closes_stream(
    monkeypatch,
) -> None:
    reader = _FakeReader(_headers(), [b"x" * (MAX_TILE_BYTES + 1)])
    writer = _FakeWriter()
    transport = _transport(monkeypatch, reader, writer)

    with pytest.raises(RainViewerUnavailable, match="source unavailable"):
        await transport.fetch(_TILE_URL, MAX_TILE_BYTES, "image/png")

    assert writer.closed == 1
    assert writer.wait_closed_calls == 1


@pytest.mark.asyncio
async def test_async_transport_expires_aggregate_deadline_while_body_trickles(
    monkeypatch,
) -> None:
    now = 0.0

    class _TrickleReader(_FakeReader):
        def read(self, _size: int) -> Awaitable[bytes]:
            nonlocal now
            now += 3.0
            self.read_calls += 1
            future: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
            future.set_result(next(self._chunks, b""))
            return future

    reader = _TrickleReader(_headers(length="2"), [b"x", b"y"])
    writer = _FakeWriter()
    transport = _transport(monkeypatch, reader, writer)
    transport._monotonic = lambda: now

    with pytest.raises(RainViewerUnavailable, match="source unavailable"):
        await transport.fetch(_TILE_URL, MAX_TILE_BYTES, "image/png")

    assert reader.read_calls == 2
    assert writer.closed == 1


@pytest.mark.asyncio
async def test_async_transport_retries_numeric_ipv6_after_ipv4_connect_failure(
    monkeypatch,
) -> None:
    attempts: list[str] = []
    server_names: list[str] = []
    reader = _FakeReader(_headers(length="2"), [b"OK"])
    writer = _FakeWriter()

    async def open_connection(
        host: str, _port: int, **kwargs: object
    ) -> tuple[_FakeReader, _FakeWriter]:
        attempts.append(host)
        server_names.append(str(kwargs["server_hostname"]))
        if host == "8.8.8.8":
            raise OSError("unreachable first address")
        return reader, writer

    monkeypatch.setattr(asyncio, "open_connection", open_connection)
    transport = AsyncPinnedHttpsTransport(resolver=lambda *_args: _public_ips())

    assert await transport.fetch(_TILE_URL, MAX_TILE_BYTES, "image/png") == b"OK"
    assert attempts == ["8.8.8.8", "2001:4860:4860::8888"]
    assert server_names == [RAINVIEWER_TILE_HOST, RAINVIEWER_TILE_HOST]
    assert writer.closed == 1


async def _public_ips() -> list[str]:
    return ["8.8.8.8", "2001:4860:4860::8888"]


@pytest.mark.asyncio
async def test_owner_cancels_request_disconnected_inflight_exchange() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def exchange(*_args: object) -> bytes:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return b""

    owner = RadarRequestOwner(exchange=exchange)
    request = asyncio.create_task(owner.fetch(_TILE_URL, MAX_TILE_BYTES, "image/png"))
    await started.wait()
    request.cancel()

    with pytest.raises(asyncio.CancelledError):
        await request
    assert cancelled.is_set()
    assert owner.inflight_count == 0
    await owner.aclose()


@pytest.mark.asyncio
async def test_owner_shutdown_cancels_every_owned_exchange_and_reaps_them() -> None:
    started = asyncio.Event()
    cancellations = 0

    async def exchange(*_args: object) -> bytes:
        nonlocal cancellations
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancellations += 1
            raise
        return b""

    owner = RadarRequestOwner(exchange=exchange)
    requests = [
        asyncio.create_task(owner.fetch(_TILE_URL, MAX_TILE_BYTES, "image/png"))
        for _ in range(2)
    ]
    await started.wait()
    await owner.aclose()

    outcomes = await asyncio.gather(*requests, return_exceptions=True)
    assert all(isinstance(outcome, asyncio.CancelledError) for outcome in outcomes)
    assert cancellations == 2
    assert owner.inflight_count == 0
