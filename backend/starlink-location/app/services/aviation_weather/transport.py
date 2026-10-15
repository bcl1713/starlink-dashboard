"""Fixed AWC origins; bounded HTTPS bodies without redirects or URL input."""

import asyncio

import httpx

from app.services.overview_weather.protocol import WeatherUnavailable

SOURCES = {
    "metar": "https://aviationweather.gov/data/cache/metars.cache.xml.gz",
    "taf": "https://aviationweather.gov/data/cache/tafs.cache.xml.gz",
    "sigmet": "https://aviationweather.gov/api/data/isigmet?format=geojson",
}
MAX_SOURCE_BYTES = 8 * 1024**2


class AwcTransport:
    def __init__(self, client=None):
        self.client = client

    def _client(self):
        if self.client is None:
            self.client = httpx.AsyncClient(
                timeout=30,
                follow_redirects=False,
                headers={
                    "User-Agent": "starlink-dashboard/aviation-weather-v1",
                    "Accept-Encoding": "identity",
                },
                limits=httpx.Limits(max_connections=2, max_keepalive_connections=0),
            )
        return self.client

    async def fetch(self, layer, before_attempt):
        if layer not in SOURCES:
            raise WeatherUnavailable()
        try:
            before_attempt()
            async with asyncio.timeout(30):
                async with self._client().stream("GET", SOURCES[layer]) as response:
                    if response.status_code != 200:
                        delay = response.headers.get("retry-after", "30")
                        raise WeatherUnavailable(
                            int(delay) if delay.isdecimal() else 30
                        )
                    expected = (
                        {"application/geo+json", "application/json"}
                        if layer == "sigmet"
                        else {
                            "application/gzip",
                            "application/x-gzip",
                            "application/octet-stream",
                        }
                    )
                    if (
                        response.headers.get("content-type", "")
                        .split(";", 1)[0]
                        .strip()
                        .lower()
                        not in expected
                        or response.headers.get("content-encoding", "identity").lower()
                        != "identity"
                    ):
                        raise WeatherUnavailable()
                    length = response.headers.get("content-length")
                    if length is not None and (
                        not length.isdecimal() or int(length) > MAX_SOURCE_BYTES
                    ):
                        raise WeatherUnavailable()
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > MAX_SOURCE_BYTES:
                            raise WeatherUnavailable()
                        body.extend(chunk)
                    if not body:
                        raise WeatherUnavailable()
                    return bytes(body)
        except (httpx.HTTPError, TimeoutError, ValueError) as error:
            raise WeatherUnavailable() from error

    async def aclose(self):
        if self.client is not None:
            await self.client.aclose()
