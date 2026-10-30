"""Real API/source transitions must own the live detector and archive."""

import httpx
import pytest

import main
from app.live.coordinator import LiveCoordinator
from app.simulation.coordinator import SimulationCoordinator
from tests.integration.test_live_background_route import (
    background_runtime,
)

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_live_status_metrics_and_eta_continue_during_slow_raw_recovery(
    background_runtime, monkeypatch
):
    import asyncio
    from datetime import timedelta
    from threading import Event
    from types import SimpleNamespace

    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.storage import save_mission_v2
    from app.models.poi import POICreate
    from app.models.route import RouteTimingProfile
    from app.models.telemetry import TelemetryData
    from app.services.flight_events.maintenance import FlightMaintenanceOwner

    clock = background_runtime.clock
    origin = background_runtime.origin
    background_runtime.route.timing_profile = RouteTimingProfile(has_timing_data=True)
    for point in background_runtime.route.points:
        point.expected_segment_speed_knots = 300
    await main.app.state.metrics_refresh_owner.close()
    del main.app.state.metrics_refresh_owner
    background_runtime.route_manager.activate_route("first")
    save_mission_v2(
        Mission(
            id="continuity",
            name="Synthetic continuity check",
            legs=[
                MissionLeg(
                    id="leg",
                    name="Leg",
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
            mission_id="continuity",
            route_id="first",
        ),
        active_route=background_runtime.route,
        generated_source="mission-timeline",
    )
    frozen = SimpleNamespace(now=lambda tz: clock[0])
    monkeypatch.setattr("app.services.flight_events.live_adapter.datetime", frozen)
    monkeypatch.setattr("app.api.overview_upcoming_pois.datetime", frozen)
    runtime = main.app.state.flight_event_runtime
    for kind, second in (("off_blocks", -40), ("takeoff", -30)):
        runtime.events.record_manual_event(
            "continuity",
            "leg",
            kind,
            origin + timedelta(seconds=second),
            "test",
            "operator",
        )
    entered, release = Event(), Event()

    def slow_prometheus(request):
        entered.set()
        assert release.wait(10)
        return httpx.Response(503)

    runtime.client.close()
    runtime.client = httpx.Client(
        base_url="http://synthetic-prometheus",
        transport=httpx.MockTransport(slow_prometheus),
    )
    owner = FlightMaintenanceOwner(main.app.state.flight_event_lifecycle.tick)
    await owner.start()
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            for second in (1, 6, 12):
                clock[0] = origin + timedelta(seconds=second)
                sample = TelemetryData.model_validate(
                    {
                        "timestamp": clock[0],
                        "metric_source": "observed",
                        "metric_availability": {
                            "latency_ms": True,
                            "throughput_down_mbps": True,
                            "throughput_up_mbps": True,
                            "packet_loss_percent": True,
                            "obstruction_percent": True,
                        },
                        "position": {
                            "latitude": 1.1,
                            "longitude": 1.1,
                            "speed": 200,
                            "altitude": 10000,
                            "observed_at": clock[0],
                            "speed_observed_at": clock[0],
                            "altitude_observed_at": clock[0],
                            "altitude_validity_source": "test",
                        },
                        "network": {
                            "latency_ms": second,
                            "throughput_down_mbps": 20,
                            "throughput_up_mbps": 5,
                            "packet_loss_percent": 0,
                        },
                        "obstruction": {"obstruction_percent": 0},
                    }
                )
                monkeypatch.setattr(
                    main._coordinator,
                    "_collect_telemetry",
                    lambda sample=sample: sample,
                )
                work = asyncio.create_task(
                    asyncio.to_thread(
                        main._background_update_tick,
                        main.app.state.poi_manager,
                        1,
                        second,
                        0,
                    )
                )
                try:
                    done, _ = await asyncio.wait({work}, timeout=2)
                    assert done, "Blocked Prometheus recovery stopped live collection"
                finally:
                    if not work.done():
                        release.set()
                    await work
                status = (await client.get("/api/status")).json()
                assert status["timestamp"] == clock[0].isoformat()
                assert status["network"]["latency_ms"] == second
                metrics = (await client.get("/metrics")).text
                assert f"starlink_network_latency_ms_current {second}.0" in metrics
                arrival = (await client.get("/api/overview/upcoming-pois")).json()
                assert arrival["position_state"] == "fresh", arrival
                assert arrival["state"] == "available"
                assert arrival["pois"][0]["estimated_arrival_time"] is not None, str(
                    arrival
                )
        samples = runtime.archive.samples(origin, clock[0])
        assert [
            row["value"]
            for row in samples
            if row["metric"] == "starlink_network_latency_ms_current"
        ] == [1, 6, 12]
    finally:
        release.set()
        await owner.close()


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_telemetry_tick_does_not_wait_for_archive_maintenance(
    background_runtime, monkeypatch
):
    import asyncio
    from datetime import timedelta
    from threading import Event

    entered, release = Event(), Event()
    runtime = main.app.state.flight_event_runtime

    def slow_recovery():
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(runtime, "tick", slow_recovery)
    background_runtime.clock[0] += timedelta(seconds=1)
    work = asyncio.create_task(
        asyncio.to_thread(
            main._background_update_tick, main.app.state.poi_manager, 1, 0, 0
        )
    )
    try:
        done, _ = await asyncio.wait({work}, timeout=1)
        assert done, "Archive maintenance blocked the next live telemetry observation"
        assert await work == 1
        assert (
            main._coordinator.get_current_telemetry().timestamp
            == background_runtime.clock[0]
        )
        assert (
            not entered.is_set()
        ), "Telemetry acquisition performed archive maintenance"
    finally:
        release.set()
        await work


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("method", ["POST", "PUT"])
async def test_config_switch_initializes_actual_live_source_and_retains_archive(
    background_runtime, method
):
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        config = (await client.get("/api/config")).json()
        config["mode"] = "live"
        response = await client.request(method, "/api/config", json=config)
        assert response.status_code == 200
        assert isinstance(main._coordinator, LiveCoordinator)
        runtime = main.app.state.flight_event_runtime
        assert runtime is not None
        status = (await client.get("/api/flight-recording/status")).json()
        assert status["detection_available"]
        assert status["recording_available"]
        assert (await client.get("/health")).json()["flight_recording"] == status
        # Confirmed history survives both source changes; no simulation samples
        # enter the operational archive even with a retained runtime.
        runtime.events.record_manual_event(
            "m", "l", "off_blocks", background_runtime.origin, "test", "operator"
        )
        config["mode"] = "simulation"
        assert (
            await client.request(method, "/api/config", json=config)
        ).status_code == 200
        assert isinstance(main._coordinator, SimulationCoordinator)
        main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
        with runtime.archive.ledger.connect() as db:
            assert db.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 0
        status = (await client.get("/api/flight-recording/status")).json()
        assert status["state"] == "inactive"
        assert status["history_available"]
        config["mode"] = "live"
        assert (
            await client.request(method, "/api/config", json=config)
        ).status_code == 200
        assert main.app.state.flight_event_runtime is runtime
        assert len(runtime.events.events("m", "l")) == 1


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_absent_live_detector_never_uses_legacy_arrival(
    background_runtime, monkeypatch
):
    from unittest.mock import Mock

    state = background_runtime.flight_state
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None)
    monkeypatch.setattr(main.app.state, "flight_event_lifecycle", None, raising=False)
    legacy = Mock()
    monkeypatch.setattr(state, "check_arrival", legacy)
    background_runtime.route_manager.activate_route("first")
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    legacy.assert_not_called()


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
@pytest.mark.parametrize("method", ["POST", "PUT"])
async def test_api_storage_failure_recovers_on_tick_without_restart(
    background_runtime, method, tmp_path
):
    import asyncio

    owner = main.app.state.flight_event_lifecycle
    owner.root = tmp_path / "unavailable-root"
    owner.root.write_text("retained")
    clock = [0]
    owner.clock = lambda: clock[0]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app), base_url="http://test"
    ) as client:
        config = (await client.get("/api/config")).json() | {"mode": "live"}
        assert (
            await client.request(method, "/api/config", json=config)
        ).status_code == 200
        health = (await client.get("/health")).json()
        assert health["status"] == "degraded"
        assert health["flight_recording"]["state"] == "retrying"
        assert not health["flight_recording"]["detection_available"]
        # Repeated configuration requests cannot create an unbounded retry loop.
        owner.root.unlink()
        assert (
            await client.request(method, "/api/config", json=config)
        ).status_code == 200
        assert main.app.state.flight_event_runtime is None
        clock[0] = 5
        await asyncio.to_thread(
            main._background_update_tick, main.app.state.poi_manager, 1, 0, 0
        )
        ready = (await client.get("/api/flight-recording/status")).json()
        assert ready["state"] == "ready"
        runtime = main.app.state.flight_event_runtime
        await asyncio.to_thread(
            main._background_update_tick, main.app.state.poi_manager, 1, 1, 0
        )
        assert main.app.state.flight_event_runtime is runtime
