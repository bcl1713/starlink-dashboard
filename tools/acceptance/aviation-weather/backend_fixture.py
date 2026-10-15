"""Production lifespan and normalizer; only fixed-source transport is substituted."""

import importlib.util
import json
import os
import sys
from pathlib import Path

# Reuse radar controls with the actual optional-service lifecycle.
sys.path.insert(0, "/radar-acceptance")
path = Path("/radar-acceptance/backend_fixture.py")
spec = importlib.util.spec_from_file_location("radar_acceptance_backend", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
main = module.main
from app.services.aviation_weather.runtime import AviationWeatherService
from app.services.overview_weather.protocol import WeatherUnavailable


class FixtureAwcTransport:
    def __init__(self):
        self.closed = False

    async def fetch(self, layer, before_attempt):
        before_attempt()
        control = json.loads(Path("/control/control.json").read_text())
        event = {
            "layer": layer,
            "source_generation": control.get("aviation_generation", 0),
        }
        with Path("/control/aviation-events.jsonl").open("a") as stream:
            stream.write(json.dumps(event) + "\n")
        if control.get("aviation_failure"):
            raise WeatherUnavailable()
        filename = {
            "metar": "metars.xml.gz",
            "taf": "tafs.xml.gz",
            "sigmet": "sigmets.json",
        }[layer]
        return (Path("/capture") / filename).read_bytes()

    async def aclose(self):
        self.closed = True


class FixtureAviationService(AviationWeatherService):
    def __init__(self, store, transport):
        # Match replay clock only in this explicit test process.
        super().__init__(store, transport, utc_ms=module.fixture_utc_ms)


main.AwcTransport = FixtureAwcTransport
main.AviationWeatherService = FixtureAviationService
app = main.app
