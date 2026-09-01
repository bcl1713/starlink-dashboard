"""RainViewer weather radar tile proxy service."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import httpcore
import httpx
from app.services.rainviewer_transport import (
    PinnedAsyncHTTPTransport,
    RainViewerPinningError,
)
from app.services.weather_radar_helpers import (
    RAINVIEWER_METADATA_URL,
    RAINVIEWER_TILE_HOST,
    CancelCheck,
    InvalidRadarTileError,
    RadarFrame,
    RadarTile,
    RainViewerRadarServiceError,
    RainViewerRadarTimeoutError,
    await_with_cancel,
    close_response,
    consume_metadata_response,
    consume_tile_response,
    raise_if_disconnected,
    resolve_redirect,
    tile_url,
    validate_frame_path,
    validate_url,
)

RAINVIEWER_MAX_ZOOM = 7
RAINVIEWER_MIN_FRAME_EPOCH = 946684800
RAINVIEWER_MAX_FRAME_EPOCH = 4102444800
RAINVIEWER_METADATA_HOST = "api.rainviewer.com"

__all__ = [
    "InvalidRadarTileError",
    "RadarTile",
    "RainViewerRadarService",
    "RainViewerRadarServiceError",
    "RainViewerRadarTimeoutError",
]


class _RainViewerHTTPXLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return (
            RAINVIEWER_METADATA_HOST not in message
            and RAINVIEWER_TILE_HOST not in message
        )


def validate_xyz(z: int, x: int, y: int) -> None:
    if z < 0 or z > RAINVIEWER_MAX_ZOOM:
        raise InvalidRadarTileError()
    upper = 2**z
    if x < 0 or y < 0 or x >= upper or y >= upper:
        raise InvalidRadarTileError()


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
        self._httpx_logger = logging.getLogger("httpx")
        self._httpx_log_filter = _RainViewerHTTPXLogFilter()
        self._httpx_logger.addFilter(self._httpx_log_filter)

    async def fetch_tile(
        self, z: int, x: int, y: int, cancel_check: CancelCheck
    ) -> RadarTile:
        """Fetch a validated PNG tile for XYZ coordinates."""
        validate_xyz(z, x, y)
        frame = await self._latest_frame(cancel_check)
        await raise_if_disconnected(cancel_check)
        url = tile_url(frame, z, x, y)
        response = await self._request_with_redirects(
            url,
            expected_url=url,
            headers={"Accept": "image/png", "Accept-Encoding": "identity"},
            cancel_check=cancel_check,
        )
        return await consume_tile_response(
            response,
            frame_timestamp=frame.timestamp,
            cancel_check=cancel_check,
            body_limit_bytes=self._tile_body_limit_bytes,
            poll_interval_seconds=self._cancel_poll_interval_seconds,
        )

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
        try:
            await self._client.aclose()
        finally:
            self._httpx_logger.removeFilter(self._httpx_log_filter)

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
            return await await_with_cancel(
                asyncio.shield(task),
                cancel_check=cancel_check,
                poll_interval_seconds=self._cancel_poll_interval_seconds,
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
        frame = await consume_metadata_response(
            response,
            limit_bytes=self._metadata_body_limit_bytes,
            parse=self._parse_metadata,
        )

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
        current = validate_url(url, expected_url)
        for _ in range(4):
            try:
                request = self._client.build_request("GET", current, headers=headers)
                send = self._client.send(request, stream=True, follow_redirects=False)
                if cancel_check is None:
                    response = await send
                else:
                    response = await await_with_cancel(
                        send,
                        cancel_check=cancel_check,
                        poll_interval_seconds=self._cancel_poll_interval_seconds,
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
            except Exception as exc:
                raise RainViewerRadarServiceError() from exc

            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("location")
                await close_response(response)
                if location is None:
                    raise RainViewerRadarServiceError()
                current = validate_url(
                    resolve_redirect(current, location), expected_url
                )
                continue
            if response.status_code != 200:
                await close_response(response)
                raise RainViewerRadarServiceError()
            return response
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
                validate_frame_path(path)
                if path.rsplit("/", 1)[-1] != str(timestamp):
                    raise RainViewerRadarServiceError()
                frames.append(RadarFrame(path=path, timestamp=timestamp))
        if not frames:
            raise RainViewerRadarServiceError()
        return max(frames, key=lambda frame: (frame.timestamp, frame.path))
