"""Real main.app/lifespan; replace only weather resolver and TLS stream I/O."""

import os

import main
from app.services.overview_weather.transport import PinnedWeatherTransport
from fastapi.staticfiles import StaticFiles
from provider_fixture import open_tls, resolve


def transport(clock):
    return PinnedWeatherTransport(clock, resolver=resolve, opener=open_tls)


main.PinnedWeatherTransport = transport
app = main.app
if os.environ.get("WEATHER_ACCEPTANCE_MODE") == "comparison":
    app.mount(
        "/api/overview-weather/comparison-assets",
        StaticFiles(directory="/capture"),
        name="comparison-captures",
    )


# Only acceptance controls can choose a normalized fixture source or historical
# replay epoch. Production WeatherService/transport/admission/freshness stay real.
import time

from app.services.overview_weather.clock import WeatherClock
from app.services.overview_weather.rainviewer import RainViewerAdapter
from app.services.overview_weather.service import WeatherService
from provider_fixture import control

replay_anchor = None


def fixture_utc_ms():
    global replay_anchor
    epoch = control().get("replay_utc_ms")
    if epoch is None:
        replay_anchor = None
        return int(time.time() * 1000)
    if replay_anchor is None or replay_anchor[0] != epoch:
        replay_anchor = (epoch, time.monotonic())
    return int(epoch + (time.monotonic() - replay_anchor[1]) * 1000)


class FixtureAdapter:
    metadata_url = RainViewerAdapter.metadata_url
    observed_frames = staticmethod(RainViewerAdapter.observed_frames)
    tile_url = staticmethod(RainViewerAdapter.tile_url)

    @property
    def max_zoom(self):
        return control().get("max_zoom", 7)

    def normalized(self):
        settings = control()
        result = RainViewerAdapter(
            source=settings.get("source", "rainviewer"),
            provenance=settings.get("provenance", "RainViewer observed radar"),
            max_zoom=self.max_zoom,
        ).normalized()
        if result["source"] != "rainviewer":
            result["attribution"] = {
                "label": "Fixture radar",
                "url": "https://example.com/radar",
            }
        return result


class FixtureWeatherService(WeatherService):
    def __init__(self, store, pool, clock):
        super().__init__(store, pool, clock, adapter=FixtureAdapter())


main.WeatherService = FixtureWeatherService
main.WeatherClock = lambda: WeatherClock(utc_ms=fixture_utc_ms)
