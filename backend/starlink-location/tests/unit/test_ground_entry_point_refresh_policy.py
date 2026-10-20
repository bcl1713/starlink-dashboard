"""Tests for automatic ground-entry discovery by operating mode."""

import asyncio

import pytest

import main
from app.models.config import SimulationConfig


def test_simulation_does_not_automatically_refresh_ground_entry_point() -> None:
    assert (
        main.should_automatically_refresh_ground_entry_point(
            SimulationConfig(mode="simulation")
        )
        is False
    )


def test_live_mode_automatically_refreshes_ground_entry_point() -> None:
    assert (
        main.should_automatically_refresh_ground_entry_point(
            SimulationConfig(mode="live")
        )
        is True
    )


class SingleUpdateCoordinator:
    def __init__(self) -> None:
        self.update_calls = 0

    def update(self):
        self.update_calls += 1


@pytest.mark.asyncio
async def test_simulation_background_update_skips_gep_refresh(
    monkeypatch,
) -> None:
    coordinator = SingleUpdateCoordinator()
    refresh_calls: list[float] = []

    def record_refresh(*, refresh_interval_seconds: float) -> None:
        refresh_calls.append(refresh_interval_seconds)

    async def cancel_after_first_update(_: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(main, "_simulation_config", SimulationConfig(mode="simulation"))
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(
        main,
        "maybe_refresh_ground_entry_point_metrics",
        record_refresh,
    )
    monkeypatch.setattr(main.asyncio, "sleep", cancel_after_first_update)

    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop()

    assert refresh_calls == []
    assert coordinator.update_calls == 1


@pytest.mark.asyncio
async def test_live_background_update_refreshes_gep_before_telemetry(
    monkeypatch,
) -> None:
    coordinator = SingleUpdateCoordinator()
    refresh_calls: list[float] = []

    def record_refresh(*, refresh_interval_seconds: float) -> None:
        refresh_calls.append(refresh_interval_seconds)

    async def cancel_after_first_update(_: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(main, "_simulation_config", SimulationConfig(mode="live"))
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(
        main,
        "maybe_refresh_ground_entry_point_metrics",
        record_refresh,
    )
    monkeypatch.setattr(main.asyncio, "sleep", cancel_after_first_update)

    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop()

    assert refresh_calls == [1.0]
    assert coordinator.update_calls == 1


@pytest.mark.asyncio
async def test_route_free_emission_publishes_matching_synthetic_status_and_metrics(
    monkeypatch, coordinator, tmp_path
):
    from prometheus_client import generate_latest

    from app.api import status as status_api
    from app.core.metrics import REGISTRY
    from app.mission.pop_status import PopStatusService
    from app.services import ground_entry_point as gep
    from app.services.pop.catalog import DEFAULT_CATALOG_PATH, load_catalog
    from app.simulation.pop import SimulationPopObservationProvider

    def forbidden(*args, **kwargs):
        raise AssertionError("Simulation must not discover real egress")

    monkeypatch.setattr(gep, "resolve_public_ip", forbidden)
    monkeypatch.setattr(gep, "geolocate_public_ip", forbidden)
    monkeypatch.setattr(gep, "resolve_public_ip_via_dns", forbidden)
    monkeypatch.setattr(gep, "resolve_public_ip_via_cloudflare_trace", forbidden)
    monkeypatch.setattr(gep._resolver, "_geolocator", forbidden)
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(main, "_route_manager", None)
    monkeypatch.setattr(main, "_simulation_config", coordinator.config)
    monkeypatch.setattr(main.app.state, "simulation_run_service", None, raising=False)
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None, raising=False)
    service = PopStatusService(
        config_provider=lambda: coordinator.config,
        observation_provider=SimulationPopObservationProvider(
            main._pop_lifecycle_token
        ),
        snapshot_context_provider=main._simulation_pop_context,
    )
    monkeypatch.setattr(main.app.state, "pop_status_service", service, raising=False)
    monkeypatch.setattr(status_api, "_coordinator", coordinator)
    monkeypatch.setattr(status_api, "_pop_service", service)
    prior_live = gep.get_cached_pop_observation()
    points = load_catalog(DEFAULT_CATALOG_PATH).sites
    try:
        for site in (points[0], points[-1]):
            position = coordinator.get_current_telemetry().position.model_copy(
                update={"latitude": site.latitude, "longitude": site.longitude}
            )
            monkeypatch.setattr(
                coordinator.position_sim, "update", lambda position=position: position
            )
            main._background_update_tick(None, 1, 0, 0)
            result = await status_api.status()
            observed = result["pop_observation"]
            assert observed["entry"]["city"] == site.city
            assert result["ground_entry_point"] == {
                "latitude": site.latitude,
                "longitude": site.longitude,
            }
            assert result["pop_forecast"]["status"] == "unavailable"
            assert result["pop_forecast"]["transitions"] == []
            metrics = generate_latest(REGISTRY).decode()
            info = next(
                line
                for line in metrics.splitlines()
                if line.startswith("starlink_ground_entry_point_info{")
            )
            assert f'ip="{observed["ip"]}"' in info
            assert f'city="{site.city}"' in info
        assert gep.get_cached_pop_observation() == prior_live
    finally:
        gep.clear_ground_entry_point_metrics()


def test_runtime_mode_switch_uses_current_config_for_live_refresh(
    monkeypatch, coordinator
):
    # The process startup configuration remains simulation after API replacement.
    initial = SimulationConfig(mode="simulation")
    coordinator.update_config(SimulationConfig(mode="live"))
    monkeypatch.setattr(main, "_simulation_config", initial)
    monkeypatch.setattr(main, "_coordinator", coordinator)
    monkeypatch.setattr(main, "_route_manager", None)
    monkeypatch.setattr(main.app.state, "simulation_run_service", None, raising=False)
    monkeypatch.setattr(main.app.state, "flight_event_runtime", None, raising=False)
    refreshes = []
    monkeypatch.setattr(
        main,
        "maybe_refresh_ground_entry_point_metrics",
        lambda **kwargs: refreshes.append(kwargs),
    )
    main._background_update_tick(None, 1, 0, 0)
    assert refreshes == [{"refresh_interval_seconds": 1}]
