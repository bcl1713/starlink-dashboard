import asyncio
import sys
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock

import main
import pytest

STATE_KEYS = (
    "coordinator",
    "poi_manager",
    "route_manager",
    "monitoring_prometheus_client",
    "rainviewer_radar_service",
)


@pytest.fixture(autouse=True)
def clean_lifespan_state(monkeypatch):
    original = {
        "coordinator": main._coordinator,
        "background_task": main._background_task,
        "simulation_config": main._simulation_config,
        "route_manager": main._route_manager,
        "poi_manager": main._poi_manager,
        "eta_service_initialized": main._eta_service_initialized,
        "lifespan_state_keys": set(main._lifespan_state_keys),
        "lifespan_owned_resources": dict(main._lifespan_owned_resources),
        "background_enabled": main._background_updates_enabled,
    }
    state_snapshot = dict(main.app.state._state)

    main._coordinator = None
    main._background_task = None
    main._simulation_config = None
    main._route_manager = None
    main._poi_manager = None
    main._eta_service_initialized = False
    main._lifespan_state_keys.clear()
    main._lifespan_owned_resources.clear()
    for key in STATE_KEYS:
        main.app.state._state.pop(key, None)

    monkeypatch.setattr(main.health, "set_coordinator", MagicMock())
    monkeypatch.setattr(main.status, "set_coordinator", MagicMock())
    monkeypatch.setattr(main.config, "set_coordinator", MagicMock())
    monkeypatch.setattr(main.pois, "set_coordinator", MagicMock())
    monkeypatch.setattr(main.gps, "set_starlink_client", MagicMock())
    monkeypatch.setattr(main, "refresh_ground_entry_point_metrics", lambda: None)
    monkeypatch.setattr(main, "_background_updates_enabled", False)

    yield

    if main._background_task is not None:
        main._background_task.cancel()
    main._coordinator = original["coordinator"]
    main._background_task = original["background_task"]
    main._simulation_config = original["simulation_config"]
    main._route_manager = original["route_manager"]
    main._poi_manager = original["poi_manager"]
    main._eta_service_initialized = original["eta_service_initialized"]
    main._lifespan_state_keys.clear()
    main._lifespan_state_keys.update(original["lifespan_state_keys"])
    main._lifespan_owned_resources.clear()
    main._lifespan_owned_resources.update(original["lifespan_owned_resources"])
    main._background_updates_enabled = original["background_enabled"]
    main.app.state._state.clear()
    main.app.state._state.update(state_snapshot)


class TrackingMonitoringClient:
    instances: ClassVar[list["TrackingMonitoringClient"]] = []

    def __init__(self, *, close_error: BaseException | None = None) -> None:
        self.close_error = close_error
        self.closed = 0
        TrackingMonitoringClient.instances.append(self)

    async def aclose(self) -> None:
        self.closed += 1
        if self.close_error is not None:
            raise self.close_error


class BlockingMonitoringClient(TrackingMonitoringClient):
    def __init__(self, *, entered: asyncio.Event, release: asyncio.Event) -> None:
        super().__init__()
        self.entered = entered
        self.release = release

    async def aclose(self) -> None:
        self.closed += 1
        self.entered.set()
        await self.release.wait()


class TrackingRainViewerService:
    instances: ClassVar[list["TrackingRainViewerService"]] = []

    def __init__(self, *, close_error: BaseException | None = None) -> None:
        self.close_error = close_error
        self.closed = 0
        TrackingRainViewerService.instances.append(self)

    async def aclose(self) -> None:
        self.closed += 1
        if self.close_error is not None:
            raise self.close_error


class FakeCoordinator:
    def __init__(self, _config) -> None:
        self.route_manager = None

    def get_uptime_seconds(self) -> float:
        return 1.0

    def set_route_manager(self, route_manager) -> None:
        self.route_manager = route_manager


class FakeRouteManager:
    instances: ClassVar[list["FakeRouteManager"]] = []

    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.stopped = asyncio.Event()
        FakeRouteManager.instances.append(self)

    def start_watching(self) -> None:
        self.started.set()

    def stop_watching(self) -> None:
        self.stopped.set()

    def get_active_route(self):
        return None


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        mode="simulation",
        update_interval_seconds=60,
        route=SimpleNamespace(pattern="circular"),
    )


def _assert_owned_state_clean() -> None:
    assert main._coordinator is None
    assert main._background_task is None
    assert main._route_manager is None
    for key in STATE_KEYS:
        assert key not in main.app.state._state


def _patch_startup_basics(monkeypatch) -> None:
    TrackingMonitoringClient.instances.clear()
    TrackingRainViewerService.instances.clear()
    FakeRouteManager.instances.clear()
    config_manager = MagicMock()
    config_manager.load.return_value = _config()
    monkeypatch.setattr(main, "ConfigManager", lambda: config_manager)
    monkeypatch.setattr(main, "MonitoringPrometheusClient", TrackingMonitoringClient)
    monkeypatch.setattr(main, "RainViewerRadarService", TrackingRainViewerService)
    monkeypatch.setattr(main, "SimulationCoordinator", FakeCoordinator)
    monkeypatch.setattr(main, "set_service_info", MagicMock())


@pytest.mark.asyncio
async def test_failure_after_coordinator_registration_cleans_owned_state(
    monkeypatch,
) -> None:
    _patch_startup_basics(monkeypatch)

    main.pois.set_coordinator.side_effect = RuntimeError(
        "startup failed after coordinator registration"
    )

    with pytest.raises(RuntimeError, match="coordinator registration"):
        async with main.lifespan(main.app):
            pass

    assert len(TrackingMonitoringClient.instances) == 1
    assert TrackingMonitoringClient.instances[0].closed == 1
    _assert_owned_state_clean()
    main.health.set_coordinator.assert_any_call(None)
    main.status.set_coordinator.assert_any_call(None)
    main.config.set_coordinator.assert_any_call(None)
    main.pois.set_coordinator.assert_any_call(None)


@pytest.mark.asyncio
async def test_failure_after_route_manager_initialization_cleans_resources(
    monkeypatch,
) -> None:
    _patch_startup_basics(monkeypatch)
    eta_shutdown = MagicMock()
    monkeypatch.setattr(main, "POIManager", MagicMock)
    monkeypatch.setattr(main, "initialize_eta_service", MagicMock())
    monkeypatch.setattr(main, "shutdown_eta_service", eta_shutdown)
    monkeypatch.setattr(main, "RouteManager", FakeRouteManager)

    flight_state_module = SimpleNamespace(
        get_flight_state_manager=MagicMock(
            side_effect=RuntimeError("flight state failed after route manager")
        )
    )
    monkeypatch.setitem(sys.modules, "app.services.flight_state", flight_state_module)

    with pytest.raises(RuntimeError, match="flight state failed"):
        async with main.lifespan(main.app):
            pass

    assert len(TrackingMonitoringClient.instances) == 1
    assert TrackingMonitoringClient.instances[0].closed == 1
    assert len(FakeRouteManager.instances) == 1
    assert FakeRouteManager.instances[0].started.is_set()
    assert FakeRouteManager.instances[0].stopped.is_set()
    eta_shutdown.assert_called_once_with()
    _assert_owned_state_clean()


@pytest.mark.asyncio
async def test_monitoring_aclose_raises_once_and_detaches_state(
    monkeypatch,
) -> None:
    close_error = RuntimeError("secret token should not be logged")
    client = TrackingMonitoringClient(close_error=close_error)
    main.app.state.monitoring_prometheus_client = client
    main._lifespan_owned_resources["monitoring_prometheus_client"] = client

    with pytest.raises(RuntimeError, match="secret token"):
        await main.shutdown_event()

    assert client.closed == 1
    assert "monitoring_prometheus_client" not in main.app.state._state

    await main.shutdown_event()

    assert client.closed == 1


@pytest.mark.asyncio
async def test_owned_rainviewer_service_closes_once_and_detaches_state() -> None:
    service = TrackingRainViewerService()
    main.app.state.rainviewer_radar_service = service
    main._lifespan_owned_resources["rainviewer_radar_service"] = service

    await main.shutdown_event()
    await main.shutdown_event()

    assert service.closed == 1
    assert "rainviewer_radar_service" not in main.app.state._state
    assert "rainviewer_radar_service" not in main._lifespan_owned_resources


@pytest.mark.asyncio
async def test_rainviewer_close_error_takes_precedence_without_primary() -> None:
    close_error = RuntimeError("rainviewer close failure")
    service = TrackingRainViewerService(close_error=close_error)
    main.app.state.rainviewer_radar_service = service
    main._lifespan_owned_resources["rainviewer_radar_service"] = service

    with pytest.raises(RuntimeError, match="rainviewer close failure"):
        await main.shutdown_event()

    assert service.closed == 1
    assert "rainviewer_radar_service" not in main.app.state._state


@pytest.mark.asyncio
async def test_unowned_monitoring_client_survives_cleanup() -> None:
    client = TrackingMonitoringClient()
    main.app.state.monitoring_prometheus_client = client

    await main.shutdown_event()

    assert client.closed == 0
    assert main.app.state.monitoring_prometheus_client is client


@pytest.mark.asyncio
async def test_replacement_monitoring_client_survives_owned_cleanup() -> None:
    owned = TrackingMonitoringClient()
    replacement = TrackingMonitoringClient()
    main.app.state.monitoring_prometheus_client = replacement
    main._lifespan_owned_resources["monitoring_prometheus_client"] = owned

    await main.shutdown_event()

    assert owned.closed == 0
    assert replacement.closed == 0
    assert main.app.state.monitoring_prometheus_client is replacement


@pytest.mark.asyncio
async def test_concurrent_cleanup_closes_owned_monitoring_client_once() -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    client = BlockingMonitoringClient(entered=entered, release=release)
    main.app.state.monitoring_prometheus_client = client
    main._lifespan_owned_resources["monitoring_prometheus_client"] = client

    first = asyncio.create_task(main.shutdown_event())
    await entered.wait()
    second = asyncio.create_task(main.shutdown_event())
    await asyncio.sleep(0)

    assert client.closed == 1
    assert "monitoring_prometheus_client" not in main.app.state._state
    assert "monitoring_prometheus_client" not in main._lifespan_owned_resources

    release.set()
    await first
    await second

    assert client.closed == 1


@pytest.mark.asyncio
async def test_lifespan_constructs_and_closes_rainviewer_service(monkeypatch) -> None:
    _patch_startup_basics(monkeypatch)
    monkeypatch.setattr(main, "POIManager", MagicMock)
    monkeypatch.setattr(main, "initialize_eta_service", MagicMock())
    monkeypatch.setattr(main, "shutdown_eta_service", MagicMock())
    monkeypatch.setattr(main, "RouteManager", FakeRouteManager)

    flight_state = MagicMock()
    flight_state.get_status.return_value = SimpleNamespace(
        phase=SimpleNamespace(value="pre_departure"),
        eta_mode=SimpleNamespace(value="anticipated"),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.flight_state",
        SimpleNamespace(get_flight_state_manager=lambda: flight_state),
    )

    async with main.lifespan(main.app):
        assert len(TrackingRainViewerService.instances) == 1
        assert (
            main.app.state.rainviewer_radar_service
            is TrackingRainViewerService.instances[0]
        )

    assert TrackingRainViewerService.instances[0].closed == 1
    _assert_owned_state_clean()


@pytest.mark.asyncio
async def test_startup_primary_exception_survives_cleanup_exception(
    monkeypatch,
) -> None:
    _patch_startup_basics(monkeypatch)
    cleanup_errors: list[dict] = []

    class FailingCloseMonitoringClient(TrackingMonitoringClient):
        def __init__(self) -> None:
            super().__init__(close_error=RuntimeError("cleanup failure with secret"))

    def record_cleanup_error(message, extra_fields=None, **_kwargs):
        cleanup_errors.append({"message": message, "extra_fields": extra_fields})

    main.pois.set_coordinator.side_effect = RuntimeError("primary startup failure")
    monkeypatch.setattr(
        main, "MonitoringPrometheusClient", FailingCloseMonitoringClient
    )
    monkeypatch.setattr(main.logger, "error_json", record_cleanup_error)

    with pytest.raises(RuntimeError, match="primary startup failure"):
        async with main.lifespan(main.app):
            pass

    assert len(TrackingMonitoringClient.instances) == 1
    assert TrackingMonitoringClient.instances[0].closed == 1
    assert "monitoring_prometheus_client" not in main.app.state._state
    assert any(
        error["message"] == "Error during lifespan cleanup" for error in cleanup_errors
    )
    assert all(
        "secret" not in str(error.get("extra_fields"))
        for error in cleanup_errors
        if error["message"] == "Error during lifespan cleanup"
    )


@pytest.mark.asyncio
async def test_successful_lifespan_after_failed_startup_cleans_normally(
    monkeypatch,
) -> None:
    _patch_startup_basics(monkeypatch)
    main.pois.set_coordinator.side_effect = RuntimeError("first startup failed")
    monkeypatch.setattr(main, "POIManager", MagicMock)
    monkeypatch.setattr(main, "initialize_eta_service", MagicMock())
    monkeypatch.setattr(main, "shutdown_eta_service", MagicMock())
    monkeypatch.setattr(main, "RouteManager", FakeRouteManager)

    flight_state = MagicMock()
    flight_state.get_status.return_value = SimpleNamespace(
        phase=SimpleNamespace(value="pre_departure"),
        eta_mode=SimpleNamespace(value="anticipated"),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.flight_state",
        SimpleNamespace(get_flight_state_manager=lambda: flight_state),
    )

    with pytest.raises(RuntimeError, match="first startup failed"):
        async with main.lifespan(main.app):
            pass
    _assert_owned_state_clean()

    main.pois.set_coordinator.side_effect = None
    async with main.lifespan(main.app):
        assert main.app.state.coordinator is main._coordinator
        assert main.app.state.route_manager is main._route_manager
        assert main.app.state.monitoring_prometheus_client is not None

    assert [client.closed for client in TrackingMonitoringClient.instances] == [1, 1]
    assert all(
        route_manager.stopped.is_set() for route_manager in FakeRouteManager.instances
    )
    _assert_owned_state_clean()


@pytest.mark.asyncio
async def test_lifespan_retains_preexisting_monitoring_client(monkeypatch) -> None:
    _patch_startup_basics(monkeypatch)
    monkeypatch.setattr(main, "POIManager", MagicMock)
    monkeypatch.setattr(main, "initialize_eta_service", MagicMock())
    monkeypatch.setattr(main, "shutdown_eta_service", MagicMock())
    monkeypatch.setattr(main, "RouteManager", FakeRouteManager)
    preexisting = TrackingMonitoringClient()
    main.app.state.monitoring_prometheus_client = preexisting

    flight_state = MagicMock()
    flight_state.get_status.return_value = SimpleNamespace(
        phase=SimpleNamespace(value="pre_departure"),
        eta_mode=SimpleNamespace(value="anticipated"),
    )
    monkeypatch.setitem(
        sys.modules,
        "app.services.flight_state",
        SimpleNamespace(get_flight_state_manager=lambda: flight_state),
    )

    async with main.lifespan(main.app):
        assert main.app.state.monitoring_prometheus_client is preexisting

    assert preexisting.closed == 0
    assert main.app.state.monitoring_prometheus_client is preexisting
    assert "monitoring_prometheus_client" not in main._lifespan_owned_resources


@pytest.mark.asyncio
async def test_repeated_cleanup_is_idempotent_and_awaits_background_task() -> None:
    started = asyncio.Event()
    cancelled = asyncio.Event()
    finalized = asyncio.Event()

    async def background() -> None:
        try:
            started.set()
            await cancelled.wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise
        finally:
            finalized.set()

    client = TrackingMonitoringClient()
    route_manager = FakeRouteManager()
    task = asyncio.create_task(background())

    main._coordinator = FakeCoordinator(_config())
    main._background_task = task
    main._poi_manager = object()
    main._route_manager = route_manager
    main.app.state.coordinator = main._coordinator
    main.app.state.poi_manager = main._poi_manager
    main.app.state.route_manager = route_manager
    main.app.state.monitoring_prometheus_client = client
    main._lifespan_owned_resources["monitoring_prometheus_client"] = client

    await started.wait()
    await main.shutdown_event()
    await main.shutdown_event()

    assert cancelled.is_set()
    assert finalized.is_set()
    assert task.cancelled()
    assert route_manager.stopped.is_set()
    assert client.closed == 1
    _assert_owned_state_clean()
