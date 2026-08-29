from unittest.mock import MagicMock

import main
import pytest


@pytest.mark.asyncio
async def test_shutdown_event_stops_route_manager_watcher():
    route_manager = MagicMock()
    original_route_manager = main._route_manager
    original_background_task = main._background_task

    try:
        main._route_manager = route_manager
        main._background_task = None

        await main.shutdown_event()

        route_manager.stop_watching.assert_called_once_with()
    finally:
        main._route_manager = original_route_manager
        main._background_task = original_background_task


@pytest.mark.asyncio
async def test_lifespan_closes_monitoring_client_after_startup_failure(
    monkeypatch,
) -> None:
    created: list[object] = []

    class TrackingMonitoringClient:
        def __init__(self) -> None:
            self.closed = 0
            created.append(self)

        async def aclose(self) -> None:
            self.closed += 1

    class FailingSimulationCoordinator:
        def __init__(self, *_args, **_kwargs) -> None:
            raise RuntimeError("startup failed after monitoring client creation")

    monkeypatch.setattr(main, "MonitoringPrometheusClient", TrackingMonitoringClient)
    monkeypatch.setattr(main, "SimulationCoordinator", FailingSimulationCoordinator)
    monkeypatch.setattr(main, "refresh_ground_entry_point_metrics", lambda: None)
    main.app.state.monitoring_prometheus_client = None

    with pytest.raises(RuntimeError, match="startup failed"):
        async with main.lifespan(main.app):
            pass

    assert len(created) == 1
    assert created[0].closed == 1
    assert main.app.state.monitoring_prometheus_client is None


@pytest.mark.asyncio
async def test_lifespan_repeated_enter_exit_closes_all_monitoring_clients(
    monkeypatch,
) -> None:
    created: list[object] = []

    class TrackingMonitoringClient:
        def __init__(self) -> None:
            self.closed = 0
            created.append(self)

        async def aclose(self) -> None:
            self.closed += 1

    async def startup() -> None:
        main.app.state.monitoring_prometheus_client = TrackingMonitoringClient()

    async def shutdown() -> None:
        return None

    monkeypatch.setattr(main, "startup_event", startup)
    monkeypatch.setattr(main, "shutdown_event", shutdown)
    main.app.state.monitoring_prometheus_client = None

    for _ in range(2):
        async with main.lifespan(main.app):
            assert main.app.state.monitoring_prometheus_client is not None
        assert main.app.state.monitoring_prometheus_client is None

    assert [client.closed for client in created] == [1, 1]
