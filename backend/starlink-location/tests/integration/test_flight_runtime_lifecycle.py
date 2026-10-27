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
