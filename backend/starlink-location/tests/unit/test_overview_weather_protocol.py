import asyncio

import pytest

from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.protocol import WeatherUnavailable, exchange_http
from tests.fixtures.weather_streams import WeatherWriter, http_response


async def exchange(wire, max_bytes=131072):
    reader = asyncio.StreamReader()
    reader.feed_data(wire)
    reader.feed_eof()
    clock = WeatherClock()
    return await exchange_http(
        reader,
        WeatherWriter(),
        "api.rainviewer.com",
        "/public/weather-maps.json",
        max_bytes,
        "application/json",
        clock.monotonic() + 5,
        clock,
    )


async def test_decodes_chunked_body():
    wire = (
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        b"Transfer-Encoding: chunked\r\n\r\n2\r\n{}\r\n0\r\n\r\n"
    )
    assert (await exchange(wire)).body == b"{}"


@pytest.mark.parametrize(
    "wire",
    [
        http_response(b"x" * 10),
        http_response(b"xx")[:-1],
        http_response(content_type="text/html"),
        http_response(status=302),
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 2\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n\r\n",
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Encoding: gzip\r\nContent-Length: 2\r\n\r\n{}",
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Huge: "
        + b"x" * 32768
        + b"\r\nContent-Length: 2\r\n\r\n{}",
    ],
)
async def test_rejects_unsafe_framing_or_payload(wire):
    with pytest.raises(WeatherUnavailable):
        await exchange(wire, max_bytes=4)


async def test_provider_retry_after_is_bounded():
    with pytest.raises(WeatherUnavailable) as caught:
        await exchange(
            b"HTTP/1.1 429 Busy\r\nRetry-After: 900\r\nContent-Length: 0\r\n\r\n"
        )
    assert caught.value.retry_after_seconds == 300
