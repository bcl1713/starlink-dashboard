"""Transport must keep acquisition bounded before normalization begins."""

import gzip
import zlib

import httpx
import pytest

from app.services.aviation_weather.transport import MAX_SOURCE_BYTES, AwcTransport
from app.services.aviation_weather.worker import expand_gzip
from app.services.overview_weather.protocol import WeatherUnavailable


async def test_fixed_source_user_agent_and_gzip_bytes_are_preserved():
    captured = []
    body = gzip.compress(b"<response/>")

    async def upstream(request):
        captured.append(request)
        return httpx.Response(
            200,
            headers={"Content-Type": "application/octet-stream"},
            stream=httpx.ByteStream(body),
        )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(upstream),
        follow_redirects=False,
        headers={
            "User-Agent": "starlink-dashboard/aviation-weather-v1",
            "Accept-Encoding": "identity",
        },
    )
    transport = AwcTransport(client)
    attempts = []
    assert await transport.fetch("metar", lambda: attempts.append(True)) == body
    assert (
        str(captured[0].url)
        == "https://aviationweather.gov/data/cache/metars.cache.xml.gz"
    )
    assert captured[0].headers["accept-encoding"] == "identity"
    assert len(attempts) == 1
    assert expand_gzip(body) == b"<response/>"
    await transport.aclose()


@pytest.mark.parametrize(
    "status,headers",
    [
        (302, {"location": "https://localhost/private"}),
        (200, {"content-type": "text/html"}),
        (200, {"content-type": "application/json", "content-encoding": "gzip"}),
        (
            200,
            {
                "content-type": "application/json",
                "content-length": str(MAX_SOURCE_BYTES + 1),
            },
        ),
        (429, {"retry-after": "120"}),
    ],
)
async def test_redirect_content_encoding_mime_and_body_bounds_fail_closed(
    status, headers
):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(status, headers=headers, content=b"{}")
        )
    )
    transport = AwcTransport(client)
    with pytest.raises(WeatherUnavailable):
        await transport.fetch("sigmet", lambda: None)
    await transport.aclose()


@pytest.mark.parametrize(
    "body",
    [b"not-gzip", gzip.compress(b"x") + gzip.compress(b"y"), gzip.compress(b"x")[:-2]],
)
def test_expansion_rejects_invalid_trailing_and_truncated_gzip(body):
    with pytest.raises((ValueError, zlib.error)):
        expand_gzip(body)
