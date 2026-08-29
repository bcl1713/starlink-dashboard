"""RainViewer weather radar tile proxy service."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import Any

import httpx
from app.services.rainviewer_transport import PinnedAsyncHTTPTransport
from httpx import StreamConsumed

RAINVIEWER_METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
RAINVIEWER_TILE_HOST = "tilecache.rainviewer.com"
RAINVIEWER_METADATA_HOST = "api.rainviewer.com"
RAINVIEWER_MAX_ZOOM = 7
RAINVIEWER_TILE_SIZE = 512
RAINVIEWER_COLOR_SCHEME = 2
RAINVIEWER_OPTIONS = "1_1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

CancelCheck = Callable[[], Awaitable[bool]]


class InvalidRadarTileError(ValueError):
    pass


class RainViewerRadarServiceError(RuntimeError):
    pass


class RainViewerRadarTimeoutError(RainViewerRadarServiceError):
    pass


@dataclass(frozen=True)
class RadarFrame:
    path: str
    timestamp: int


@dataclass
class RadarTile:
    spool: SpooledTemporaryFile[bytes]
    size_bytes: int
    frame_timestamp: int

    def read(self) -> bytes:
        self.spool.seek(0)
        return self.spool.read()

    def close(self) -> None:
        self.spool.close()


class RainViewerRadarService:
    """Fetch and validate RainViewer radar PNG tiles for same-origin proxying."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        metadata_cache_ttl_seconds: float = 300.0,
        clock: Callable[[], float] | None = None,
        metadata_body_limit_bytes: int = 256 * 1024,
        tile_body_limit_bytes: int = 2 * 1024 * 1024,
        request_timeout_seconds: float = 10.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            transport=PinnedAsyncHTTPTransport(),
            timeout=httpx.Timeout(request_timeout_seconds),
            follow_redirects=False,
            trust_env=False,
        )
        self._metadata_cache_ttl_seconds = metadata_cache_ttl_seconds
        self._clock = clock or time.monotonic
        self._metadata_body_limit_bytes = metadata_body_limit_bytes
        self._tile_body_limit_bytes = tile_body_limit_bytes
        self._cached_frame: RadarFrame | None = None
        self._cached_at_monotonic = 0.0
        self._metadata_lock = asyncio.Lock()
        self._metadata_task: asyncio.Task[RadarFrame] | None = None
        self._metadata_waiters = 0
        self._closed = False

    async def fetch_tile(
        self, z: int, x: int, y: int, cancel_check: CancelCheck
    ) -> RadarTile:
        """Fetch a validated PNG tile for XYZ coordinates."""
        self._validate_xyz(z, x, y)
        frame = await self._latest_frame()
        await self._raise_if_disconnected(cancel_check)
        url = self._tile_url(frame, z, x, y)
        response = await self._request_with_redirects(
            url,
            expected_host=RAINVIEWER_TILE_HOST,
            expected_path=url.path,
            headers={"Accept": "image/png", "Accept-Encoding": "identity"},
        )
        try:
            tile = await self._consume_tile(response, frame.timestamp, cancel_check)
        finally:
            await response.aclose()
        return tile

    async def aclose(self) -> None:
        """Close the owned client and any live metadata task exactly once."""
        if self._closed:
            return
        self._closed = True
        task = self._metadata_task
        self._metadata_task = None
        if task is not None and not task.done():
            task.cancel()
            with suppress(BaseException):
                await task
        await self._client.aclose()

    async def _latest_frame(self) -> RadarFrame:
        if self._cache_valid():
            assert self._cached_frame is not None
            return self._cached_frame

        async with self._metadata_lock:
            if self._cache_valid():
                assert self._cached_frame is not None
                return self._cached_frame
            if self._metadata_task is None or self._metadata_task.done():
                self._metadata_task = asyncio.create_task(self._load_frame())
            task = self._metadata_task
            self._metadata_waiters += 1
        try:
            return await asyncio.shield(task)
        except httpx.TimeoutException as exc:
            raise RainViewerRadarTimeoutError() from exc
        except RainViewerRadarServiceError:
            raise
        except Exception as exc:
            raise RainViewerRadarServiceError() from exc
        finally:
            async with self._metadata_lock:
                self._metadata_waiters = max(0, self._metadata_waiters - 1)
                if (
                    self._metadata_waiters == 0
                    and self._metadata_task is task
                    and task.done()
                ):
                    self._metadata_task = None

    def _cache_valid(self) -> bool:
        return (
            self._cached_frame is not None
            and self._clock() - self._cached_at_monotonic
            < self._metadata_cache_ttl_seconds
        )

    async def _load_frame(self) -> RadarFrame:
        url = httpx.URL(RAINVIEWER_METADATA_URL)
        response = await self._request_with_redirects(
            url,
            expected_host=RAINVIEWER_METADATA_HOST,
            expected_path="/public/weather-maps.json",
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
        )
        try:
            raw = await self._consume_limited_raw(
                response, self._metadata_body_limit_bytes
            )
            metadata = json.loads(raw.decode("utf-8"))
            frame = self._parse_metadata(metadata)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
            raise RainViewerRadarServiceError() from exc
        finally:
            await response.aclose()

        self._cached_frame = frame
        self._cached_at_monotonic = self._clock()
        return frame

    async def _request_with_redirects(
        self,
        url: httpx.URL,
        *,
        expected_host: str,
        expected_path: str,
        headers: dict[str, str],
    ) -> httpx.Response:
        current = self._validate_url(url, expected_host, expected_path)
        for _ in range(4):
            try:
                request = self._client.build_request("GET", current, headers=headers)
                response = await self._client.send(
                    request, stream=True, follow_redirects=False
                )
            except httpx.TimeoutException as exc:
                raise RainViewerRadarTimeoutError() from exc
            except httpx.HTTPError as exc:
                raise RainViewerRadarServiceError() from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                await response.aclose()
                if location is None:
                    raise RainViewerRadarServiceError()
                current = self._validate_url(
                    current.join(location), expected_host, expected_path
                )
                continue
            if response.status_code != 200:
                await response.aclose()
                raise RainViewerRadarServiceError()
            return response
        raise RainViewerRadarServiceError()

    def _validate_url(
        self, url: httpx.URL, expected_host: str, expected_path: str
    ) -> httpx.URL:
        if (
            url.scheme != "https"
            or url.host != expected_host
            or url.port not in (None, 443)
            or url.userinfo
            or url.fragment
            or url.query
            or url.path != expected_path
        ):
            raise RainViewerRadarServiceError()
        return url

    def _parse_metadata(self, metadata: Any) -> RadarFrame:
        if (
            not isinstance(metadata, dict)
            or metadata.get("host") != "https://tilecache.rainviewer.com"
        ):
            raise RainViewerRadarServiceError()
        radar = metadata.get("radar")
        if not isinstance(radar, dict):
            raise RainViewerRadarServiceError()
        frames: list[RadarFrame] = []
        for section in ("past", "nowcast"):
            values = radar.get(section) or []
            if not isinstance(values, list) or len(values) > 128:
                raise RainViewerRadarServiceError()
            for value in values:
                if not isinstance(value, dict):
                    raise RainViewerRadarServiceError()
                timestamp = value.get("time")
                path = value.get("path")
                if (
                    not isinstance(timestamp, int)
                    or timestamp < 0
                    or not isinstance(path, str)
                ):
                    raise RainViewerRadarServiceError()
                self._validate_frame_path(path)
                frames.append(RadarFrame(path=path, timestamp=timestamp))
        if not frames:
            raise RainViewerRadarServiceError()
        return max(frames, key=lambda frame: (frame.timestamp, frame.path))

    def _tile_url(self, frame: RadarFrame, z: int, x: int, y: int) -> httpx.URL:
        self._validate_frame_path(frame.path)
        return httpx.URL(
            f"https://{RAINVIEWER_TILE_HOST}{frame.path}/"
            f"{RAINVIEWER_TILE_SIZE}/{z}/{x}/{y}/"
            f"{RAINVIEWER_COLOR_SCHEME}/{RAINVIEWER_OPTIONS}.png"
        )

    def _validate_frame_path(self, path: str) -> None:
        if not path.startswith("/v2/radar/"):
            raise RainViewerRadarServiceError()
        if "?" in path or "#" in path or "\\" in path or "//" in path:
            raise RainViewerRadarServiceError()

    def _validate_xyz(self, z: int, x: int, y: int) -> None:
        if z < 0 or z > RAINVIEWER_MAX_ZOOM:
            raise InvalidRadarTileError()
        upper = 2**z
        if x < 0 or y < 0 or x >= upper or y >= upper:
            raise InvalidRadarTileError()

    async def _consume_tile(
        self,
        response: httpx.Response,
        frame_timestamp: int,
        cancel_check: CancelCheck,
    ) -> RadarTile:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self._tile_body_limit_bytes:
                    raise RainViewerRadarServiceError()
            except ValueError as exc:
                raise RainViewerRadarServiceError() from exc
        content_type = response.headers.get("content-type", "").split(";", 1)[0]
        if content_type.strip().lower() != "image/png":
            raise RainViewerRadarServiceError()

        spool: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(  # noqa: SIM115
            max_size=self._tile_body_limit_bytes
        )
        size = 0
        try:
            try:
                async for chunk in response.aiter_raw():
                    await self._raise_if_disconnected(cancel_check)
                    size += len(chunk)
                    if size > self._tile_body_limit_bytes:
                        raise RainViewerRadarServiceError()
                    spool.write(chunk)
            except StreamConsumed:
                content = response.content
                size = len(content)
                if size > self._tile_body_limit_bytes:
                    raise RainViewerRadarServiceError()
                spool.write(content)
            spool.seek(0)
            if spool.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
                raise RainViewerRadarServiceError()
            spool.seek(0)
            return RadarTile(
                spool=spool, size_bytes=size, frame_timestamp=frame_timestamp
            )
        except BaseException:
            spool.close()
            raise

    async def _consume_limited_raw(self, response: httpx.Response, limit: int) -> bytes:
        chunks: list[bytes] = []
        size = 0
        try:
            async for chunk in response.aiter_raw():
                size += len(chunk)
                if size > limit:
                    raise RainViewerRadarServiceError()
                chunks.append(chunk)
        except StreamConsumed:
            content = response.content
            if len(content) > limit:
                raise RainViewerRadarServiceError()
            return content
        return b"".join(chunks)

    async def _raise_if_disconnected(self, cancel_check: CancelCheck) -> None:
        if await cancel_check():
            raise asyncio.CancelledError()
