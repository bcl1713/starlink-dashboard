"""Production status wiring consumes captured evidence without mission rebuilds."""

import pytest

import main
from app.core.config import ConfigManager
from app.mission import pop_capabilities, pop_continuity
from tests.integration.test_simulation_pop_status import pop_api, start_paced
from tests.integration.test_simulation_run_api import api

__all__ = ["api", "pop_api"]


def test_replay_status_reuses_immutable_prepared_capabilities(pop_api, monkeypatch):
    client, service, _, _, _ = pop_api
    monkeypatch.setattr(
        ConfigManager, "get_config", lambda self: service.coordinator.config
    )
    start_paced(client, 10)
    artifacts = service.runtime.selected_plan().artifacts
    assert artifacts.call_capabilities is not None

    def forbidden(*args, **kwargs):
        pytest.fail("Status must reuse captured capability inputs")

    monkeypatch.setattr(pop_capabilities, "capture_call_capabilities", forbidden)
    monkeypatch.setattr(pop_continuity, "capabilities_from_timeline", forbidden)
    assert (
        main._simulation_pop_context()["call_capabilities"]
        is artifacts.call_capabilities
    )
    saved = artifacts.timeline.call_continuity.model_dump()
    for _ in range(2):
        response = client.get("/api/status")
        assert response.status_code == 200
        payload = response.json()
        assert payload["call_continuity"] is not None
        assert (
            payload["call_continuity"]["revision"]
            == payload["pop_forecast"]["revision"]
        )
    assert artifacts.timeline.call_continuity.model_dump() == saved


@pytest.mark.parametrize("observation_known", [True, False])
def test_first_status_after_replay_crossing_reconciles_captured_occurrence(
    pop_api, monkeypatch, observation_known
):
    from app.simulation.pop import unknown_simulation_observation

    client, service, clocks, pops, _ = pop_api
    monkeypatch.setattr(
        ConfigManager, "get_config", lambda self: service.coordinator.config
    )
    start_paced(client, 10)
    artifacts = service.runtime.selected_plan().artifacts
    saved = artifacts.timeline.model_dump()
    clocks.advance(21)  # Crossing at mission second 150; first status at T + 60.
    service.collect(service.coordinator, service.publish)
    if not observation_known:
        pops.observation_provider = lambda *args: unknown_simulation_observation()
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pop_forecast"]["transitions"] == []
    assert payload["pop_observation"]["status"] == (
        "known" if observation_known else "unknown"
    )
    assert len(pops.state.completed_ids) == int(observation_known)
    assert {a["kind"] for a in payload["pop_advisories"]} == (
        set() if observation_known else {"observation_unknown", "window"}
    )
    assert payload["call_continuity"] is not None
    assert artifacts.timeline.model_dump() == saved
    assert payload["network"]["packet_loss_percent"] is None
    assert payload["metric_availability"]["packet_loss_percent"] is False
    assert service.status().run.transport_states["Ku"] == "available"
