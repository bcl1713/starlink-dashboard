"""Pinned async transport for RainViewer HTTP requests."""

from __future__ import annotations

import ipaddress
import socket
import ssl
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

import dns.asyncresolver
import httpcore
import httpx

ALLOWED_RAINVIEWER_HOSTS = {"api.rainviewer.com", "tilecache.rainviewer.com"}
RAINVIEWER_HTTPS_PORT = 443


class RainViewerPinningError(RuntimeError):
    """Raised when RainViewer DNS or connection pinning rejects a request."""


class AddressResolver(Protocol):
    """Resolve a hostname to candidate address strings."""

    async def resolve(self, host: str) -> tuple[str, ...]:
        """Return A/AAAA address strings for host."""


class DnsPythonAddressResolver:
    """Resolve addresses with dnspython without search-domain expansion."""

    def __init__(self, lifetime_seconds: float = 2.0) -> None:
        self._resolver = dns.asyncresolver.Resolver(configure=True)
        self._resolver.lifetime = lifetime_seconds
        self._resolver.timeout = lifetime_seconds
        self._resolver.search = []
        self._resolver.use_search_by_default = False

    async def resolve(self, host: str) -> tuple[str, ...]:
        try:
            answer = await self._resolver.resolve_name(host, family=socket.AF_UNSPEC)
        except Exception as exc:
            raise RainViewerPinningError("rainviewer_dns_unavailable") from exc
        return tuple(address.address for address in answer.addresses())


def validate_global_addresses(
    addresses: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """Return addresses only when every DNS answer is globally routable."""
    parsed: list[str] = []
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as exc:
            raise RainViewerPinningError("rainviewer_dns_rejected") from exc
        if (
            not ip.is_global
            or ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            raise RainViewerPinningError("rainviewer_dns_rejected")
        parsed.append(str(ip))
    if not parsed:
        raise RainViewerPinningError("rainviewer_dns_rejected")
    return tuple(parsed)


class PinnedNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve RainViewer hosts and connect only to validated numeric addresses."""

    def __init__(
        self,
        resolver: AddressResolver | None = None,
        network_backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self._resolver = resolver or DnsPythonAddressResolver()
        self._network_backend = network_backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            ascii_host = host.encode("ascii").decode("ascii")
        except UnicodeError as exc:
            raise RainViewerPinningError("rainviewer_host_rejected") from exc
        if ascii_host != host or ascii_host not in ALLOWED_RAINVIEWER_HOSTS:
            raise RainViewerPinningError("rainviewer_host_rejected")
        if port != RAINVIEWER_HTTPS_PORT:
            raise RainViewerPinningError("rainviewer_port_rejected")

        addresses = validate_global_addresses(await self._resolver.resolve(host))
        return await self._network_backend.connect_tcp(
            addresses[0],
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        raise RainViewerPinningError("rainviewer_unix_socket_rejected")


class _HTTPXResponseStream(httpx.AsyncByteStream):
    def __init__(self, stream: httpcore.AsyncByteStream) -> None:
        self._stream = stream

    async def __aiter__(self) -> AsyncIterator[bytes]:
        async with _map_httpcore_exceptions():
            async for chunk in self._stream:
                yield chunk

    async def aclose(self) -> None:
        async with _map_httpcore_exceptions():
            await self._stream.aclose()


@asynccontextmanager
async def _map_httpcore_exceptions() -> AsyncIterator[None]:
    try:
        yield
    except RainViewerPinningError as exc:
        raise httpx.ConnectError("") from exc
    except httpcore.TimeoutException as exc:
        if isinstance(exc, httpcore.ConnectTimeout):
            raise httpx.ConnectTimeout("") from exc
        if isinstance(exc, httpcore.ReadTimeout):
            raise httpx.ReadTimeout("") from exc
        if isinstance(exc, httpcore.WriteTimeout):
            raise httpx.WriteTimeout("") from exc
        if isinstance(exc, httpcore.PoolTimeout):
            raise httpx.PoolTimeout("") from exc
        raise httpx.TimeoutException("") from exc
    except httpcore.NetworkError as exc:
        if isinstance(exc, httpcore.ConnectError):
            raise httpx.ConnectError("") from exc
        if isinstance(exc, httpcore.ReadError):
            raise httpx.ReadError("") from exc
        if isinstance(exc, httpcore.WriteError):
            raise httpx.WriteError("") from exc
        raise httpx.NetworkError("") from exc
    except httpcore.ProtocolError as exc:
        if isinstance(exc, httpcore.RemoteProtocolError):
            raise httpx.RemoteProtocolError("") from exc
        if isinstance(exc, httpcore.LocalProtocolError):
            raise httpx.LocalProtocolError("") from exc
        raise httpx.ProtocolError("") from exc


class PinnedAsyncHTTPTransport(httpx.AsyncBaseTransport):
    """HTTPX transport backed by a pinned HTTPCore connection pool."""

    def __init__(
        self,
        resolver: AddressResolver | None = None,
        network_backend: httpcore.AsyncNetworkBackend | None = None,
        *,
        max_connections: int = 10,
        max_keepalive_connections: int = 5,
        keepalive_expiry: float = 30.0,
    ) -> None:
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=max_connections,
            max_keepalive_connections=max_keepalive_connections,
            keepalive_expiry=keepalive_expiry,
            http1=True,
            http2=False,
            retries=0,
            network_backend=PinnedNetworkBackend(
                resolver=resolver, network_backend=network_backend
            ),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        core_request = httpcore.Request(
            request.method,
            str(request.url),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        async with _map_httpcore_exceptions():
            core_response = await self._pool.handle_async_request(core_request)
        return httpx.Response(
            status_code=core_response.status,
            headers=core_response.headers,
            stream=_HTTPXResponseStream(core_response.stream),
            extensions=core_response.extensions,
            request=request,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()
