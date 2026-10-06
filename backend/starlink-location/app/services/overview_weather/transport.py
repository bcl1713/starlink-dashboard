"""Public-IP-pinned TLS. Every opened stream has exactly one cleanup owner."""

import asyncio
import ipaddress
import ssl
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import dns.asyncresolver
import dns.exception

from .clock import WeatherClock
from .protocol import WeatherPayload, WeatherUnavailable, exchange_http, remaining
from .rainviewer import valid_tile_path

Resolver = Callable[[str, float], Awaitable[list[str]]]
TlsOpener = Callable[
    [str, str, ssl.SSLContext, float],
    Awaitable[tuple[asyncio.StreamReader, asyncio.StreamWriter]],
]


async def resolve_public(host: str, timeout: float) -> list[str]:
    resolver = dns.asyncresolver.Resolver()

    async def query(kind):
        try:
            answer = await resolver.resolve(host, kind, lifetime=timeout)
            return [record.address for record in answer]
        except dns.exception.DNSException:
            return []

    answers = await asyncio.gather(query("A"), query("AAAA"))
    return [address for answer in answers for address in answer]


async def open_tls(ip: str, host: str, context: ssl.SSLContext, timeout: float):
    return await asyncio.open_connection(
        ip, 443, ssl=context, server_hostname=host, ssl_handshake_timeout=timeout
    )


class PinnedWeatherTransport:
    def __init__(
        self,
        clock: WeatherClock,
        resolver: Resolver | None = None,
        opener: TlsOpener | None = None,
    ):
        self.clock = clock
        self.resolver = resolver or resolve_public
        self.opener = opener or open_tls

    async def fetch(
        self,
        url: str,
        max_bytes: int,
        expected_type: str,
        deadline: float,
        *,
        before_attempt: Callable[[], None],
    ) -> WeatherPayload:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.query
            or parsed.fragment
            or (
                parsed.netloc == "api.rainviewer.com"
                and parsed.path != "/public/weather-maps.json"
            )
            or (
                parsed.netloc == "tilecache.rainviewer.com"
                and not valid_tile_path(parsed.path)
            )
            or parsed.netloc not in {"api.rainviewer.com", "tilecache.rainviewer.com"}
        ):
            raise WeatherUnavailable()
        writer = None
        try:
            async with asyncio.timeout(remaining(deadline, self.clock)):
                addresses = await self.resolver(
                    parsed.netloc, remaining(deadline, self.clock)
                )
            if not addresses or len(addresses) > 16:
                raise WeatherUnavailable()
            for address in addresses:
                ip = ipaddress.ip_address(address)
                if not ip.is_global or ip.is_multicast or ip.is_reserved:
                    raise WeatherUnavailable()
            context = ssl.create_default_context()
            for address in dict.fromkeys(addresses):
                remaining(deadline, self.clock)
                before_attempt()
                try:
                    async with asyncio.timeout(remaining(deadline, self.clock)):
                        reader, writer = await self.opener(
                            address,
                            parsed.netloc,
                            context,
                            remaining(deadline, self.clock),
                        )
                    break
                except (OSError, ssl.SSLError):
                    continue
            if writer is None:
                raise WeatherUnavailable()
            return await exchange_http(
                reader,
                writer,
                parsed.netloc,
                parsed.path,
                max_bytes,
                expected_type,
                deadline,
                self.clock,
            )
        except (OSError, ValueError, dns.exception.DNSException) as error:
            raise WeatherUnavailable() from error
        finally:
            if writer is not None:
                writer.close()
                try:
                    await asyncio.shield(asyncio.wait_for(writer.wait_closed(), 1))
                except (OSError, TimeoutError):
                    pass
