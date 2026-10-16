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
