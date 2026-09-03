"""Application-owned cancellable exchanges for RainViewer radar requests."""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import ssl
import time
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlparse

import dns.asyncresolver
from app.services.weather_radar import (
    MAX_METADATA_BYTES,
    MAX_TILE_BYTES,
    RAINVIEWER_METADATA_URL,
    RAINVIEWER_TILE_HOST,
    REQUEST_TIMEOUT_SECONDS,
    RainViewerRadarService,
    RainViewerUnavailable,
)

Exchange = Callable[[str, int, str], Awaitable[bytes]]
Resolver = Callable[[str, float], Awaitable[list[str]]]


class AsyncPinnedHttpsTransport:
    """Perform a pinned HTTPS exchange with cancellable DNS and streams."""

    def __init__(
        self,
        resolver: Resolver | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        context_factory: Callable[[], ssl.SSLContext] = ssl.create_default_context,
    ) -> None:
        self._resolver = resolver or self._resolve_public_ips
        self._monotonic = monotonic
        self._context_factory = context_factory
        self._writers: set[asyncio.StreamWriter] = set()
        self._lock = asyncio.Lock()

    async def fetch(self, url: str, max_bytes: int, expected_type: str) -> bytes:
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
        deadline = self._monotonic() + REQUEST_TIMEOUT_SECONDS
        candidates = await self._with_deadline(
            self._resolver(host, self._remaining(deadline)), deadline
        )
        if not candidates:
            raise RainViewerUnavailable("RainViewer source unavailable")
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        last_error: BaseException | None = None
        for ip in candidates:
            try:
                return await self._fetch_candidate(
                    ip, host, path, max_bytes, expected_type, deadline
                )
            except asyncio.CancelledError:
                raise
            except (OSError, ValueError, ssl.SSLError, asyncio.TimeoutError) as exc:
                last_error = exc
        raise RainViewerUnavailable("RainViewer source unavailable") from last_error

    async def aclose(self) -> None:
        async with self._lock:
            writers = list(self._writers)
            self._writers.clear()
        for writer in writers:
            writer.close()
        if writers:
            await asyncio.gather(
                *(writer.wait_closed() for writer in writers), return_exceptions=True
            )

    async def _fetch_candidate(
        self,
        ip: str,
        host: str,
        path: str,
        max_bytes: int,
        expected_type: str,
        deadline: float,
    ) -> bytes:
        context = self._context_factory()
        reader, writer = await self._with_deadline(
            asyncio.open_connection(
                ip,
                443,
                ssl=context,
                server_hostname=host,
                ssl_handshake_timeout=self._remaining(deadline),
            ),
            deadline,
        )
        async with self._lock:
            self._writers.add(writer)
        try:
            writer.write(
                (
                    f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                    "Accept: image/png, application/json\r\n"
                    "User-Agent: starlink-dashboard/0.2 weather-radar\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("ascii")
            )
            await self._with_deadline(writer.drain(), deadline)
            header_block = await self._with_deadline(
                reader.readuntil(b"\r\n\r\n"), deadline
            )
            status, headers = self._parse_headers(header_block)
            if (
                status != 200
                or headers.get("content-type", "").split(";", 1)[0] != expected_type
            ):
                raise RainViewerUnavailable("RainViewer source unavailable")
            declared_size = self._declared_size(
                headers.get("content-length"), max_bytes
            )
            body = await self._read_body(reader, max_bytes, deadline)
            if len(body) > max_bytes or (
                declared_size is not None and len(body) != declared_size
            ):
                raise RainViewerUnavailable("RainViewer source unavailable")
            return body
        finally:
            async with self._lock:
                self._writers.discard(writer)
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _read_body(
        self, reader: asyncio.StreamReader, max_bytes: int, deadline: float
    ) -> bytes:
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            chunk = await self._with_deadline(
                reader.read(min(64 * 1024, remaining)), deadline
            )
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    async def _with_deadline(self, operation: Awaitable[Any], deadline: float) -> Any:
        async with asyncio.timeout(self._remaining(deadline)):
            return await operation

    def _remaining(self, deadline: float) -> float:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise RainViewerUnavailable("RainViewer source unavailable")
        return remaining

    async def _resolve_public_ips(self, host: str, timeout: float) -> list[str]:
        resolver = dns.asyncresolver.Resolver()
        answers = await asyncio.gather(
            resolver.resolve(host, "A", lifetime=timeout),
            resolver.resolve(host, "AAAA", lifetime=timeout),
            return_exceptions=True,
        )
        candidates: list[str] = []
        for answer in answers:
            if isinstance(answer, BaseException):
                continue
            for record in answer:
                candidate = str(record)
                try:
                    parsed = ipaddress.ip_address(candidate)
                except ValueError:
                    continue
                if parsed.is_global and candidate not in candidates:
                    candidates.append(candidate)
        return candidates

    @staticmethod
    def _parse_headers(header_block: bytes) -> tuple[int, dict[str, str]]:
        lines = header_block.decode("iso-8859-1").split("\r\n")
        try:
            _, code, _ = lines[0].split(" ", 2)
            status = int(code)
        except (IndexError, ValueError) as exc:
            raise RainViewerUnavailable("RainViewer source unavailable") from exc
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line:
                continue
            try:
                name, value = line.split(":", 1)
            except ValueError as exc:
                raise RainViewerUnavailable("RainViewer source unavailable") from exc
            headers[name.lower()] = value.strip()
        return status, headers

    @staticmethod
    def _declared_size(value: str | None, max_bytes: int) -> int | None:
        if value is None:
            return None
        try:
            size = int(value)
        except ValueError as exc:
            raise RainViewerUnavailable("RainViewer source unavailable") from exc
        if size < 0 or size > max_bytes:
            raise RainViewerUnavailable("RainViewer source unavailable")
        return size


class RadarRequestOwner:
    """Track production radar exchanges and close them on cancellation/shutdown."""

    def __init__(self, exchange: Exchange | None = None) -> None:
        self._transport = AsyncPinnedHttpsTransport() if exchange is None else None
        self._exchange = exchange or self._transport.fetch
        self._tasks: set[asyncio.Task[bytes]] = set()
        self._lock = asyncio.Lock()
        self._closed = False

    @property
    def inflight_count(self) -> int:
        return len(self._tasks)

    async def fetch(self, url: str, max_bytes: int, expected_type: str) -> bytes:
        async with self._lock:
            if self._closed:
                raise RainViewerUnavailable("RainViewer source unavailable")
            task = asyncio.create_task(self._exchange(url, max_bytes, expected_type))
            self._tasks.add(task)
        try:
            return await task
        finally:
            async with self._lock:
                self._tasks.discard(task)

    async def aclose(self) -> None:
        async with self._lock:
            self._closed = True
            tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        if self._transport is not None:
            await self._transport.aclose()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


class OwnedRainViewerRadarService:
    """Radar service whose network operations are owned by application lifespan."""

    def __init__(self, owner: RadarRequestOwner, cache_ttl_seconds: int = 300) -> None:
        self._owner = owner
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_metadata: dict[str, Any] | None = None
        self._cached_at_monotonic = 0.0

    async def frame_token(self) -> str:
        frame = RainViewerRadarService._latest_frame(await self._metadata())
        token = frame.get("time")
        if not isinstance(token, int) or token < 0:
            raise RuntimeError("RainViewer metadata unavailable")
        return str(token)

    async def tile_bytes(self, z: int, x: int, y: int) -> bytes:
        url = await self.tile_url(z, x, y)
        try:
            return await self._owner.fetch(url, MAX_TILE_BYTES, "image/png")
        except (OSError, ValueError, RainViewerUnavailable) as exc:
            raise RuntimeError("RainViewer source unavailable") from exc

    async def tile_url(self, z: int, x: int, y: int) -> str:
        RainViewerRadarService._validate_tile_coordinates(z, x, y)
        metadata = await self._metadata()
        host = metadata.get("host")
        path = RainViewerRadarService._latest_frame(metadata).get("path")
        if host != f"https://{RAINVIEWER_TILE_HOST}" or not isinstance(path, str):
            raise RuntimeError("RainViewer metadata unavailable")
        return f"{host}{path}/512/{z}/{x}/{y}/2/1_1.png"

    async def _metadata(self) -> dict[str, Any]:
        now = time.monotonic()
        if (
            self._cached_metadata is not None
            and now - self._cached_at_monotonic < self._cache_ttl_seconds
        ):
            return self._cached_metadata
        try:
            raw = await self._owner.fetch(
                RAINVIEWER_METADATA_URL, MAX_METADATA_BYTES, "application/json"
            )
            metadata = json.loads(raw)
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            RainViewerUnavailable,
        ) as exc:
            raise RuntimeError("RainViewer metadata unavailable") from exc
        if not isinstance(metadata, dict):
            raise TypeError("RainViewer metadata unavailable")
        self._cached_metadata = metadata
        self._cached_at_monotonic = now
        return metadata
