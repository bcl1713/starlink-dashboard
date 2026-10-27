"""Application-owned routes must reach live background phase evaluation."""

import asyncio
import threading
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main
from app.core.metrics import metric_updater
from app.live.client import StarlinkClient
from app.live.coordinator import LiveCoordinator
from app.models.config import SimulationConfig
from app.models.flight_status import FlightPhase
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.flight_state import get_flight_state_manager
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager


@pytest.mark.asyncio
@pytest.mark.parametrize("background_runtime", ["simulation"], indirect=True)
async def test_repeated_cancellation_drains_owned_telemetry(
    background_runtime, monkeypatch
):
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = main._background_update_tick

    def update(*args):
        entered.set()
        try:
            assert release.wait(3)
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(main, "_background_update_tick", update)
    task = asyncio.create_task(main._background_update_loop())
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        done, _ = await asyncio.wait({task}, timeout=0.05)
        assert not done, "The telemetry owner exited while its worker still ran"
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.to_thread(finished.wait, 2)


@pytest.fixture
async def background_runtime(monkeypatch, tmp_path, request):
    origin = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
    clock = [origin]
    frozen = SimpleNamespace(now=lambda tz: clock[0])
    for module in (
        "app.live.client",
        "app.live.coordinator",
        "app.core.metrics.metric_updater",
        "app.services.flight_state.manager",
    ):
        monkeypatch.setattr(f"{module}.datetime", frozen)

    # Stub transport only; live collection and speed provenance remain real.
    dish = StarlinkClient(connect_immediately=False)
    dish.context = SimpleNamespace(close=lambda: None)
    monkeypatch.setattr(dish, "connect", lambda: False)
    monkeypatch.setattr(dish, "get_status_data", lambda: ({"uptime": 3600}, {}, {}))
    monkeypatch.setattr(
        dish,
        "get_location_data",
        lambda: {"latitude": 1.0, "longitude": 1.0, "altitude": 100.0},
    )
    monkeypatch.setattr(
        dish, "get_history_stats", lambda **kwargs: ({}, {}, {}, {}, {}, {}, {})
    )
    monkeypatch.setattr("app.live.coordinator.StarlinkClient", lambda **kwargs: dish)

    config = SimulationConfig(mode=request.param, update_interval_seconds=1)
    monkeypatch.setattr(
        main, "ConfigManager", lambda: SimpleNamespace(load=lambda: config)
    )
    monkeypatch.setattr(main, "_coordinator", None)
    monkeypatch.setattr(main, "_route_manager", None)
    monkeypatch.setattr(main, "_background_task", None)
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    monkeypatch.setattr(main, "_simulation_config", None)
    monkeypatch.setattr(
        main, "OVERVIEW_HISTORY_SETTINGS_PATH", tmp_path / "history.json"
    )
    monkeypatch.setattr(main, "OVERVIEW_CLOCK_SETTINGS_PATH", tmp_path / "clocks.json")
    monkeypatch.setattr(
        main, "should_automatically_refresh_ground_entry_point", lambda _: False
    )
    monkeypatch.setattr(main, "POIManager", lambda: POIManager(tmp_path / "pois.json"))
    monkeypatch.setattr(RouteManager, "start_watching", lambda _: None)
    for attribute in ("coordinator", "route_manager", "poi_manager"):
        monkeypatch.setattr(main.app.state, attribute, None, raising=False)

    flight_state = get_flight_state_manager()
    flight_state.reset()
    flight_state.reset_detection()
    try:
        await main.startup_event()
    except Exception:
        # Failed startup still owns clients/tasks created before the failure.
        await main.shutdown_event()
        if config.mode == "live" and main._coordinator is not None:
            main._coordinator.shutdown()
        raise
    route_manager = main._route_manager
    assert isinstance(route_manager, RouteManager)
    assert main.app.state.route_manager is route_manager
    if config.mode == "live":
        assert isinstance(main._coordinator, LiveCoordinator)
        assert not hasattr(main._coordinator, "route_manager")

    def make_route(name, destination):
        return ParsedRoute(
            metadata=RouteMetadata(name=name, file_path=f"{name}.kml", point_count=2),
            points=[
                RoutePoint(latitude=10, longitude=10, sequence=0),
                RoutePoint(latitude=destination, longitude=destination, sequence=1),
            ],
        )

    route = make_route("first", 1)
    other_route = make_route("second", 2)
    route_manager._routes = {"first": route, "second": other_route}
    try:
        yield SimpleNamespace(
            origin=origin,
            clock=clock,
            route=route,
            other_route=other_route,
            route_manager=route_manager,
            flight_state=flight_state,
        )
    finally:
        await main.shutdown_event()
        if config.mode == "live":
            main._coordinator.shutdown()
        flight_state.reset()
        flight_state.reset_detection()


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
async def test_background_loop_uses_current_application_route(
    background_runtime, monkeypatch
):
    runtime = background_runtime
    update_metrics = MagicMock()
    monkeypatch.setattr(
        metric_updater, "_update_metrics_from_telemetry_admitted", update_metrics
    )
    expected_routes = [None, runtime.route, runtime.other_route, None]
    completed = 0
    delays = []

    async def next_observation(delay):
        nonlocal completed
        delays.append(delay)
        completed += 1
        if completed == 1:
            assert runtime.route_manager.activate_route("first")
        elif completed == 2:
            assert runtime.route_manager.activate_route("second")
        elif completed == 3:
            runtime.route_manager.deactivate_route()
        else:
            raise asyncio.CancelledError
        runtime.clock[0] += timedelta(seconds=1)

    monkeypatch.setattr(main.asyncio, "sleep", next_observation)
    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop(main.app.state.poi_manager)
    assert completed == 4
    assert delays == [1] * 4
    assert update_metrics.call_count == 4
    for call, expected_route in zip(update_metrics.call_args_list, expected_routes):
        assert call.args[2] is expected_route
        assert call.args[3] is main.app.state.poi_manager


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_live_background_loop_without_route_manager(
    background_runtime, monkeypatch
):
    monkeypatch.setattr(main, "_route_manager", None)
    update_metrics = MagicMock()
    monkeypatch.setattr(
        metric_updater, "_update_metrics_from_telemetry_admitted", update_metrics
    )

    async def stop_after_update(_delay):
        raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", stop_after_update)
    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop(main.app.state.poi_manager)

    update_metrics.assert_called_once()
    assert update_metrics.call_args.args[2] is None


@pytest.mark.parametrize("background_runtime", ["live", "simulation"], indirect=True)
async def test_telemetry_updates_remain_ordered(background_runtime, monkeypatch):
    loop_thread = threading.get_ident()
    observed = []
    active = 0

    def update(telemetry, *args, **kwargs):
        nonlocal active
        active += 1
        assert active == 1
        observed.append((threading.get_ident(), telemetry.timestamp))
        active -= 1

    async def next_tick(_delay):
        if len(observed) == 2:
            raise asyncio.CancelledError()
        background_runtime.clock[0] += timedelta(seconds=1)

    monkeypatch.setattr(
        metric_updater, "_update_metrics_from_telemetry_admitted", update
    )
    monkeypatch.setattr(main.asyncio, "sleep", next_tick)
    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop(main.app.state.poi_manager)
    assert len(observed) == 2
    assert all(worker != loop_thread for worker, _ in observed)
    assert observed[0][1] < observed[1][1]


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
@pytest.mark.parametrize("active_route", [False, True])
async def test_live_background_does_not_invent_arrival_without_bound_mission(
    background_runtime, monkeypatch, active_route
):
    runtime = background_runtime
    if active_route:
        assert runtime.route_manager.activate_route("first")
    runtime.flight_state.transition_phase(FlightPhase.IN_FLIGHT)
    statuses = []
    delays = []

    async def next_observation(delay):
        delays.append(delay)
        statuses.append(runtime.flight_state.get_status())
        if len(statuses) == 62:
            raise asyncio.CancelledError
        runtime.clock[0] += timedelta(seconds=1)

    monkeypatch.setattr(main.asyncio, "sleep", next_observation)
    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop(main.app.state.poi_manager)

    assert delays == [1] * 62
    # The first collection has no verified speed. Arrival dwell starts at t=1.
    assert all(status.phase == FlightPhase.IN_FLIGHT for status in statuses[:-1])
    assert all(status.arrival_time is None for status in statuses[:-1])
    final = statuses[-1]
    # A selected route and a singleton phase do not establish a bound mission
    # or verified airborne/landing evidence. Endpoint dwell alone must not land.
    assert final.phase == FlightPhase.IN_FLIGHT
    assert final.arrival_time is None


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_125_live_ticks_reuse_mission_without_json_reads(
    background_runtime, monkeypatch
):
    import builtins
    import io
    from app.mission import storage
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.active_context_cache import get_active_mission_snapshot

    mission = Mission(
        id="cached-live",
        name="Cached live",
        legs=[
            MissionLeg(
                id="cached-leg",
                name="Cached leg",
                route_id="first",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    storage.save_mission_v2(mission)
    background_runtime.route_manager.activate_route("first")
    get_active_mission_snapshot(background_runtime.route_manager)
    reads = []
    real_open, real_io_open = builtins.open, io.open

    def record_open(opener):
        def opened(path, *args, **kwargs):
            if str(path).endswith(".json") and str(storage.MISSIONS_DIR) in str(path):
                reads.append(str(path))
            return opener(path, *args, **kwargs)

        return opened

    monkeypatch.setattr(builtins, "open", record_open(real_open))
    monkeypatch.setattr(io, "open", record_open(real_io_open))
    observations = []
    runtime = SimpleNamespace(
        record_live=lambda _: None,
        observe_live=lambda telemetry, context: observations.append(
            (telemetry.timestamp, context.parent_mission_id, context.leg.id)
        ),
        sync_legacy_phase=lambda *_: None,
    )
    existing = main.app.state.flight_event_runtime
    monkeypatch.setattr(existing, "record_live", runtime.record_live)
    monkeypatch.setattr(existing, "observe_live", runtime.observe_live)
    monkeypatch.setattr(existing, "sync_legacy_phase", runtime.sync_legacy_phase)
    for count in range(125):
        background_runtime.clock[0] += timedelta(seconds=1)
        main._background_update_tick(main.app.state.poi_manager, 1, count, 0)
    assert len(observations) == 125
    assert {(mission_id, leg_id) for _, mission_id, leg_id in observations} == {
        ("cached-live", "cached-leg")
    }
    assert len({timestamp for timestamp, *_ in observations}) == 125
    assert reads == []


@pytest.mark.parametrize("background_runtime", ["live"], indirect=True)
async def test_mission_switch_during_recording_cannot_observe_prior_leg(
    background_runtime, monkeypatch
):
    from app.mission import storage
    from app.mission.models import Mission, MissionLeg, TransportConfig

    mission = Mission(
        id="switch-live",
        name="Switch live",
        legs=[
            MissionLeg(
                id="old-leg",
                name="Old",
                route_id="first",
                is_active=True,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )
    storage.save_mission_v2(mission)
    background_runtime.route_manager.activate_route("first")
    observations = []

    def record(_):
        mission.legs[0].is_active = False
        storage.save_mission_v2(mission)

    runtime = SimpleNamespace(
        record_live=record,
        observe_live=lambda *args: observations.append(args),
        sync_legacy_phase=lambda *_: None,
    )
    existing = main.app.state.flight_event_runtime
    monkeypatch.setattr(existing, "record_live", runtime.record_live)
    monkeypatch.setattr(existing, "observe_live", runtime.observe_live)
    monkeypatch.setattr(existing, "sync_legacy_phase", runtime.sync_legacy_phase)
    main._background_update_tick(main.app.state.poi_manager, 1, 0, 0)
    assert observations == []
