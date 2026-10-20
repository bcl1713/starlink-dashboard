"""Supported mutation paths cannot pass a held model-input admission boundary."""

import threading

import pytest

from app.mission import storage


@pytest.mark.parametrize(
    "writer", ["route", "configuration", "telemetry", "flight", "catalog"]
)
def test_real_publishers_wait_for_model_input_admission(
    service, clock, tmp_path, monkeypatch, writer
):
    from app.core.config import ConfigManager
    from app.models.config import SimulationConfig
    from app.satellites.catalog import Satellite, SatelliteCatalog
    from app.services.flight_state import get_flight_state_manager
    from app.services.route_manager import RouteManager
    from app.simulation.coordinator import SimulationCoordinator
    from tests.operator.fixtures import pop_inputs

    inputs = pop_inputs(clock)
    if writer == "route":
        routes = RouteManager(tmp_path / "routes")
        mutation = lambda: routes.add_route("changed", inputs["route"])
    elif writer == "configuration":
        manager = ConfigManager()
        monkeypatch.setattr(manager, "_config", SimulationConfig())
        mutation = lambda: manager.update_config({"update_interval_seconds": 2.0})
    elif writer == "telemetry":
        coordinator = SimulationCoordinator(SimulationConfig())
        mutation = lambda: coordinator.restore_telemetry(None)
    elif writer == "flight":
        flight = get_flight_state_manager()
        checkpoint = flight.checkpoint()
        mutation = lambda: flight.restore_checkpoint(checkpoint)
    else:
        catalog = SatelliteCatalog()
        mutation = lambda: catalog.add_satellite(
            Satellite("guard-test", "X", longitude=0)
        )
    entered, finished = threading.Event(), threading.Event()
    failures = []

    def write():
        entered.set()
        try:
            mutation()
        except BaseException as error:  # noqa: BLE001 - forward owned worker failure
            failures.append(error)
        finally:
            finished.set()

    worker = threading.Thread(target=write, name="operator-model-input-test")
    try:
        with storage.get_active_leg_lock():
            worker.start()
            assert entered.wait(1)
            assert not finished.wait(0.05), f"{writer} bypassed input admission"
    finally:
        worker.join(timeout=5)
    assert not worker.is_alive()
    assert not failures
    assert finished.is_set()
