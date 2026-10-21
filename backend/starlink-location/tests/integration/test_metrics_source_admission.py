"""Real producers, repository writers and HTTP scrapes share safe boundaries."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from math import isnan
from threading import Event

import httpx
import pytest

import main
from app.core.metrics import frame_builder
from app.core.metrics import prometheus_metrics as metrics
from tests.integration.test_live_background_route import background_runtime

__all__ = ["background_runtime"]


@pytest.fixture(autouse=True)
async def manual_publication_owner(background_runtime):
    # This suite explicitly controls all publication barriers. Lifecycle-owned
    # concurrency is exercised in test_metrics_publication_lifecycle.py.
    await main.app.state.metrics_refresh_owner.close()


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
@pytest.mark.parametrize("change", ["config", "route", "mission", "phase", "poi"])
async def test_http_scrapes_complete_while_producer_and_source_writer_contend(
    background_runtime, monkeypatch, change
):
    coordinator = main._coordinator
    entered, release, writer_entered = Event(), Event(), Event()
    prepare = frame_builder.prepare_frame
    old = metrics.FRAME_STORE.read()
    config = coordinator.get_config().model_copy(update={"update_interval_seconds": 2})

    def paused_prepare(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        entered.set()
        assert release.wait(5)
        return frame

    def change_config():
        writer_entered.set()
        from app.mission.storage import get_active_leg_lock
        from app.models.flight_status import FlightPhase
        from app.models.poi import POICreate

        with get_active_leg_lock():
            if change == "config":
                coordinator.update_config(config)
            elif change == "route":
                background_runtime.route_manager.activate_route("second")
            elif change == "mission":
                main.app.state.simulation_run_service.runtime.clear_selection()
            elif change == "phase":
                background_runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
            else:
                main.app.state.poi_manager.create_poi(
                    POICreate(name="Concurrent", latitude=0, longitude=1)
                )

    monkeypatch.setattr(frame_builder, "prepare_frame", paused_prepare)
    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(
            main._background_update_tick, main.app.state.poi_manager, 1, 0, 0
        )
        writer = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            writer = pool.submit(change_config)
            assert await asyncio.to_thread(writer_entered.wait, 3)
            assert (
                not writer.done()
            ), "Source writes must wait for admitted observation work"
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=main.app), base_url="http://test"
            ) as client:
                responses = await asyncio.wait_for(
                    asyncio.gather(*(client.get("/metrics") for _ in range(20))), 3
                )
            assert all(response.status_code == 200 for response in responses)
            assert all(response.text.endswith("# EOF\n") for response in responses)
            assert metrics.FRAME_STORE.read() is old
        finally:
            release.set()
            producer.result(timeout=5)
            if writer is not None:
                writer.result(timeout=5)
    if change == "config":
        assert coordinator.get_config() is config


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_disconnect_frame_uses_current_planned_route_without_counting_observation(
    background_runtime, monkeypatch
):
    runtime = background_runtime
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    previous_time = metrics.FRAME_STORE.read().frame.last_observation_publication_time
    before_count = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    assert runtime.route_manager.activate_route("second")
    monkeypatch.setattr(main._coordinator, "update", lambda: None)
    main._coordinator._connection_status = False
    main._background_update_tick(main.app.state.poi_manager, 1, 1, 0)
    frame = metrics.FRAME_STORE.read().frame
    assert frame.identity.observation_id is None
    assert frame.last_observation_publication_time == previous_time
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before_count
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_has_timing_data", {"route_name": "second"}
        )
        == 0
    )
    assert isnan(metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees"))


@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_retained_fallback_is_not_another_observation(
    background_runtime, monkeypatch
):
    coordinator = main._coordinator
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    old = metrics.FRAME_STORE.read()
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")
    from app.core import eta_service

    stats = eta_service.get_eta_calculator().get_stats()
    retained = coordinator.get_current_telemetry()
    monkeypatch.setattr(coordinator, "update", lambda: retained)
    main._background_update_tick(main.app.state.poi_manager, 1, 1, 0)
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before
    assert metrics.FRAME_STORE.read() is old
    assert eta_service.get_eta_calculator().get_stats() == stats


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
@pytest.mark.parametrize("replacement", ["config", "mission", "coordinator", "reset"])
@pytest.mark.parametrize("newer_publication", [False, True])
async def test_source_replaced_during_collection_is_rejected(
    background_runtime, monkeypatch, replacement, newer_publication
):
    from app.mission.storage import get_active_leg_lock
    from app.simulation.coordinator import SimulationCoordinator

    coordinator = main._coordinator
    entered, release = Event(), Event()
    collect = coordinator.update
    old = metrics.FRAME_STORE.read()
    newer = None
    before = metrics.REGISTRY.get_sample_value("simulation_updates_total")

    def paused_collection():
        entered.set()
        assert release.wait(5)
        return collect()

    monkeypatch.setattr(coordinator, "update", paused_collection)
    with ThreadPoolExecutor(max_workers=1) as pool:
        producer = pool.submit(
            main._background_update_tick, main.app.state.poi_manager, 1, 0, 0
        )
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            with get_active_leg_lock():
                if replacement == "config":
                    coordinator.update_config(
                        coordinator.get_config().model_copy(
                            update={"update_interval_seconds": 2}
                        )
                    )
                elif replacement == "mission":
                    main.app.state.simulation_run_service.runtime.clear_selection()
                elif replacement == "coordinator":
                    monkeypatch.setattr(
                        main,
                        "_coordinator",
                        SimulationCoordinator(coordinator.get_config()),
                    )
                else:
                    coordinator.reset()
                if newer_publication:
                    current = metrics.FRAME_STORE.read()
                    assert metrics.FRAME_STORE.publish(current, current.frame)
                    newer = metrics.FRAME_STORE.read()
        finally:
            release.set()
            try:
                producer.result(timeout=5)
            finally:
                # The lifespan fixture must close its original live coordinator.
                monkeypatch.setattr(main, "_coordinator", coordinator)
    assert metrics.REGISTRY.get_sample_value("simulation_updates_total") == before
    assert metrics.FRAME_STORE.read().frame is old.frame
    if newer_publication:
        assert metrics.FRAME_STORE.read() is newer
        assert newer.status == "ready"
    else:
        assert metrics.FRAME_STORE.read().status != "ready"


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
async def test_normal_frame_has_one_source_progress_and_timestamp(
    background_runtime, monkeypatch
):
    from types import SimpleNamespace

    from app.core.metrics.frame_builder import coordinator_identity
    from app.models.poi import POICreate

    runtime = background_runtime
    monkeypatch.setattr(
        "app.simulation.coordinator.datetime",
        SimpleNamespace(now=lambda tz: runtime.clock[0]),
    )
    runtime.route_manager.activate_route("first")
    main.app.state.poi_manager.create_poi(
        POICreate(name="Destination", latitude=1, longitude=1)
    )
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    telemetry = main._coordinator.get_current_telemetry()
    frame = metrics.FRAME_STORE.read().frame
    mode = main._coordinator.mode
    assert frame.identity.mode == mode
    assert frame.identity.coordinator_id == coordinator_identity(main._coordinator)
    assert frame.identity.observation_timestamp == telemetry.timestamp.timestamp()
    assert frame.last_observation_publication_time == runtime.clock[0].timestamp()
    assert (
        metrics.REGISTRY.get_sample_value("starlink_dish_latitude_degrees")
        == telemetry.position.latitude
    )
    assert (
        metrics.REGISTRY.get_sample_value("starlink_dish_longitude_degrees")
        == telemetry.position.longitude
    )
    assert metrics.REGISTRY.get_sample_value("starlink_mode_info", {"mode": mode}) == 1
    assert metrics.REGISTRY.get_sample_value("starlink_flight_phase") == 0
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_route_has_timing_data", {"route_name": "first"}
        )
        == 0
    )
    if mode == "simulation":
        assert (
            metrics.REGISTRY.get_sample_value(
                "starlink_route_progress_percent", {"route_name": "first"}
            )
            == main._coordinator.route_progress_snapshot()[0]
        )
    else:
        assert (
            metrics.REGISTRY.get_sample_value(
                "starlink_route_progress_percent", {"route_name": "first"}
            )
            is None
        )
    assert (
        metrics.REGISTRY.get_sample_value(
            "starlink_eta_poi_seconds",
            {"name": "Destination", "category": "", "eta_type": "anticipated"},
        )
        >= 0
    )


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_live_prepared_frame_rechecks_persisted_mission_identity(
    background_runtime, monkeypatch, isolate_mission_storage
):
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.storage import save_mission_v2

    runtime = background_runtime
    runtime.route_manager.activate_route("first")
    mission = Mission(
        id="source-mission",
        name="Before",
        legs=[
            MissionLeg(
                id="source-leg",
                name="Active",
                route_id="first",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    save_mission_v2(mission)
    old = metrics.FRAME_STORE.read()
    prepare = frame_builder.prepare_frame

    def changed_mission(*args, **kwargs):
        frame = prepare(*args, **kwargs)
        mission.name = "After preparation"
        save_mission_v2(mission)
        return frame

    monkeypatch.setattr(frame_builder, "prepare_frame", changed_mission)
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    assert metrics.FRAME_STORE.read().frame is old.frame
    assert metrics.FRAME_STORE.read().status == "failed"
