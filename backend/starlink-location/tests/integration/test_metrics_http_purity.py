"""Disabled-background HTTP scrapes cannot invoke producers or storage."""

import asyncio

import httpx
import pytest

import main
from app.core import eta_service
from app.core.metrics import prometheus_metrics as metrics
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
async def test_100_sequential_and_concurrent_scrapes_do_not_touch_sources(
    background_runtime, monkeypatch
):
    from app.core.config import ConfigManager
    from app.services.eta_calculator import ETACalculator
    from app.simulation.coordinator import SimulationCoordinator
    from app.simulation.network import NetworkSimulator
    from app.simulation.obstructions import ObstructionSimulator
    from app.simulation.position import PositionSimulator

    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    owner = main.app.state.metrics_refresh_owner
    await owner.refresh_without_collection()
    coordinator = main._coordinator
    frame = metrics.FRAME_STORE.read()
    observation = coordinator._last_valid_telemetry.model_dump()
    eta = eta_service.get_eta_calculator()
    stats = eta.get_stats()
    detector = background_runtime.flight_state.checkpoint()

    def observation_instruments():
        return {
            (sample.name, tuple(sorted(sample.labels.items()))): sample.value
            for family in metrics.REGISTRY.collect()
            if family.type in {"counter", "histogram"}
            and not family.name.startswith("starlink_metrics_")
            for sample in family.samples
        }

    observations = observation_instruments()

    def forbidden(*args, **kwargs):
        raise AssertionError("scrape invoked source, storage, or calculation")

    with monkeypatch.context() as spies:
        for cls in (
            SimulationCoordinator,
            PositionSimulator,
            NetworkSimulator,
            ObstructionSimulator,
            ETACalculator,
        ):
            spies.setattr(cls, "__init__", forbidden)
        for target, names in (
            (coordinator, ("update", "get_current_telemetry", "get_config")),
            (main.app.state.route_manager, ("get_active_route",)),
            (
                main.app.state.poi_manager,
                ("list_pois", "get_poi", "_load_pois", "_save_pois"),
            ),
            (ConfigManager, ("load", "get_config")),
            (eta, ("calculate_poi_metrics",)),
            (
                background_runtime.flight_state,
                ("observe_detection", "check_departure", "check_arrival", "get_status"),
            ),
            (main.app.state.simulation_run_service, ("collect",)),
        ):
            for name in names:
                spies.setattr(target, name, forbidden)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app), base_url="http://test"
        ) as client:
            for _ in range(100):
                assert (await client.get("/metrics")).status_code == 200
            results = await asyncio.wait_for(
                asyncio.gather(*(client.get("/metrics") for _ in range(100))), 15
            )
        assert all(r.status_code == 200 for r in results)
        assert all(r.text.count("# EOF\n") == 1 for r in results)
        assert metrics.FRAME_STORE.read() is frame
        assert coordinator._last_valid_telemetry.model_dump() == observation
        assert eta.get_stats() == stats
        assert background_runtime.flight_state.checkpoint() == detector
        assert observation_instruments() == observations
    assert owner.task is None or owner.task.done()
