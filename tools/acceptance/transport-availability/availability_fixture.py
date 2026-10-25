"""Synthetic raw clocks/catalogs only; use normal product startup and calculations."""

import asyncio
import importlib
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

from app.mission import storage
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore

if os.getenv("OPERATOR_ACCEPTANCE_FIXTURE") != "synthetic-local-only":
    raise RuntimeError("Private synthetic deployment required")
root = Path(os.environ["OPERATOR_ACCEPTANCE_ROOT"])
root.mkdir(parents=True, exist_ok=True)
storage.MISSIONS_DIR = root / "missions"
os.environ["OPERATOR_ROOT"] = str(root / "operator")


class InputClock:
    elapsed = 0.0
    start = datetime(2035, 3, 1, 12, tzinfo=timezone.utc)

    def now(self):
        return self.start + timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed


clock = InputClock()
coverage = Path("/app/data/sat_coverage")
coverage.mkdir(parents=True, exist_ok=True)
(coverage / "commka.geojson").write_text(
    json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"satellite_id": "AOR"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [[-20, -10], [2, -10], [2, 10], [-20, 10], [-20, -10]]
                        ],
                    },
                }
            ],
        }
    )
)
(root / "availability-pops.json").write_text(
    json.dumps(
        {
            "sites": [
                {
                    "id": identity,
                    "city": identity,
                    "country": "US",
                    "latitude": 0,
                    "longitude": longitude,
                    "source": "synthetic",
                    "coordinate_source": "synthetic",
                }
                for identity, longitude in (
                    ("synthetic-west", -8),
                    ("synthetic-east", 8),
                )
            ]
        }
    )
)
main = importlib.import_module("main")
original_binding = main.OperatorRuntimeBinding


def controlled_binding(**kwargs):
    return original_binding(**(kwargs | {"clock": clock}))


main.OperatorRuntimeBinding = controlled_binding
app = main.app
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    settings = OperatorSettings(
        enabled=True, root=root / "operator", source_mode="live"
    )
    store = OperatorStore.open(settings, initialize=True, clock=clock)
    store.close()
    async with original_lifespan(application):
        # Replace time INPUTS on the normal authoritative runtime, never its status.
        service = app.state.simulation_run_service
        service.runtime._monotonic = clock.monotonic
        service.runtime._utc_now = clock.now
        app.state.availability_clock = clock
        yield


app.router.lifespan_context = lifespan


@app.post("/api/_synthetic/transport-inputs")
async def inputs(body: dict):
    if set(body) - {"elapsed_seconds"}:
        raise HTTPException(422, "Only raw elapsed time is accepted")
    seconds = body.get("elapsed_seconds", clock.elapsed)
    if not isinstance(seconds, (float, int)) or seconds < clock.elapsed:
        raise HTTPException(422, "Time must advance")
    clock.elapsed = float(seconds)
    service = app.state.simulation_run_service
    sample = main._coordinator.get_current_telemetry().model_copy(deep=True)
    sample.position.latitude = 0
    sample.position.longitude = -10 + min(clock.elapsed, 3600) / 180
    sample.position.speed = 600
    sample.position.heading = 90
    sample.position.observed_at = clock.now()
    sample.position.speed_observed_at = clock.now()
    main._coordinator.restore_telemetry(sample)
    if service.status().service_mode == "live":
        from dataclasses import replace
        from app.models.flight_status import ETAMode, FlightPhase
        from app.services.flight_state import get_flight_state_manager

        flight = get_flight_state_manager()
        checkpoint = flight.checkpoint()
        status = checkpoint.status.model_copy(
            update={
                "phase": FlightPhase.IN_FLIGHT,
                "eta_mode": ETAMode.ESTIMATED,
                "departure_time": clock.start,
            }
        )
        flight.restore_checkpoint(replace(checkpoint, status=status))
    if service.status().state == "running":
        await asyncio.to_thread(
            service.collect, main._coordinator, main._publish_replay_telemetry
        )
    return {
        "synthetic": True,
        "raw_inputs_only": True,
        "now": clock.now(),
        "run": service.status(),
    }
