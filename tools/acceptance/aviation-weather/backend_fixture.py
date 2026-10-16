"""Production lifespan and normalizer; only fixed-source transport is substituted."""

import asyncio
import importlib.util
import json
import sys
import time
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
        events_path = Path("/control/aviation-events.jsonl")
        with events_path.open("a") as stream:  # noqa: ASYNC230 - tiny fixture ledger
            stream.write(json.dumps(event) + "\n")
        if control.get("aviation_failure"):
            raise WeatherUnavailable()
        filename = {
            "metar": "metars.xml.gz",
            "taf": "tafs.xml.gz",
            "sigmet": "sigmets.json",
        }[layer]
        if layer == "sigmet":
            filename = control.get("sigmet_fixture", filename)
            if filename not in {
                "sigmets.json",
                "route-sigmets.json",
                "attention-sigmets.json",
                "encounter-sigmets.json",
                "new-sigmets.json",
                "amended-sigmets.json",
                "cancelled-sigmets.json",
                "reused-sigmets.json",
                "empty-sigmets.json",
                "real-sigmets.json",
            }:
                raise WeatherUnavailable()
        if control.get("aviation_delay_ms"):
            await asyncio.sleep(min(control["aviation_delay_ms"], 15000) / 1000)
        return (Path("/capture") / filename).read_bytes()

    async def aclose(self):
        self.closed = True


class FixtureAviationService(AviationWeatherService):
    def __init__(self, store, transport):
        # Fixture UTC is shared by acquisition and RouteSigmetService (which
        # reads weather.utc_ms); it is independent of simulation replay time.
        # Advance only refresh scheduling to exercise feed changes promptly.
        def scheduling_clock():
            control = json.loads(Path("/control/control.json").read_text())
            return time.monotonic() + control.get("aviation_generation", 0) * 600

        super().__init__(
            store, transport, utc_ms=module.fixture_utc_ms, monotonic=scheduling_clock
        )


main.AwcTransport = FixtureAwcTransport
main.AviationWeatherService = FixtureAviationService
app = main.app


# Only this acceptance image mounts this module. Exercise a same-geometry edit
# through the real route capture; production exposes no fixture control API.
from datetime import datetime, timedelta, timezone

from fastapi import Request

from app.mission.storage import get_active_leg_lock


@app.post("/api/__acceptance/route-encounter")
async def edit_encounter_plan(request: Request):
    change = await request.json()

    def edit():
        with get_active_leg_lock():
            route = request.app.state.route_manager.get_active_route()
            if route is None:
                raise ValueError("No active fixture route")
            for index, point in enumerate(route.points):
                if index in change.get("missing_indices", []):
                    point.expected_arrival_time = None
                elif point.expected_arrival_time is not None:
                    point.expected_arrival_time += timedelta(
                        milliseconds=change.get("offset_ms", 0)
                    )
                if "height" in change:
                    point.altitude = change["height"]
        return {"edited": True}

    return await asyncio.to_thread(edit)


class FixtureSimulationCoordinator(main.SimulationCoordinator):
    def get_current_telemetry(self):
        return self._controlled(super().get_current_telemetry())

    def update(self, replay_frame=None):
        return self._controlled(super().update(replay_frame=replay_frame))

    @staticmethod
    def _controlled(telemetry):
        if telemetry is None:
            return None
        control = json.loads(Path("/control/control.json").read_text())
        updates = {}
        if control.get("telemetry_altitude_ft") is not None:
            updates["altitude"] = float(control["telemetry_altitude_ft"])
        if control.get("live_flight"):
            live = control["live_flight"]
            now = datetime.now(timezone.utc)
            updates.update(
                latitude=live["latitude"],
                longitude=live["longitude"],
                speed=live["speed"],
                observed_at=now - timedelta(seconds=live.get("age", 0)),
                speed_observed_at=now - timedelta(seconds=live.get("speed_age", 0)),
            )
        if not updates:
            return telemetry
        return telemetry.model_copy(
            update={"position": telemetry.position.model_copy(update=updates)}
        )


main.SimulationCoordinator = FixtureSimulationCoordinator
