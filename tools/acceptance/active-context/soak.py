"""Opt-in real live-coordinator/SQLite/ASGI soak over fictional saved missions.

Run explicitly with pytest and ISSUE392_SOAK_SECONDS. Only dish transport is
stubbed by the existing live-background fixture. This lane has no Docker,
Nginx, physical dish, browser, or representative-display performance claim.
"""

import asyncio
import json
import os
import platform
import resource
import statistics
import time
from datetime import timedelta
from math import ceil
from pathlib import Path

import httpx
import main
import pytest
from app.mission import storage
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.operator.clock import SystemClock
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from tests.integration.test_live_background_route import background_runtime

from tools.benchmark_active_context import counters

__all__ = ["background_runtime"]


@pytest.fixture
def operator_seed(monkeypatch, tmp_path):
    root = tmp_path / "operator"
    monkeypatch.setenv("OPERATOR_ENABLED", "true")
    monkeypatch.setenv("OPERATOR_ROOT", str(root))
    monkeypatch.setenv("OPERATOR_SOURCE_MODE", "live")
    store = OperatorStore.open(
        OperatorSettings(root=root, source_mode="live"),
        initialize=True,
        clock=SystemClock(),
    )
    store.close()


@pytest.fixture
async def soak_runtime(operator_seed, background_runtime):
    yield background_runtime


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_live_like_soak(soak_runtime, monkeypatch):
    seconds = int(os.environ["ISSUE392_SOAK_SECONDS"])
    output = Path(os.environ["ISSUE392_SOAK_OUTPUT"])
    assert not output.exists(), "Evidence is write-once"
    runtime = soak_runtime
    missions = int(os.environ.get("ISSUE392_SOAK_MISSIONS", "100"))
    for index in range(missions):
        mission = Mission(
            id=f"soak-{index}",
            name=f"Fictional soak {index}",
            legs=[
                MissionLeg(
                    id=f"leg-{leg}",
                    name=f"Leg {leg}",
                    route_id="first",
                    is_active=index == 0 and leg == 0,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
                for leg in range(4)
            ],
        )
        folder = storage.MISSIONS_DIR / mission.id
        (folder / "legs").mkdir(parents=True)
        (folder / "mission.json").write_text(
            mission.model_copy(update={"legs": []}).model_dump_json()
        )
        for leg in mission.legs:
            (folder / "legs" / f"{leg.id}.json").write_text(leg.model_dump_json())
    runtime.route_manager.activate_route("first")
    monkeypatch.setattr(
        "app.services.flight_events.live_adapter.datetime",
        type("Clock", (), {"now": staticmethod(lambda tz=None: runtime.clock[0])}),
    )
    owner = None
    try:
        from app.mission.active_context_owner import ActiveContextOwner
    except ImportError:
        pass
    else:
        owner = ActiveContextOwner(runtime.route_manager, lambda: "live")
        await owner.start()
    observed = []
    original_observe = main.app.state.flight_event_runtime.observe_live

    def observe(telemetry, context, **kwargs):
        assert context.parent_mission_id == "soak-0"
        assert context.leg.id == "leg-0"
        result = original_observe(telemetry, context, **kwargs)
        observed.append(telemetry.timestamp)
        return result

    monkeypatch.setattr(main.app.state.flight_event_runtime, "observe_live", observe)
    walls, cpus, status, operator = [], [], [], []
    errors = []
    resource_samples = []

    def process_io():
        return {
            key: int(value)
            for key, value in (
                line.split(":", 1)
                for line in Path("/proc/self/io").read_text().splitlines()
            )
        }

    def rss_kib():
        return next(
            int(line.split()[1])
            for line in Path("/proc/self/status").read_text().splitlines()
            if line.startswith("VmRSS:")
        )

    started = time.monotonic()
    tick_index = 0

    def tick():
        nonlocal tick_index
        wall, cpu = time.perf_counter_ns(), time.thread_time_ns()
        tick_index = main._background_update_tick(
            main.app.state.poi_manager, 1, tick_index, 0
        )
        cpus.append(time.thread_time_ns() - cpu)
        walls.append(time.perf_counter_ns() - wall)

    async def probe(client, path, samples):
        start = time.perf_counter_ns()
        response = await client.get(path)
        samples.append(time.perf_counter_ns() - start)
        if response.status_code != 200:
            errors.append(
                {
                    "path": path,
                    "status": response.status_code,
                    "body": response.text[:300],
                }
            )
        return response

    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://soak"
        ) as client:
            for _ in range(5):
                runtime.clock[0] += timedelta(seconds=1)
                await asyncio.to_thread(tick)
            walls.clear()
            cpus.clear()
            observed.clear()
            started = time.monotonic()
            process_cpu_start = time.process_time_ns()
            initial_io = process_io()
            with counters() as counts:
                for second in range(seconds):
                    runtime.clock[0] += timedelta(seconds=1)
                    producer = asyncio.create_task(asyncio.to_thread(tick))
                    await asyncio.gather(
                        probe(client, "/api/status", status),
                        probe(
                            client,
                            "/api/v2/operator/records?mission_id=soak-0",
                            operator,
                        ),
                        producer,
                    )
                    if second % 60 == 0:
                        resource_samples.append(
                            {
                                "elapsed_seconds": time.monotonic() - started,
                                "rss_kib": rss_kib(),
                                "io": process_io(),
                                "process_cpu_seconds": (
                                    time.process_time_ns() - process_cpu_start
                                )
                                / 1e9,
                            }
                        )
                        print(
                            f"soak progress: {second}/{seconds}s, observations={len(observed)}, errors={len(errors)}",
                            flush=True,
                        )
                    await asyncio.sleep(max(0, started + second + 1 - time.monotonic()))
            measured_seconds = time.monotonic() - started
            total_process_cpu_seconds = (
                time.process_time_ns() - process_cpu_start
            ) / 1e9
            final_io = process_io()
        assert len(observed) == seconds
        assert len(set(observed)) == seconds
        assert not errors
        state = main.app.state.flight_event_runtime.events.state("soak-0", "leg-0")

        def summary(values):
            return {
                "samples": len(values),
                "mean_ms": statistics.mean(values) / 1e6,
                "p95_ms": sorted(values)[ceil(len(values) * 0.95) - 1] / 1e6,
            }

        report = {
            "application_sha": os.environ["ISSUE392_APPLICATION_SHA"],
            "harness_sha": os.environ["ISSUE392_HARNESS_SHA"],
            "counter_scope": "Python file-read, Path and os boundaries; Path/os counts overlap; proc I/O is whole-process including SQLite and observer",
            "scope": __doc__,
            "missions": missions,
            "legs_per_mission": 4,
            "warmup_ticks": 5,
            "measured_seconds": measured_seconds,
            "process_cpu_seconds": total_process_cpu_seconds,
            "process_io_delta": {
                key: final_io[key] - initial_io[key] for key in initial_io
            },
            "rss_peak_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "resource_samples": resource_samples,
            "ticks": len(walls),
            "observations": len(observed),
            "tick_wall": summary(walls),
            "tick_thread_cpu": summary(cpus),
            "status_asgi": summary(status),
            "operator_records_asgi": summary(operator),
            "counts": dict(counts),
            "errors": errors,
            "movement": str(state.movement),
            "last_observed_at": str(state.last_observed_at),
            "python": platform.python_version(),
            "platform": platform.platform(),
        }
        output.write_text(json.dumps(report, indent=2) + "\n")
    finally:
        if owner is not None:
            await owner.close()
