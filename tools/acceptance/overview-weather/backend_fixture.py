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
        "/api/weather-comparison-assets",
        StaticFiles(directory="/capture"),
        name="comparison-captures",
    )
