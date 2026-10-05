"""Real main.app/lifespan; replace only weather resolver and TLS stream I/O."""

import main
from app.services.overview_weather.transport import PinnedWeatherTransport
from provider_fixture import open_tls, resolve


def transport(clock):
    return PinnedWeatherTransport(clock, resolver=resolve, opener=open_tls)


main.PinnedWeatherTransport = transport
app = main.app
