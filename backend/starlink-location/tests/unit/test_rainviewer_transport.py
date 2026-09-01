"""Tests for RainViewer pinned HTTP transport."""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import Iterable

import httpcore
import httpx
import pytest
from app.services import rainviewer_transport
from app.services.rainviewer_transport import (
    DnsPythonAddressResolver,
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


class RawDNSAnswer:
    def __init__(self, addresses: tuple[object, ...]) -> None:
        self._addresses = addresses

    def addresses(self) -> tuple[object, ...]:
        return self._addresses


class RawStringDNSResolver:
    def __init__(self, addresses: tuple[object, ...]) -> None:
        self._answer = RawDNSAnswer(addresses)

    async def resolve_name(self, host: str, family: int) -> RawDNSAnswer:
        return self._answer


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


class FailingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        raise self.exc

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options=None
    ):
        raise AssertionError("unix sockets are not used for RainViewer")


class ScriptedBackend(httpcore.AsyncNetworkBackend):
    def __init__(self, outcomes: Iterable[RecordingStream | BaseException]) -> None:
        self.outcomes = list(outcomes)
        self.tcp_calls: list[tuple[str, int, float | None]] = []

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        self.tcp_calls.append((host, port, timeout))
        if not self.outcomes:
            raise AssertionError("unexpected connection")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options=None
    ):
        raise AssertionError("unix sockets are not used for RainViewer")


@pytest.mark.parametrize(
    "addresses",
    [
        (),
        ("8.8.8.8", "10.0.0.1"),
        ("10.0.0.1",),
        ("100.64.0.1",),
        ("127.0.0.1",),
        ("169.254.1.1",),
        ("192.168.1.1",),
        ("224.0.0.1",),
        ("0.0.0.0",),
        ("2001:db8::1",),
        ("::1",),
        ("fe80::1",),
        ("not-an-ip-address",),
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
async def test_dns_python_raw_string_answers_pin_through_transport() -> None:
    resolver = DnsPythonAddressResolver()
    object.__setattr__(
        resolver,
        "_resolver",
        RawStringDNSResolver(("2001:4860:4860::8888", "8.8.8.8")),
    )
    backend = RecordingBackend()
    pinned = PinnedNetworkBackend(resolver=resolver, network_backend=backend)

    await pinned.connect_tcp("api.rainviewer.com", 443)

    assert backend.tcp_calls == [("2001:4860:4860::8888", 443)]


@pytest.mark.asyncio
async def test_transport_falls_back_from_failed_ipv6_to_ipv4_with_original_tls_host() -> (
    None
):
    first_failure = httpcore.ConnectError("unreachable ipv6")
    successful_stream = RecordingStream()
    backend = ScriptedBackend([first_failure, successful_stream])
    transport = PinnedAsyncHTTPTransport(
        resolver=FakeResolver(("2001:4860:4860::8888", "8.8.8.8")),
        network_backend=backend,
    )

    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.get(
            "https://api.rainviewer.com/public/weather-maps.json"
        )

    assert response.status_code == 200
    assert [(host, port) for host, port, _ in backend.tcp_calls] == [
        ("2001:4860:4860::8888", 443),
        ("8.8.8.8", 443),
    ]
    first_timeout = backend.tcp_calls[0][2]
    second_timeout = backend.tcp_calls[1][2]
    assert first_timeout is not None
    assert second_timeout is not None
    assert 0 < second_timeout <= first_timeout <= 5.0
    assert successful_stream.sni == ["api.rainviewer.com"]
    assert b"Host: api.rainviewer.com" in successful_stream.writes[0]


@pytest.mark.asyncio
async def test_transport_attempts_every_valid_address_then_sanitizes_terminal_error() -> (
    None
):
    first_failure = httpcore.ConnectError("SECRET first candidate")
    terminal_failure = httpcore.ConnectError("SECRET final candidate")
    backend = ScriptedBackend([first_failure, terminal_failure])
    transport = PinnedAsyncHTTPTransport(
        resolver=FakeResolver(("2001:4860:4860::8888", "8.8.8.8")),
        network_backend=backend,
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.ConnectError) as exc_info:
            await client.get("https://api.rainviewer.com/public/weather-maps.json")

    assert [(host, port) for host, port, _ in backend.tcp_calls] == [
        ("2001:4860:4860::8888", 443),
        ("8.8.8.8", 443),
    ]
    first_timeout = backend.tcp_calls[0][2]
    second_timeout = backend.tcp_calls[1][2]
    assert first_timeout is not None
    assert second_timeout is not None
    assert 0 < second_timeout <= first_timeout <= 5.0
    assert str(exc_info.value) == ""
    assert exc_info.value.__cause__ is terminal_failure


@pytest.mark.asyncio
async def test_pinned_backend_rejects_mixed_public_and_unsafe_answers_before_dialing() -> (
    None
):
    backend = RecordingBackend()
    pinned = PinnedNetworkBackend(
        resolver=FakeResolver(("8.8.8.8", "10.0.0.1")),
        network_backend=backend,
    )

    with pytest.raises(RainViewerPinningError, match="rainviewer_dns_rejected"):
        await pinned.connect_tcp("api.rainviewer.com", 443)

    assert backend.tcp_calls == []


@pytest.mark.asyncio
async def test_pinned_backend_propagates_cancellation_without_retrying() -> None:
    backend = ScriptedBackend([asyncio.CancelledError(), RecordingStream()])
    pinned = PinnedNetworkBackend(
        resolver=FakeResolver(("2001:4860:4860::8888", "8.8.8.8")),
        network_backend=backend,
    )

    with pytest.raises(asyncio.CancelledError):
        await pinned.connect_tcp("api.rainviewer.com", 443, timeout=5.0)

    assert [(host, port) for host, port, _ in backend.tcp_calls] == [
        ("2001:4860:4860::8888", 443)
    ]
    assert backend.tcp_calls[0][2] is not None
    assert 0 < backend.tcp_calls[0][2] <= 5.0


@pytest.mark.asyncio
async def test_pinned_backend_uses_one_decreasing_connect_timeout_budget(
    monkeypatch,
) -> None:
    now = [100.0]

    class AdvancingBackend(ScriptedBackend):
        async def connect_tcp(
            self,
            host: str,
            port: int,
            timeout: float | None = None,
            local_address: str | None = None,
            socket_options=None,
        ):
            self.tcp_calls.append((host, port, timeout))
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, BaseException):
                now[0] += 3.0
                raise outcome
            return outcome

    monkeypatch.setattr(rainviewer_transport.time, "monotonic", lambda: now[0])
    backend = AdvancingBackend([httpcore.ConnectError("first"), RecordingStream()])
    pinned = PinnedNetworkBackend(
        resolver=FakeResolver(("2001:4860:4860::8888", "8.8.8.8")),
        network_backend=backend,
    )

    await pinned.connect_tcp("api.rainviewer.com", 443, timeout=5.0)

    assert backend.tcp_calls == [
        ("2001:4860:4860::8888", 443, 5.0),
        ("8.8.8.8", 443, 2.0),
    ]


@pytest.mark.asyncio
async def test_dns_python_rejects_malformed_answer_shape() -> None:
    resolver = DnsPythonAddressResolver()
    object.__setattr__(resolver, "_resolver", RawStringDNSResolver((object(),)))

    with pytest.raises(RainViewerPinningError, match="rainviewer_dns_rejected"):
        await resolver.resolve("api.rainviewer.com")


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
    assert backend.streams[0].closed is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("core_exc", "httpx_exc"),
    [
        (
            httpcore.ProxyError("SECRET proxy api.rainviewer.com 8.8.8.8"),
            httpx.ProxyError,
        ),
        (
            httpcore.UnsupportedProtocol("SECRET protocol api.rainviewer.com 8.8.8.8"),
            httpx.UnsupportedProtocol,
        ),
    ],
)
async def test_http_transport_maps_canonical_core_exceptions_without_message(
    core_exc: BaseException, httpx_exc: type[httpx.HTTPError]
) -> None:
    transport = PinnedAsyncHTTPTransport(
        resolver=FakeResolver(("8.8.8.8",)),
        network_backend=FailingBackend(core_exc),
    )

    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx_exc) as exc_info:
            await client.get("https://api.rainviewer.com/public/weather-maps.json")

    assert str(exc_info.value) == ""
    assert exc_info.value.__cause__ is core_exc
