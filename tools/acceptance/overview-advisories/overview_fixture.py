"""Synthetic telemetry inputs for the current live coordinator; no model overrides."""

import asyncio

import availability_fixture as base
from fastapi import HTTPException
from app.live.client import StarlinkClient
from app.live.coordinator import LiveCoordinator
from app.models.telemetry import TelemetryData

# The private acceptance network never needs a dish or a connection attempt.
StarlinkClient.connect = lambda self: False
app = base.app
app.router.routes[:] = [
    route
    for route in app.router.routes
    if getattr(route, "path", None) != "/api/_synthetic/transport-inputs"
]


@app.post("/api/_synthetic/transport-inputs")
async def raw_inputs(body: dict):
    if set(body) - {"elapsed_seconds"}:
        raise HTTPException(422, "Only raw elapsed time is accepted")
    seconds = body.get("elapsed_seconds", base.clock.elapsed)
    if type(seconds) not in (int, float) or seconds < base.clock.elapsed:
        raise HTTPException(422, "Time must advance")
    base.clock.elapsed = float(seconds)
    now = base.clock.now()
    sample = TelemetryData(
        timestamp=now,
        position={
            "latitude": 0,
            "longitude": -10 + min(seconds, 3600) / 180,
            "altitude": 30000,
            "altitude_observed_at": now,
            "speed": 600,
            "heading": 90,
            "observed_at": now,
            "speed_observed_at": now,
        },
        network={
            "latency_ms": 0,
            "throughput_down_mbps": 0,
            "throughput_up_mbps": 0,
            "packet_loss_percent": 0,
        },
        obstruction={"obstruction_percent": 0},
        metric_source="unavailable",
    )
    coordinator = base.main._coordinator
    if isinstance(coordinator, LiveCoordinator):
        coordinator._publish_telemetry(sample, False)
    else:
        coordinator.restore_telemetry(sample)
    service = app.state.simulation_run_service
    if service.status().state == "running":
        await asyncio.to_thread(
            service.collect, coordinator, base.main._publish_replay_telemetry
        )
    return {
        "synthetic": True,
        "raw_inputs_only": True,
        "now": now,
        "departure": base.clock.start,
        "run": service.status(),
    }
