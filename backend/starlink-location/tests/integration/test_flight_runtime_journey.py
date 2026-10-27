"""Synthetic accepted-live journey through real source admission, API and archive."""

import asyncio
from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest

import main
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import save_mission_v2
from app.models.poi import POICreate
from app.models.telemetry import TelemetryData
from app.services.kml.geometry import haversine_distance
from tests.integration.test_live_background_route import (
    background_runtime,
)

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_restored_live_journey_lands_parks_and_exports_outside_endpoint(
    background_runtime, monkeypatch
):
    runtime = background_runtime
    await main.app.state.metrics_refresh_owner.close()
    # This test manually owns publication to inspect each admitted tick.
    del main.app.state.metrics_refresh_owner
    runtime.route_manager.activate_route("first")
    save_mission_v2(
        Mission(
            id="journey",
            name="Synthetic journey",
            legs=[
                MissionLeg(
                    id="leg",
                    name="Large airport",
                    route_id="first",
                    is_active=True,
                    transports=TransportConfig(initial_x_satellite_id="X-1"),
                )
            ],
        )
    )
    main.app.state.poi_manager.create_poi(
        POICreate(
            name="Arrival",
            latitude=1,
            longitude=1,
            kind="arrival",
            mission_id="journey",
            route_id="first",
            generated_source="mission-timeline",
        )
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        config = (await client.get("/api/config")).json() | {"mode": "live"}
        assert (await client.post("/api/config", json=config)).status_code == 200
        recording = main.app.state.flight_event_runtime
        assert recording is not None
        # Only accepted telemetry is synthetic: real coordinator publication,
        # admission, detector, persistence, phase/ETA projection and export run.
        sample = [None]
        monkeypatch.setattr(main._coordinator, "_collect_telemetry", lambda: sample[0])
        monkeypatch.setattr(
            "app.services.flight_events.live_adapter.datetime",
            SimpleNamespace(now=lambda tz: runtime.clock[0]),
        )
        monkeypatch.setattr(
            "app.api.overview_upcoming_pois.datetime",
            SimpleNamespace(now=lambda tz: runtime.clock[0]),
        )
        # No real Prometheus history is available for this synthetic flight.
        recording.client.close()
        recording.client = httpx.Client(
            base_url="http://synthetic-prometheus",
            transport=httpx.MockTransport(lambda request: httpx.Response(503)),
        )
        for second in range(711):
            runtime.clock[0] = runtime.origin + timedelta(seconds=second)
            speed, altitude = (
                (0, 100)
                if second <= 300
                else (
                    (10, 100)
                    if second <= 320
                    else (
                        (120, 500)
                        if second <= 350
                        else (
                            (200, 10000)
                            if second <= 360
                            else (25, 100) if second <= 400 else (0, 100)
                        )
                    )
                )
            )
            assert haversine_distance(1.01, 1, 1, 1) > 100
            sample[0] = TelemetryData.model_validate(
                {
                    "timestamp": runtime.clock[0],
                    "metric_source": "observed",
                    "position": {
                        "latitude": 1.01,
                        "longitude": 1,
                        "speed": speed,
                        "altitude": altitude,
                        "observed_at": runtime.clock[0],
                        "speed_observed_at": runtime.clock[0],
                        "altitude_observed_at": runtime.clock[0],
                        "altitude_validity_source": "synthetic_live",
                    },
                    "network": {
                        "latency_ms": 10,
                        "throughput_down_mbps": 20,
                        "throughput_up_mbps": 5,
                        "packet_loss_percent": 0,
                    },
                    "obstruction": {"obstruction_percent": 0},
                }
            )
            await asyncio.to_thread(
                main._background_update_tick, main.app.state.poi_manager, 1, second, 0
            )
        view = (
            await client.get("/api/v2/missions/journey/legs/leg/flight-events")
        ).json()
        assert [event["kind"] for event in view["events"]] == [
            "off_blocks",
            "takeoff",
            "landed",
            "on_blocks",
        ]
        assert view["status"]["movement_state"] == "parked"
        landed = view["events"][2]
        assert landed["occurred_at"] != landed["detected_at"]
        assert landed["source"] == "inferred"
        phase = (await client.get("/api/flight-status")).json()
        assert phase["phase"] == "post_arrival"
        overview = (await client.get("/api/overview/upcoming-pois")).json()
        assert overview["flight_phase"] == "post_arrival"
        assert not any(
            poi.get("eta_seconds") is not None
            for poi in overview["pois"]
            if poi["kind"] == "arrival"
        )
        # A failed inference tick must not leave the last fresh movement looking
        # certain, even though the committed ledger is still readable.
        import sqlite3

        original_observe = recording.observe_live

        def fail_detection(*args, **kwargs):
            raise sqlite3.OperationalError("event persistence unavailable")

        monkeypatch.setattr(recording, "observe_live", fail_detection)
        runtime.clock[0] += timedelta(seconds=1)
        sample[0] = sample[0].model_copy(deep=True)
        sample[0].timestamp = runtime.clock[0]
        sample[0].position.observed_at = runtime.clock[0]
        sample[0].position.speed_observed_at = runtime.clock[0]
        sample[0].position.altitude_observed_at = runtime.clock[0]
        await asyncio.to_thread(
            main._background_update_tick, main.app.state.poi_manager, 1, 711, 0
        )
        uncertain = (
            await client.get("/api/v2/missions/journey/legs/leg/flight-events")
        ).json()
        assert uncertain["status"]["movement_uncertain"]
        assert (await client.get("/api/overview/upcoming-pois")).json()[
            "movement_uncertain"
        ]
        monkeypatch.setattr(recording, "observe_live", original_observe)
        recording.capture.recover(runtime.clock[0])
        capture = recording.archive.capture_summary("journey", "leg")
        assert (
            capture["start"]
            == (
                runtime.origin + timedelta(seconds=301) - timedelta(minutes=30)
            ).isoformat()
        )
        assert (
            capture["end"]
            == (
                runtime.origin + timedelta(seconds=401) + timedelta(minutes=30)
            ).isoformat()
        )
        assert capture["state"] == "recording"  # never seal at touchdown
        end = runtime.origin + timedelta(seconds=2211)
        recording.capture.max_retries = 1
        config["mode"] = "simulation"
        assert (await client.post("/api/config", json=config)).status_code == 200
        runtime.clock[0] = end
        recording.last_recovery = 0
        main.app.state.flight_event_lifecycle.tick()
        from app.services.telemetry_archive.reader import ArchiveReader

        for _ in range(30):
            recording.capture.backfill_one(ArchiveReader(recording.client), end)
        recording.last_recovery = 0
        main.app.state.flight_event_lifecycle.tick()
        final = recording.archive.capture("journey", "leg")
        assert final["state"] == "sealed"
        assert final["revision"] == capture["revision"]
        assert not final["complete"]  # unavailable raw history stays explicitly partial
        assert final["samples"]
        assert all(
            row["labels"]["source"] == "accepted_live" for row in final["samples"]
        )
        from app.mission.package import operations_archive

        monkeypatch.setattr(
            operations_archive, "runtime_for", lambda _: nullcontext(None)
        )
        bundle = operations_archive.capture_archive(
            SimpleNamespace(app=main.app), "journey"
        )
        assert bundle["components"]["telemetry"]["status"] == "included"
        assert any(path.startswith("telemetry/") for path in bundle["files"])
