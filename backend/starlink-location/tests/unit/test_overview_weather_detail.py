"""Detail delivery remains canonical, normalized and subordinate to coarse work."""

import asyncio
import struct

import httpx
import pytest
from app.services.overview_weather.admission import WeatherAdmission
from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.protocol import WeatherUnavailable
from app.services.overview_weather.service import WeatherService, WeatherTileError

from tests.fixtures.weather_streams import WeatherStreams, http_response
from tests.unit.test_overview_weather_api import weather_app
from tests.unit.test_overview_weather_service import metadata, service_for


@pytest.mark.parametrize("xyz", [(2, 3, 3), (7, 127, 127)])
async def test_detail_delivers_admitted_product_with_canonical_xyz(tmp_path, xyz):
    streams = WeatherStreams(http_response(metadata()))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    try:
        ready = await service.read_frame()
        assert ready.max_zoom == 7
        assert ready.source == "rainviewer"
        assert ready.tile_schema == "xyz-rgba-pair-v1"
        assert ready.coverage_encoding == "absence-rgba-v1"
        assert len(ready.product_id) == 64
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"
            + struct.pack(">II", 512, 512)
            + bytes(9)
        )
        streams.wire = http_response(png, "image/png")
        app = weather_app(service, store)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            z, x, y = xyz
            path = f"/api/overview-weather/radar/1791244200/{z}/{x}/{y}.png"
            assert (
                await client.get(path, params={"product_id": ready.product_id})
            ).content == png
            assert f"/512/{z}/{x}/{y}/2/1_1.png".encode() in streams.writers[-1].written
    finally:
        await service.aclose()


@pytest.mark.parametrize(
    "xyz",
    [
        (1, 0, 0),
        (8, 0, 0),
        (2, -1, 0),
        (2, 4, 0),
        (7, 128, 0),
        (7, 0, 128),
        (True, 0, 0),
        (2, 0.5, 0),
    ],
)
def test_internal_coordinate_bounds_are_strict(xyz):
    with pytest.raises(WeatherTileError):
        WeatherService._coordinates(*xyz)


@pytest.mark.parametrize(
    "coords", ["02/0/0", "+2/0/0", "2/00/0", "2/0/0.0", "7/128/0", "8/0/0", "2/-1/0"]
)
async def test_noncanonical_api_coordinates_never_dial(tmp_path, coords):
    streams = WeatherStreams(http_response(metadata()))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    try:
        ready = await service.read_frame()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(weather_app(service, store)),
            base_url="http://test",
        ) as client:
            result = await client.get(
                f"/api/overview-weather/radar/1791244200/{coords}.png",
                params={"product_id": ready.product_id},
            )
            assert result.status_code == 400
        assert len(streams.dials) == 1
    finally:
        await service.aclose()


def test_detail_attempt_subset_reserves_remaining_budget_for_coarse():
    now = [0.0]
    admission = WeatherAdmission(WeatherClock(monotonic=lambda: now[0]))
    for _ in range(30):
        admission.take_attempt(detail=True)
    with pytest.raises(WeatherUnavailable):
        admission.take_attempt(detail=True)
    for _ in range(60):
        admission.take_attempt()
    with pytest.raises(WeatherUnavailable):
        admission.take_attempt()
    now[0] = 60
    admission.take_attempt(detail=True)


async def test_detail_concurrency_and_priority_with_cancelled_waiters():
    admission = WeatherAdmission(WeatherClock())
    holds, order = {}, []

    async def job(name, detail):
        async with admission.admit(admission.clock.monotonic() + 5, detail=detail):
            order.append(name)
            event = holds.setdefault(name, asyncio.Event())
            await event.wait()

    tasks = [asyncio.create_task(job(str(i), i < 3)) for i in range(5)]
    try:
        for _ in range(10):
            await asyncio.sleep(0)
        assert order == ["0", "1", "3", "4"]
        coarse = asyncio.create_task(job("coarse", False))
        tasks.append(coarse)
        await asyncio.sleep(0)
        holds["0"].set()
        for _ in range(5):
            await asyncio.sleep(0)
        assert order[-1] == "coarse"
        tasks[2].cancel()
        await asyncio.gather(tasks[2], return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert admission._pending == 0


async def test_product_identity_is_stable_for_provenance_and_isolates_source_cache(
    tmp_path,
):
    from dataclasses import replace

    streams = WeatherStreams(http_response(metadata()))
    service, store = service_for(tmp_path, streams)
    store.update({"enabled": True})
    try:
        first = await service.read_frame()
        service.adapter = replace(service.adapter, provenance="RainViewer")
        wording = await service.read_frame()
        assert wording.product_id == first.product_id
        assert wording.radar_tile_template == first.radar_tile_template
        assert len(streams.dials) == 1
        service.adapter = replace(service.adapter, source="fixture-radar", max_zoom=5)
        changed = await service.read_frame()
        assert changed.product_id != first.product_id
        assert changed.frame_time_ms == first.frame_time_ms
        assert len(streams.dials) == 2
        with pytest.raises(WeatherTileError) as caught:
            await service.radar_tile(1791244200, 2, 0, 0, first.product_id)
        assert caught.value.status_code == 404
        assert len(streams.dials) == 2
    finally:
        await service.aclose()


@pytest.mark.parametrize(
    "coords", ["02/0/0", "2/4/0", "7/128/0", "7/0/128", "7/00/0", "8/0/0"]
)
async def test_transport_rejects_noncanonical_detail_before_dns(coords):
    from app.services.overview_weather.transport import PinnedWeatherTransport

    streams = WeatherStreams()
    clock = WeatherClock()
    from unittest.mock import AsyncMock

    resolver = AsyncMock(side_effect=streams.resolve)
    transport = PinnedWeatherTransport(clock, resolver, streams.open)
    with pytest.raises(WeatherUnavailable):
        await transport.fetch(
            f"https://tilecache.rainviewer.com/v2/radar/id/512/{coords}/2/1_1.png",
            2097152,
            "image/png",
            clock.monotonic() + 5,
            before_attempt=lambda: None,
        )
    assert streams.dials == []
    resolver.assert_not_awaited()
