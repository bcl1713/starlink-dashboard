"""RainViewer radar provider contract and response I/O helpers."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from tempfile import SpooledTemporaryFile
from typing import Any, NoReturn

import httpcore
import httpx
from httpx import StreamConsumed

RAINVIEWER_METADATA_URL = "https://api.rainviewer.com/public/weather-maps.json"
RAINVIEWER_TILE_HOST = "tilecache.rainviewer.com"
RAINVIEWER_TILE_SIZE = 512
RAINVIEWER_COLOR_SCHEME = 2
RAINVIEWER_OPTIONS = "1_1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
FRAME_PATH_RE = re.compile(r"^/v2/radar/(0|[1-9][0-9]*)$")
TIMEOUT_ERRORS = (httpx.TimeoutException, httpcore.TimeoutException)
RADAR_IO_ERRORS = (
    httpx.HTTPError,
    httpcore.NetworkError,
    httpcore.ProtocolError,
    RuntimeError,
)
SYSTEM_EXIT_ERRORS = (
    asyncio.CancelledError,
    GeneratorExit,
    KeyboardInterrupt,
    SystemExit,
)

CancelCheck = Callable[[], Awaitable[bool]]

# fmt: off
class InvalidRadarTileError(ValueError): ...
class RainViewerRadarServiceError(RuntimeError): ...
class RainViewerRadarTimeoutError(RainViewerRadarServiceError): ...
# fmt: on


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


def tile_url(frame: RadarFrame, z: int, x: int, y: int) -> str:
    validate_frame_path(frame.path)
    return (
        f"https://{RAINVIEWER_TILE_HOST}{frame.path}/"
        f"{RAINVIEWER_TILE_SIZE}/{z}/{x}/{y}/"
        f"{RAINVIEWER_COLOR_SCHEME}/{RAINVIEWER_OPTIONS}.png"
    )


def validate_url(url: str, expected_url: str) -> str:
    if url != expected_url:
        raise RainViewerRadarServiceError()
    return url


def resolve_redirect(current: str, location: str) -> str:
    if any(char in location for char in ("\r", "\n", "\t", " ")):
        raise RainViewerRadarServiceError()
    if location.startswith("https://"):
        return location
    if location.startswith("/"):
        if current == RAINVIEWER_METADATA_URL:
            return f"https://api.rainviewer.com{location}"
        return f"https://tilecache.rainviewer.com{location}"
    raise RainViewerRadarServiceError()


def validate_frame_path(path: str) -> None:
    if FRAME_PATH_RE.fullmatch(path) is None:
        raise RainViewerRadarServiceError()


async def raise_if_disconnected(cancel_check: CancelCheck) -> None:
    if await cancel_check():
        raise asyncio.CancelledError()


async def await_with_cancel(
    awaitable: Awaitable[Any],
    *,
    cancel_check: CancelCheck,
    poll_interval_seconds: float,
) -> Any:
    task = asyncio.ensure_future(awaitable)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=poll_interval_seconds)
            if done:
                return task.result()
            if await cancel_check():
                task.cancel()
                with suppress(BaseException):
                    await task
                raise asyncio.CancelledError()
    except BaseException:
        if not task.done():
            task.cancel()
            with suppress(BaseException):
                await task
        raise


async def consume_tile_response(
    response: httpx.Response,
    *,
    frame_timestamp: int,
    cancel_check: CancelCheck,
    body_limit_bytes: int,
    poll_interval_seconds: float,
) -> RadarTile:
    tile: RadarTile | None = None
    try:
        tile = await _consume_tile_body(
            response,
            frame_timestamp=frame_timestamp,
            cancel_check=cancel_check,
            body_limit_bytes=body_limit_bytes,
            poll_interval_seconds=poll_interval_seconds,
        )
    except BaseException:
        with suppress(BaseException):
            await close_response(response)
        raise

    try:
        await close_response(response)
    except BaseException:
        tile.close()
        raise
    return tile


async def _close_suppressing(response: httpx.Response) -> None:
    with suppress(BaseException):
        await close_response(response)


async def consume_metadata_response(
    response: httpx.Response,
    *,
    limit_bytes: int,
    parse: Callable[[Any], RadarFrame],
) -> RadarFrame:
    try:
        raw = await _consume_limited_raw(response, limit_bytes)
        metadata = json.loads(raw.decode("utf-8"))
        frame = parse(metadata)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        await _close_suppressing(response)
        raise RainViewerRadarServiceError() from exc
    except BaseException:
        await _close_suppressing(response)
        raise

    await close_response(response)
    return frame


async def close_response(response: httpx.Response) -> None:
    try:
        await response.aclose()
    except TIMEOUT_ERRORS as exc:
        raise RainViewerRadarTimeoutError() from exc
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        raise RainViewerRadarServiceError() from exc


def _raise_consumption_error(
    exc: BaseException, spool: SpooledTemporaryFile[bytes] | None = None
) -> NoReturn:
    if spool is not None:
        spool.close()
    if isinstance(exc, TIMEOUT_ERRORS):
        raise RainViewerRadarTimeoutError() from exc
    if isinstance(exc, asyncio.CancelledError):
        raise exc
    if isinstance(exc, Exception):
        raise RainViewerRadarServiceError() from exc
    raise exc


async def _consume_tile_body(
    response: httpx.Response,
    *,
    frame_timestamp: int,
    cancel_check: CancelCheck,
    body_limit_bytes: int,
    poll_interval_seconds: float,
) -> RadarTile:
    content_lengths = response.headers.get_list("content-length")
    if content_lengths:
        _validate_content_length(content_lengths, body_limit_bytes)
    content_type = response.headers.get("content-type", "").split(";", 1)[0]
    if content_type.strip().lower() != "image/png":
        raise RainViewerRadarServiceError()

    spool: SpooledTemporaryFile[bytes] = SpooledTemporaryFile(  # noqa: SIM115
        max_size=body_limit_bytes
    )
    size = 0
    try:
        try:
            iterator = response.aiter_raw().__aiter__()
            while True:
                try:
                    chunk = await await_with_cancel(
                        iterator.__anext__(),
                        cancel_check=cancel_check,
                        poll_interval_seconds=poll_interval_seconds,
                    )
                except StopAsyncIteration:
                    break
                await raise_if_disconnected(cancel_check)
                size += len(chunk)
                if size > body_limit_bytes:
                    raise RainViewerRadarServiceError()
                spool.write(chunk)
        except StreamConsumed:
            content = response.content
            size = len(content)
            if size > body_limit_bytes:
                raise RainViewerRadarServiceError()
            spool.write(content)
        spool.seek(0)
        if spool.read(len(PNG_SIGNATURE)) != PNG_SIGNATURE:
            raise RainViewerRadarServiceError()
        spool.seek(0)
        return RadarTile(spool=spool, size_bytes=size, frame_timestamp=frame_timestamp)
    except TIMEOUT_ERRORS as exc:
        _raise_consumption_error(exc, spool)
    except RADAR_IO_ERRORS as exc:
        _raise_consumption_error(exc, spool)
    except SYSTEM_EXIT_ERRORS as exc:
        _raise_consumption_error(exc, spool)


async def _consume_limited_raw(response: httpx.Response, limit: int) -> bytes:
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
    except TIMEOUT_ERRORS as exc:
        _raise_consumption_error(exc)
    except RADAR_IO_ERRORS as exc:
        _raise_consumption_error(exc)
    except SYSTEM_EXIT_ERRORS as exc:
        _raise_consumption_error(exc)
    return b"".join(chunks)


def _validate_content_length(values: list[str], body_limit_bytes: int) -> None:
    if len(values) != 1:
        raise RainViewerRadarServiceError()
    content_length = values[0]
    if not content_length.isascii() or not content_length.isdecimal():
        raise RainViewerRadarServiceError()
    if len(content_length) > 1 and content_length.startswith("0"):
        raise RainViewerRadarServiceError()
    if int(content_length) > body_limit_bytes:
        raise RainViewerRadarServiceError()
