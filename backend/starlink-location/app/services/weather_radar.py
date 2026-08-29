"""RainViewer weather radar tile proxy service."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import Any

import httpcore
import httpx
from app.services.rainviewer_transport import (
    PinnedAsyncHTTPTransport,
    RainViewerPinningError,
)
from httpx import StreamConsumed

RAINVIEWER_METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
RAINVIEWER_TILE_ORIGIN = "https://tilecache.rainviewer.com"
RAINVIEWER_TILE_HOST = "tilecache.rainviewer.com"
RAINVIEWER_METADATA_HOST = "api.rainviewer.com"
RAINVIEWER_MAX_ZOOM = 7
RAINVIEWER_TILE_SIZE = 512
RAINVIEWER_COLOR_SCHEME = 2
RAINVIEWER_OPTIONS = "1_1"
RAINVIEWER_MIN_FRAME_EPOCH = 946684800
RAINVIEWER_MAX_FRAME_EPOCH = 4102444800
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FRAME_PATH_RE = re.compile(r"^/v2/radar/(0|[1-9][0-9]*)$")
HTTPX_LOGGER = logging.getLogger("httpx")

CancelCheck = Callable[[], Awaitable[bool]]


class InvalidRadarTileError(ValueError):
    pass


class RainViewerRadarServiceError(RuntimeError):
    pass


class RainViewerRadarTimeoutError(RainViewerRadarServiceError):
    pass


class _RainViewerHTTPXLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return (
            RAINVIEWER_METADATA_HOST not in message
            and RAINVIEWER_TILE_HOST not in message
        )


if not any(
    isinstance(log_filter, _RainViewerHTTPXLogFilter)
    for log_filter in HTTPX_LOGGER.filters
):
    HTTPX_LOGGER.addFilter(_RainViewerHTTPXLogFilter())


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
        cancel_poll_interval_seconds: float = 0.05,
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
        self._cancel_poll_interval_seconds = cancel_poll_interval_seconds
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
        frame = await self._latest_frame(cancel_check)
        await self._raise_if_disconnected(cancel_check)
        url = self._tile_url(frame, z, x, y)
        response = await self._request_with_redirects(
            url,
            expected_url=url,
            headers={"Accept": "image/png", "Accept-Encoding": "identity"},
            cancel_check=cancel_check,
        )
        try:
            tile = await self._consume_tile(response, frame.timestamp, cancel_check)
        finally:
            await self._close_response(response)
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

    async def _latest_frame(self, cancel_check: CancelCheck) -> RadarFrame:
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
            return await self._await_with_cancel(
                asyncio.shield(task), cancel_check=cancel_check
            )
        except httpx.TimeoutException as exc:
            raise RainViewerRadarTimeoutError() from exc
        except RainViewerRadarServiceError:
            raise
        except asyncio.CancelledError:
            raise
        except httpcore.TimeoutException as exc:
            raise RainViewerRadarTimeoutError() from exc
        except (httpx.HTTPError, httpcore.NetworkError, httpcore.ProtocolError) as exc:
            raise RainViewerRadarServiceError() from exc
        except Exception as exc:
            raise RainViewerRadarServiceError() from exc
        finally:
            should_cancel = False
            async with self._metadata_lock:
                self._metadata_waiters = max(0, self._metadata_waiters - 1)
                if self._metadata_waiters == 0 and self._metadata_task is task:
                    if task.done():
                        self._metadata_task = None
                    else:
                        self._metadata_task = None
                        should_cancel = True
            if should_cancel:
                task.cancel()
                with suppress(BaseException):
                    await task

    def _cache_valid(self) -> bool:
        return (
            self._cached_frame is not None
            and self._clock() - self._cached_at_monotonic
            < self._metadata_cache_ttl_seconds
        )

    async def _load_frame(self) -> RadarFrame:
        response = await self._request_with_redirects(
            RAINVIEWER_METADATA_URL,
            expected_url=RAINVIEWER_METADATA_URL,
            headers={"Accept": "application/json", "Accept-Encoding": "identity"},
            cancel_check=None,
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
            await self._close_response(response)

        self._cached_frame = frame
        self._cached_at_monotonic = self._clock()
        return frame

    async def _request_with_redirects(
        self,
        url: str,
        *,
        expected_url: str,
        headers: dict[str, str],
        cancel_check: CancelCheck | None,
    ) -> httpx.Response:
        current = self._validate_url(url, expected_url)
        for _ in range(4):
            try:
                request = self._client.build_request("GET", current, headers=headers)
                send = self._client.send(request, stream=True, follow_redirects=False)
                if cancel_check is None:
                    response = await send
                else:
                    response = await self._await_with_cancel(
                        send, cancel_check=cancel_check
                    )
            except httpx.TimeoutException as exc:
                raise RainViewerRadarTimeoutError() from exc
            except httpcore.TimeoutException as exc:
                raise RainViewerRadarTimeoutError() from exc
            except asyncio.CancelledError:
                raise
            except (
                httpx.HTTPError,
                httpcore.NetworkError,
                httpcore.ProtocolError,
                RainViewerPinningError,
            ) as exc:
                raise RainViewerRadarServiceError() from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                await self._close_response(response)
                if location is None:
                    raise RainViewerRadarServiceError()
                current = self._validate_url(
                    self._resolve_redirect(current, location), expected_url
                )
                continue
            if response.status_code != 200:
                await self._close_response(response)
                raise RainViewerRadarServiceError()
            return response
        raise RainViewerRadarServiceError()

    def _validate_url(self, url: str, expected_url: str) -> str:
        if url != expected_url:
            raise RainViewerRadarServiceError()
        return url

    def _resolve_redirect(self, current: str, location: str) -> str:
        if any(char in location for char in ("\r", "\n", "\t", " ")):
            raise RainViewerRadarServiceError()
        if location.startswith("https://"):
            return location
        if location.startswith("/"):
            if current == RAINVIEWER_METADATA_URL:
                return f"https://{RAINVIEWER_METADATA_HOST}{location}"
            return f"{RAINVIEWER_TILE_ORIGIN}{location}"
        raise RainViewerRadarServiceError()

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
                    type(timestamp) is not int
                    or timestamp < RAINVIEWER_MIN_FRAME_EPOCH
                    or timestamp > RAINVIEWER_MAX_FRAME_EPOCH
                    or not isinstance(path, str)
                ):
                    raise RainViewerRadarServiceError()
                self._validate_frame_path(path)
                if path.rsplit("/", 1)[-1] != str(timestamp):
                    raise RainViewerRadarServiceError()
                frames.append(RadarFrame(path=path, timestamp=timestamp))
        if not frames:
            raise RainViewerRadarServiceError()
        return max(frames, key=lambda frame: (frame.timestamp, frame.path))

    def _tile_url(self, frame: RadarFrame, z: int, x: int, y: int) -> str:
        self._validate_frame_path(frame.path)
        return (
            f"https://{RAINVIEWER_TILE_HOST}{frame.path}/"
            f"{RAINVIEWER_TILE_SIZE}/{z}/{x}/{y}/"
            f"{RAINVIEWER_COLOR_SCHEME}/{RAINVIEWER_OPTIONS}.png"
        )

    def _validate_frame_path(self, path: str) -> None:
        if FRAME_PATH_RE.fullmatch(path) is None:
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
        content_lengths = response.headers.get_list("content-length")
        if content_lengths:
            self._validate_content_length(content_lengths)
        content_type = response.headers.get("content-type", "").split(";", 1)[0]
        if content_type.strip().lower() != "image/png":
            raise RainViewerRadarServiceError()

        spool: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(  # noqa: SIM115
            max_size=self._tile_body_limit_bytes
        )
        size = 0
        try:
            try:
                iterator = response.aiter_raw().__aiter__()
                while True:
                    try:
                        chunk = await self._await_with_cancel(
                            iterator.__anext__(), cancel_check=cancel_check
                        )
                    except StopAsyncIteration:
                        break
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
        except (httpx.TimeoutException, httpcore.TimeoutException) as exc:
            spool.close()
            raise RainViewerRadarTimeoutError() from exc
        except asyncio.CancelledError:
            spool.close()
            raise
        except (
            httpx.HTTPError,
            httpcore.NetworkError,
            httpcore.ProtocolError,
            RainViewerPinningError,
        ) as exc:
            spool.close()
            raise RainViewerRadarServiceError() from exc
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
        except (httpx.TimeoutException, httpcore.TimeoutException) as exc:
            raise RainViewerRadarTimeoutError() from exc
        except asyncio.CancelledError:
            raise
        except (
            httpx.HTTPError,
            httpcore.NetworkError,
            httpcore.ProtocolError,
            RainViewerPinningError,
        ) as exc:
            raise RainViewerRadarServiceError() from exc
        return b"".join(chunks)

    def _validate_content_length(self, values: list[str]) -> None:
        if len(values) != 1:
            raise RainViewerRadarServiceError()
        content_length = values[0]
        if not content_length.isascii() or not content_length.isdecimal():
            raise RainViewerRadarServiceError()
        if len(content_length) > 1 and content_length.startswith("0"):
            raise RainViewerRadarServiceError()
        if int(content_length) > self._tile_body_limit_bytes:
            raise RainViewerRadarServiceError()

    async def _await_with_cancel(
        self, awaitable: Awaitable[Any], *, cancel_check: CancelCheck
    ) -> Any:
        task = asyncio.ensure_future(awaitable)
        try:
            while True:
                done, _ = await asyncio.wait(
                    {task}, timeout=self._cancel_poll_interval_seconds
                )
                if done:
                    return task.result()
                if await cancel_check():
                    task.cancel()
                    with suppress(BaseException):
                        await task
                    raise asyncio.CancelledError()
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
                with suppress(BaseException):
                    await task
            raise

    async def _close_response(self, response: httpx.Response) -> None:
        try:
            await response.aclose()
        except httpx.TimeoutException as exc:
            raise RainViewerRadarTimeoutError() from exc
        except httpcore.TimeoutException as exc:
            raise RainViewerRadarTimeoutError() from exc
        except asyncio.CancelledError:
            raise
        except (
            httpx.HTTPError,
            httpcore.NetworkError,
            httpcore.ProtocolError,
            RainViewerPinningError,
        ) as exc:
            raise RainViewerRadarServiceError() from exc

    async def _raise_if_disconnected(self, cancel_check: CancelCheck) -> None:
        if await cancel_check():
            raise asyncio.CancelledError()
