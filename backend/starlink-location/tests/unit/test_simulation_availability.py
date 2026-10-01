"""Generated samples have provenance; failed batches keep their original age."""

import pytest

from app.models.config import SimulationConfig
from app.simulation.coordinator import SimulationCoordinator


@pytest.mark.parametrize("operation", ["initial", "update", "reset", "update_config"])
def test_generated_simulation_metrics_are_available(operation):
    coordinator = SimulationCoordinator(SimulationConfig())
    if operation == "update":
        coordinator.update()
    elif operation == "reset":
        coordinator.reset()
    elif operation == "update_config":
        coordinator.update_config(SimulationConfig())
    assert coordinator.get_current_telemetry().metric_availability.model_dump() == {
        "latency_ms": True,
        "throughput_down_mbps": True,
        "throughput_up_mbps": True,
        "packet_loss_percent": True,
        "obstruction_percent": True,
    }


def test_failed_simulation_batch_keeps_last_observation(monkeypatch):
    coordinator = SimulationCoordinator(SimulationConfig())
    previous = coordinator.get_current_telemetry().model_copy(deep=True)

    def fail():
        raise ValueError("collection failed")

    monkeypatch.setattr(coordinator, "_generate_telemetry", fail)
    result = coordinator.update()
    assert result.timestamp == previous.timestamp
    assert result.model_dump() == previous.model_dump()
