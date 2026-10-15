"""Subscriber demand, deadlines and bounded budgets control actual exchanges."""

import asyncio

import pytest

from app.services.overview_weather.acquisitions import WeatherAcquisitionPool
from app.services.overview_weather.admission import WeatherAdmission
from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.protocol import WeatherUnavailable
from app.services.overview_weather.transport import PinnedWeatherTransport
from tests.fixtures.weather_streams import WeatherStreams, http_response

URL = "https://api.rainviewer.com/public/weather-maps.json"
KEY = ("metadata", 0, 0, 0, 0)


def pool_for(streams, clock=None):
    clock = clock or WeatherClock()
    return WeatherAcquisitionPool(
        PinnedWeatherTransport(clock, streams.resolve, streams.open),
        WeatherAdmission(clock),
        clock,
    )


async def acquire(pool, key=KEY, validate=lambda _: None):
    return await pool.acquire(key, URL, 131072, "application/json", 300, validate)


async def test_subscriber_cancel_keeps_sibling_then_last_release_closes_once():
    streams = WeatherStreams()
    pool = pool_for(streams)
    first = asyncio.create_task(acquire(pool))
    await streams.opened.wait()
    second = asyncio.create_task(acquire(pool))
    await asyncio.sleep(0)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    assert streams.writers[0].close_calls == 0
    assert not second.done()
    second.cancel()
    with pytest.raises(asyncio.CancelledError):
        await second
    assert len(streams.dials) == 1
    assert streams.writers[0].close_calls == 1
    assert streams.writers[0].wait_closed_calls == 1
    await asyncio.gather(pool.aclose(), pool.aclose())
    assert streams.writers[0].close_calls == 1
    with pytest.raises(WeatherUnavailable):
        await acquire(pool)


async def test_invalidate_cancels_work_and_prevents_old_cache_publication():
    streams = WeatherStreams()
    pool = pool_for(streams)
    task = asyncio.create_task(acquire(pool))
    await streams.opened.wait()
    await pool.invalidate()
    with pytest.raises(WeatherUnavailable):
        await task
    assert streams.writers[0].close_calls == 1
    streams.wire = http_response(b'{"new":true}')
    assert (await acquire(pool)).body == b'{"new":true}'
    await pool.aclose()


async def test_invalid_payload_cooldown_and_success_ttl():
    now = [0.0]
    clock = WeatherClock(monotonic=lambda: now[0])
    streams = WeatherStreams(http_response())
    pool = pool_for(streams, clock)

    def invalid(_):
        raise ValueError("bad payload")

    for _ in range(2):
        with pytest.raises(WeatherUnavailable):
            await acquire(pool, validate=invalid)
    assert len(streams.dials) == 1
    now[0] = 30
    assert (await acquire(pool)).body == b"{}"
    now[0] = 329
    await acquire(pool)
    assert len(streams.dials) == 2
    now[0] = 330
    await acquire(pool)
    assert len(streams.dials) == 3
    await pool.aclose()


def test_rolling_attempt_budget_includes_failed_attempts():
    now = [0.0]
    admission = WeatherAdmission(WeatherClock(monotonic=lambda: now[0]))
    for _ in range(90):
        admission.take_attempt()
    with pytest.raises(WeatherUnavailable):
        admission.take_attempt()
    now[0] = 59.999
    with pytest.raises(WeatherUnavailable):
        admission.take_attempt()
    now[0] = 60
    admission.take_attempt()


async def test_four_active_and_thirty_two_pending_unique_limit():
    streams = WeatherStreams()
    pool = pool_for(streams)
    tasks = [
        asyncio.create_task(acquire(pool, ("metadata", n, 0, 0, 0))) for n in range(36)
    ]
    for _ in range(100):
        await asyncio.sleep(0)
        if len(streams.dials) == 4:
            break
    with pytest.raises(WeatherUnavailable):
        await acquire(pool, ("metadata", 99, 0, 0, 0))
    assert len(streams.dials) == 4
    await pool.aclose()
    await asyncio.gather(*tasks, return_exceptions=True)
    assert all(w.close_calls == w.wait_closed_calls == 1 for w in streams.writers)


@pytest.mark.parametrize("coarse_active", [0, 2])
async def test_saturated_detail_keeps_coarse_admission_and_priority(coarse_active):
    streams = WeatherStreams()
    pool = pool_for(streams)
    tasks = [
        asyncio.create_task(acquire(pool, ("product", "radar", n, 2, 0, 0)))
        for n in range(coarse_active)
    ]
    tasks += [
        asyncio.create_task(acquire(pool, ("product", "radar", n, 7, 0, 0)))
        for n in range(36)
    ]
    try:
        for _ in range(100):
            await asyncio.sleep(0)
        before = len(streams.dials)
        coarse = asyncio.create_task(
            acquire(pool, ("product", "metadata", 99, 0, 0, 0))
        )
        tasks.append(coarse)
        for _ in range(100):
            await asyncio.sleep(0)
        assert not coarse.done(), "detail saturation rejected coarse work"
        assert pool.admission._pending <= 32
        assert pool.admission._active <= 4
        assert pool.admission._detail_active <= 2
        if coarse_active:
            tasks[0].cancel()
            await asyncio.gather(tasks[0], return_exceptions=True)
            for _ in range(100):
                await asyncio.sleep(0)
        assert len(streams.dials) == before + 1
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await pool.aclose()
    assert all(writer.close_calls == 1 for writer in streams.writers)
    assert pool.admission._pending == 0


@pytest.mark.parametrize("count,body", [(49, b"small"), (33, b"x" * 2097152)])
async def test_png_cache_evicts_first_entry_at_count_or_byte_bound(count, body):
    streams = WeatherStreams(http_response(body))
    pool = pool_for(streams)
    for token in range(count):
        await pool.acquire(
            ("radar", token, 2, 0, 0),
            URL,
            2097152,
            "application/json",
            300,
            lambda _: None,
        )
    # The earliest entry cannot fit under either 48 entries or 64 MiB.
    await pool.acquire(
        ("radar", 0, 2, 0, 0), URL, 2097152, "application/json", 300, lambda _: None
    )
    assert len(streams.dials) == count + 1
    await pool.aclose()
