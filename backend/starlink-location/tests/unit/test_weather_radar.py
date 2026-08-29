"""Tests for RainViewer weather radar fetching."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterable

import httpx
import pytest

from app.services.weather_radar import (
    InvalidRadarTileError,
    RainViewerRadarService,
    RainViewerRadarServiceError,
    RainViewerRadarTimeoutError,
)

PNG = b"\x89PNG\r\n\x1a\nradar"
METADATA = {
    "host": "https://tilecache.rainviewer.com",
    "radar": {
        "past": [
            {"time": 1710001000, "path": "/v2/radar/1710001000"},
            {"time": 1710001600, "path": "/v2/radar/1710001600"},
        ],
        "nowcast": [{"time": 1710001500, "path": "/v2/radar/1710001500"}],
    },
}


def _json_response(data: object) -> httpx.Response:
    return httpx.Response(200, content=json.dumps(data).encode("utf-8"))


def _png_response(
    content: bytes = PNG, headers: dict[str, str] | None = None
) -> httpx.Response:
    merged = {"Content-Type": "image/png"}
    if headers:
        merged.update(headers)
    return httpx.Response(200, content=content, headers=merged)


class ScriptedTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: Iterable[httpx.Response | BaseException]) -> None:
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []
        self.closed = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("unexpected request")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        response.request = request
        return response

    async def aclose(self) -> None:
        self.closed += 1


class ChunkStream(httpx.AsyncByteStream):
    def __init__(self, chunks: list[bytes]) -> None:
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            await asyncio.sleep(0)
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


class BlockingTransport(ScriptedTransport):
    def __init__(self, release: asyncio.Event) -> None:
        super().__init__([])
        self.release = release
        self.cancelled = 0
        self.metadata_started = asyncio.Event()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "api.rainviewer.com":
            self.metadata_started.set()
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            return _json_response(METADATA)
        return _png_response()


class BlockingBodyStream(httpx.AsyncByteStream):
    def __init__(self, first_chunk: bytes, release: asyncio.Event) -> None:
        self.first_chunk = first_chunk
        self.release = release
        self.closed = False
        self.cancelled = 0

    async def __aiter__(self):
        yield self.first_chunk
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise
        yield b"tail"

    async def aclose(self) -> None:
        self.closed = True


def _service(
    transport: ScriptedTransport,
    *,
    now: list[float] | None = None,
    metadata_cache_ttl_seconds: float = 60,
) -> RainViewerRadarService:
    clock = (lambda: now[0]) if now is not None else None
    client = httpx.AsyncClient(transport=transport, follow_redirects=False)
    return RainViewerRadarService(
        client=client,
        metadata_cache_ttl_seconds=metadata_cache_ttl_seconds,
        clock=clock,
        tile_body_limit_bytes=32,
        metadata_body_limit_bytes=256,
        cancel_poll_interval_seconds=0.001,
    )


async def _not_disconnected() -> bool:
    return False


async def _wait_until(condition, *, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition was not reached")
        await asyncio.sleep(0)


async def _fetch(service: RainViewerRadarService, z=3, x=4, y=5):
    tile = await service.fetch_tile(z, x, y, _not_disconnected)
    try:
        return tile.read()
    finally:
        tile.close()


@pytest.mark.asyncio
async def test_fetch_tile_returns_png_bytes_and_provider_frame_timestamp() -> None:
    transport = ScriptedTransport([_json_response(METADATA), _png_response()])
    service = _service(transport)

    tile = await service.fetch_tile(3, 4, 5, _not_disconnected)
    try:
        assert tile.read() == PNG
        assert tile.frame_timestamp == 1710001600
        assert transport.requests[0].url == (
            "https://api.rainviewer.com/public/weather-maps.json"
        )
        assert transport.requests[0].headers["accept-encoding"] == "identity"
        assert transport.requests[1].url == (
            "https://tilecache.rainviewer.com/v2/radar/1710001600/"
            "512/3/4/5/2/1_1.png"
        )
    finally:
        tile.close()
        await service.aclose()


@pytest.mark.asyncio
async def test_xyz_validation_happens_before_upstream_work() -> None:
    transport = ScriptedTransport([])
    service = _service(transport)

    with pytest.raises(InvalidRadarTileError):
        await service.fetch_tile(8, 0, 0, _not_disconnected)
    with pytest.raises(InvalidRadarTileError):
        await service.fetch_tile(3, 8, 0, _not_disconnected)

    assert transport.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {"host": "http://tilecache.rainviewer.com", "radar": {"past": []}},
        {"host": "https://evil.example", "radar": {"past": []}},
        {"host": "https://tilecache.rainviewer.com", "radar": {}},
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": "soon", "path": "/v2/radar/a"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "https://evil.example/a"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "/bad/a"}]},
        },
    ],
)
async def test_rejects_malformed_metadata(metadata) -> None:
    service = _service(ScriptedTransport([_json_response(metadata)]))

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(0, 0, 0, _not_disconnected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": True, "path": "/v2/radar/1"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "/v2/radar/01"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "/v2/radar/1/extra"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "/v2/radar/%2e%2e/%2fescape"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "/v2/radar/a b"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com",
            "radar": {"past": [{"time": 1, "path": "/v2/radar/"}]},
        },
        {
            "host": "https://tilecache.rainviewer.com.",
            "radar": {"past": [{"time": 1, "path": "/v2/radar/1"}]},
        },
    ],
)
async def test_rejects_noncanonical_metadata_contract_values(metadata) -> None:
    service = _service(ScriptedTransport([_json_response(metadata)]))

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(0, 0, 0, _not_disconnected)


@pytest.mark.asyncio
async def test_rejects_oversize_metadata_body() -> None:
    response = httpx.Response(200, content=b"x" * 300)
    service = _service(ScriptedTransport([response]))

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(0, 0, 0, _not_disconnected)


@pytest.mark.asyncio
async def test_metadata_cache_uses_injected_clock_and_preserves_provider_time() -> None:
    now = [10.0]
    newer = {
        "host": "https://tilecache.rainviewer.com",
        "radar": {"past": [{"time": 1710002222, "path": "/v2/radar/1710002222"}]},
    }
    transport = ScriptedTransport(
        [
            _json_response(METADATA),
            _png_response(),
            _png_response(),
            _json_response(newer),
            _png_response(),
        ]
    )
    service = _service(transport, now=now, metadata_cache_ttl_seconds=5)

    first = await service.fetch_tile(0, 0, 0, _not_disconnected)
    first.close()
    now[0] = 14.0
    second = await service.fetch_tile(0, 0, 0, _not_disconnected)
    second.close()
    now[0] = 16.0
    third = await service.fetch_tile(0, 0, 0, _not_disconnected)
    third.close()

    assert [request.url.host for request in transport.requests].count(
        "api.rainviewer.com"
    ) == 2
    assert second.frame_timestamp == 1710001600
    assert third.frame_timestamp == 1710002222


@pytest.mark.asyncio
async def test_metadata_fetch_is_single_flight_for_concurrent_callers() -> None:
    release = asyncio.Event()
    calls = 0

    class BarrierTransport(ScriptedTransport):
        def __init__(self) -> None:
            super().__init__([])
            self.metadata_started = asyncio.Event()

        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            nonlocal calls
            self.requests.append(request)
            if request.url.host == "api.rainviewer.com":
                calls += 1
                self.metadata_started.set()
                await release.wait()
                return _json_response(METADATA)
            return _png_response()

    transport = BarrierTransport()
    service = _service(transport)
    tasks = [
        asyncio.create_task(service.fetch_tile(0, 0, 0, _not_disconnected))
        for _ in range(20)
    ]
    await asyncio.wait_for(transport.metadata_started.wait(), timeout=1)
    release.set()
    tiles = await asyncio.gather(*tasks)

    assert calls == 1
    for tile in tiles:
        tile.close()


@pytest.mark.asyncio
async def test_manual_redirect_policy_validates_each_hop_and_exhaustion() -> None:
    service = _service(
        ScriptedTransport(
            [
                httpx.Response(302, headers={"Location": "/public/weather-maps.json"}),
                _json_response(METADATA),
                httpx.Response(
                    302,
                    headers={"Location": "/v2/radar/1710001600/512/3/4/5/2/1_1.png"},
                ),
                _png_response(),
            ]
        )
    )

    assert await _fetch(service) == PNG

    bad = _service(
        ScriptedTransport(
            [
                _json_response(METADATA),
                httpx.Response(302, headers={"Location": "https://evil.example/a"}),
            ]
        )
    )
    with pytest.raises(RainViewerRadarServiceError):
        await bad.fetch_tile(3, 4, 5, _not_disconnected)

    exhausted = _service(
        ScriptedTransport(
            [
                _json_response(METADATA),
                httpx.Response(
                    302,
                    headers={"Location": "/v2/radar/1710001600/512/3/4/5/2/1_1.png"},
                ),
                httpx.Response(
                    302,
                    headers={"Location": "/v2/radar/1710001600/512/3/4/5/2/1_1.png"},
                ),
                httpx.Response(
                    302,
                    headers={"Location": "/v2/radar/1710001600/512/3/4/5/2/1_1.png"},
                ),
                httpx.Response(
                    302,
                    headers={"Location": "/v2/radar/1710001600/512/3/4/5/2/1_1.png"},
                ),
            ]
        )
    )
    with pytest.raises(RainViewerRadarServiceError):
        await exhausted.fetch_tile(3, 4, 5, _not_disconnected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location",
    [
        "https://API.RAINVIEWER.COM/public/weather-maps.json",
        "https://api.rainviewer.com.:443/public/weather-maps.json",
        "https://api.rainviewer.com:443/public/weather-maps.json",
        "https://api.rainviewer.com/public/%77eather-maps.json",
        "https://api.rainviewer.com/public/weather-maps.json?x=1",
        "https://user@api.rainviewer.com/public/weather-maps.json",
        "/public/weather-maps.json%0d%0aX-Test: injected",
    ],
)
async def test_rejects_noncanonical_metadata_redirects(location: str) -> None:
    service = _service(
        ScriptedTransport([httpx.Response(302, headers={"Location": location})])
    )

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(0, 0, 0, _not_disconnected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "location",
    [
        (
            "https://tilecache.rainviewer.com:443/v2/radar/1710001600/"
            "512/3/4/5/2/1_1.png"
        ),
        ("https://TILECACHE.RAINVIEWER.COM/v2/radar/1710001600/" "512/3/4/5/2/1_1.png"),
        "/v2/radar/1710001600/512/3/4/5/2/1_1.png?x=1",
        "/v2/radar/1710001600/512/3/4/5/2/1_1.png#frag",
        "/v2/radar/1710001600/512/3/4/5/2/1_1%2epng",
    ],
)
async def test_rejects_noncanonical_tile_redirects(location: str) -> None:
    service = _service(
        ScriptedTransport(
            [
                _json_response(METADATA),
                httpx.Response(302, headers={"Location": location}),
            ]
        )
    )

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(3, 4, 5, _not_disconnected)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, content=PNG, headers={"Content-Type": "text/plain"}),
        httpx.Response(200, content=b"not-png", headers={"Content-Type": "image/png"}),
        httpx.Response(
            200,
            content=PNG,
            headers={"Content-Type": "image/png", "Content-Length": "33"},
        ),
        httpx.Response(500, content=b"no", headers={"Content-Type": "text/plain"}),
    ],
)
async def test_rejects_invalid_tile_responses(response) -> None:
    service = _service(ScriptedTransport([_json_response(METADATA), response]))

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(3, 4, 5, _not_disconnected)


@pytest.mark.asyncio
@pytest.mark.parametrize("content_length", ["-1", "+1", " 1 ", "1, 2", "01"])
async def test_rejects_noncanonical_content_length(content_length: str) -> None:
    response = _png_response(headers={"Content-Length": content_length})
    service = _service(ScriptedTransport([_json_response(METADATA), response]))

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(3, 4, 5, _not_disconnected)


@pytest.mark.asyncio
async def test_irregular_raw_chunks_crossing_tile_cap_close_response() -> None:
    stream = ChunkStream([PNG, b"a" * 20, b"b" * 20])
    response = httpx.Response(200, headers={"Content-Type": "image/png"}, stream=stream)
    service = _service(ScriptedTransport([_json_response(METADATA), response]))

    with pytest.raises(RainViewerRadarServiceError):
        await service.fetch_tile(3, 4, 5, _not_disconnected)

    assert stream.closed is True


@pytest.mark.asyncio
async def test_disconnect_cancellation_closes_response_stream() -> None:
    stream = ChunkStream([PNG, b"payload"])
    response = httpx.Response(200, headers={"Content-Type": "image/png"}, stream=stream)
    service = _service(ScriptedTransport([_json_response(METADATA), response]))
    calls = 0

    async def disconnected() -> bool:
        nonlocal calls
        calls += 1
        return calls > 1

    with pytest.raises(asyncio.CancelledError):
        await service.fetch_tile(3, 4, 5, disconnected)

    assert stream.closed is True


@pytest.mark.asyncio
async def test_disconnect_while_waiting_for_metadata_headers_cancels_upstream() -> None:
    release = asyncio.Event()
    transport = BlockingTransport(release)
    service = _service(transport)
    disconnect = asyncio.Event()

    async def disconnected() -> bool:
        return disconnect.is_set()

    task = asyncio.create_task(service.fetch_tile(0, 0, 0, disconnected))
    while not transport.requests:
        await asyncio.sleep(0)
    disconnect.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert transport.cancelled == 1
    assert service._metadata_task is None


@pytest.mark.asyncio
async def test_one_cancelled_metadata_waiter_does_not_cancel_shared_task() -> None:
    release = asyncio.Event()
    transport = BlockingTransport(release)
    service = _service(transport)
    disconnected = asyncio.Event()

    async def first_disconnected() -> bool:
        return disconnected.is_set()

    first = asyncio.create_task(service.fetch_tile(0, 0, 0, first_disconnected))
    second = asyncio.create_task(service.fetch_tile(0, 0, 0, _not_disconnected))
    while service._metadata_waiters < 2:
        await asyncio.sleep(0)

    disconnected.set()
    with pytest.raises(asyncio.CancelledError):
        await first

    assert transport.cancelled == 0
    release.set()
    tile = await second
    tile.close()


@pytest.mark.asyncio
async def test_all_metadata_waiters_disconnect_cancel_upstream_once() -> None:
    release = asyncio.Event()
    transport = BlockingTransport(release)
    service = _service(transport)
    disconnect = asyncio.Event()

    async def disconnected() -> bool:
        return disconnect.is_set()

    tasks = [
        asyncio.create_task(service.fetch_tile(0, 0, 0, disconnected)) for _ in range(3)
    ]
    await asyncio.wait_for(transport.metadata_started.wait(), timeout=1)
    await _wait_until(lambda: service._metadata_waiters == 3)
    disconnect.set()

    for task in tasks:
        with pytest.raises(asyncio.CancelledError):
            await task

    assert transport.cancelled == 1
    assert service._metadata_task is None
    assert service._metadata_waiters == 0


@pytest.mark.asyncio
async def test_disconnect_while_waiting_for_tile_headers_cancels_upstream() -> None:
    release = asyncio.Event()

    class TileBlockingTransport(BlockingTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            if request.url.host == "api.rainviewer.com":
                return _json_response(METADATA)
            try:
                await self.release.wait()
            except asyncio.CancelledError:
                self.cancelled += 1
                raise
            raise AssertionError("tile request should have been cancelled")

    transport = TileBlockingTransport(release)
    service = _service(transport)
    disconnect = asyncio.Event()

    async def disconnected() -> bool:
        return disconnect.is_set()

    task = asyncio.create_task(service.fetch_tile(0, 0, 0, disconnected))
    while len(transport.requests) < 2:
        await asyncio.sleep(0)
    disconnect.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert transport.cancelled == 1


@pytest.mark.asyncio
async def test_disconnect_while_body_stalled_closes_stream_and_cancels_read() -> None:
    release = asyncio.Event()
    stream = BlockingBodyStream(PNG, release)
    response = httpx.Response(200, headers={"Content-Type": "image/png"}, stream=stream)
    service = _service(ScriptedTransport([_json_response(METADATA), response]))
    disconnect = asyncio.Event()
    checks = 0

    async def disconnected() -> bool:
        nonlocal checks
        checks += 1
        return disconnect.is_set()

    task = asyncio.create_task(service.fetch_tile(0, 0, 0, disconnected))
    while checks < 2:
        await asyncio.sleep(0)
    disconnect.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert stream.closed is True
    assert stream.cancelled == 1


@pytest.mark.asyncio
async def test_plain_task_cancellation_remains_cancelled_error() -> None:
    release = asyncio.Event()
    transport = BlockingTransport(release)
    service = _service(transport)
    task = asyncio.create_task(service.fetch_tile(0, 0, 0, _not_disconnected))
    while not transport.requests:
        await asyncio.sleep(0)

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert transport.cancelled == 1


@pytest.mark.asyncio
async def test_timeout_maps_to_typed_timeout() -> None:
    service = _service(
        ScriptedTransport([httpx.ReadTimeout("do not leak upstream detail")])
    )

    with pytest.raises(RainViewerRadarTimeoutError):
        await service.fetch_tile(0, 0, 0, _not_disconnected)


@pytest.mark.asyncio
async def test_aclose_closes_owned_client_once() -> None:
    transport = ScriptedTransport([])
    service = _service(transport)

    await service.aclose()
    await service.aclose()

    assert transport.closed == 1
