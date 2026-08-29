"""Tests for RainViewer pinned HTTP transport."""

from __future__ import annotations

import ssl
from collections.abc import Iterable

import httpcore
import httpx
import pytest
from app.services.rainviewer_transport import (
    PinnedAsyncHTTPTransport,
    PinnedNetworkBackend,
    RainViewerPinningError,
    validate_global_addresses,
)


class FakeResolver:
    def __init__(self, *answers: Iterable[str]) -> None:
        self.answers = [tuple(answer) for answer in answers]
        self.hosts: list[str] = []

    async def resolve(self, host: str) -> tuple[str, ...]:
        self.hosts.append(host)
        if len(self.hosts) <= len(self.answers):
            return self.answers[len(self.hosts) - 1]
        return self.answers[-1]


class RecordingStream:
    def __init__(self) -> None:
        self.output = (
            b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok"
        )
        self.writes: list[bytes] = []
        self.closed = False
        self.sni: list[str | None] = []

    async def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        chunk, self.output = self.output[:max_bytes], self.output[max_bytes:]
        return chunk

    async def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self.writes.append(buffer)

    async def aclose(self) -> None:
        self.closed = True

    async def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ):
        self.sni.append(server_hostname)
        return self

    def get_extra_info(self, info: str):
        return None


class RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.tcp_calls: list[tuple[str, int]] = []
        self.streams: list[RecordingStream] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        self.tcp_calls.append((host, port))
        stream = RecordingStream()
        self.streams.append(stream)
        return stream

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options=None
    ):
        raise AssertionError("unix sockets are not used for RainViewer")


@pytest.mark.parametrize(
    "addresses",
    [
        (),
        ("8.8.8.8", "10.0.0.1"),
        ("100.64.0.1",),
        ("127.0.0.1",),
        ("169.254.1.1",),
        ("224.0.0.1",),
        ("0.0.0.0",),
        ("2001:db8::1",),
    ],
)
def test_validate_global_addresses_rejects_any_unsafe_answer(addresses) -> None:
    with pytest.raises(RainViewerPinningError):
        validate_global_addresses(addresses)


def test_validate_global_addresses_accepts_only_global_answers() -> None:
    assert validate_global_addresses(("8.8.8.8", "2001:4860:4860::8888")) == (
        "8.8.8.8",
        "2001:4860:4860::8888",
    )


@pytest.mark.asyncio
async def test_pinned_backend_resolves_original_host_but_connects_numeric_ip() -> None:
    resolver = FakeResolver(("8.8.8.8", "2001:4860:4860::8888"))
    backend = RecordingBackend()
    pinned = PinnedNetworkBackend(resolver=resolver, network_backend=backend)

    await pinned.connect_tcp("api.rainviewer.com", 443)

    assert resolver.hosts == ["api.rainviewer.com"]
    assert backend.tcp_calls == [("8.8.8.8", 443)]


@pytest.mark.asyncio
async def test_pinned_backend_rejects_wrong_host_port_and_private_dns() -> None:
    backend = RecordingBackend()
    pinned = PinnedNetworkBackend(
        resolver=FakeResolver(("10.0.0.1",)),
        network_backend=backend,
    )

    with pytest.raises(RainViewerPinningError):
        await pinned.connect_tcp("evil.example", 443)
    with pytest.raises(RainViewerPinningError):
        await pinned.connect_tcp("api.rainviewer.com", 80)
    with pytest.raises(RainViewerPinningError):
        await pinned.connect_tcp("api.rainviewer.com", 443)

    assert backend.tcp_calls == []


@pytest.mark.asyncio
async def test_selected_numeric_destination_is_not_replaced_by_later_dns() -> None:
    resolver = FakeResolver(("8.8.8.8",), ("1.1.1.1",))
    backend = RecordingBackend()
    pinned = PinnedNetworkBackend(resolver=resolver, network_backend=backend)

    await pinned.connect_tcp("tilecache.rainviewer.com", 443)
    await pinned.connect_tcp("tilecache.rainviewer.com", 443)

    assert backend.tcp_calls == [("8.8.8.8", 443), ("1.1.1.1", 443)]


@pytest.mark.asyncio
async def test_http_transport_preserves_hostname_for_tls_sni_and_host_header() -> None:
    resolver = FakeResolver(("8.8.8.8",))
    backend = RecordingBackend()
    transport = PinnedAsyncHTTPTransport(resolver=resolver, network_backend=backend)

    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get(
            "https://api.rainviewer.com/public/weather-maps.json"
        )

    assert response.status_code == 200
    assert backend.tcp_calls == [("8.8.8.8", 443)]
    assert backend.streams[0].sni == ["api.rainviewer.com"]
    assert b"Host: api.rainviewer.com" in backend.streams[0].writes[0]
