import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

import main


@pytest.mark.parametrize("background_enabled", [False, True])
def test_poi_constructor_failure_aborts_lifespan_with_original_error(
    monkeypatch, background_enabled
):
    """A failed required POI store must not expose a ready application."""
    failure = RuntimeError("POI store unavailable")

    def fail_poi_construction():
        raise failure

    monkeypatch.setattr(main, "POIManager", fail_poi_construction)
    monkeypatch.setattr(main, "_background_updates_enabled", background_enabled)
    monkeypatch.setattr(main, "_background_task", None)
    monkeypatch.setattr(main, "_route_manager", None)
    monkeypatch.delattr(main.app.state, "poi_manager", raising=False)

    try:
        with pytest.raises(RuntimeError) as caught, TestClient(main.app):
            pytest.fail("Lifespan unexpectedly started")

        assert caught.value is failure
        assert not hasattr(main.app.state, "poi_manager")
        assert main._background_task is None
    finally:
        asyncio.run(main.shutdown_event())
        if hasattr(main.app.state, "poi_manager"):
            monkeypatch.delattr(main.app.state, "poi_manager")


def test_successful_startup_exposes_poi_manager_even_when_eta_is_unavailable(
    monkeypatch,
):
    """Optional ETA failure must not suppress the required POI API state."""
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    monkeypatch.setattr(main, "_background_task", None)
    monkeypatch.setattr(main, "_route_manager", None)
    monkeypatch.delattr(main.app.state, "poi_manager", raising=False)

    def fail_eta_initialization(_poi_manager):
        raise RuntimeError("ETA unavailable")

    monkeypatch.setattr(main, "initialize_eta_service", fail_eta_initialization)

    try:
        with TestClient(main.app) as client:
            response = client.get("/api/pois/")
            assert response.status_code == 200
            payload = response.json()
            assert isinstance(payload["pois"], list)
            assert payload["total"] == len(payload["pois"])
            assert isinstance(main.app.state.poi_manager, main.POIManager)
            assert client.get("/health").status_code == 200
    finally:
        if hasattr(main.app.state, "poi_manager"):
            monkeypatch.delattr(main.app.state, "poi_manager")


@pytest.mark.asyncio
async def test_shutdown_cancels_background_task_before_stopping_watcher(monkeypatch):
    events = []
    task = asyncio.create_task(asyncio.Event().wait())

    def stop_watching():
        assert task.cancelled()
        events.append("watcher stopped")

    route_manager = SimpleNamespace(stop_watching=stop_watching)
    monkeypatch.setattr(main, "_background_task", task)
    monkeypatch.setattr(main, "_route_manager", route_manager)

    await main.shutdown_event()

    assert task.cancelled()
    assert events == ["watcher stopped"]
    assert main._background_task is None
    assert main._route_manager is None


@pytest.mark.asyncio
async def test_background_loop_retries_after_update_error_and_propagates_cancellation(
    monkeypatch,
):
    attempts = []
    delays = []
    warnings = []

    def update():
        attempts.append("update")
        if len(attempts) == 1:
            raise RuntimeError("transient update failure")

    async def sleep(delay):
        delays.append(delay)
        if len(delays) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main, "_coordinator", SimpleNamespace(update=update))
    monkeypatch.setattr(
        main,
        "_simulation_config",
        SimpleNamespace(mode="simulation", update_interval_seconds=0.25),
    )
    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    monkeypatch.setattr(
        main.logger,
        "warning_json",
        lambda message, **kwargs: warnings.append((message, kwargs)),
    )

    with pytest.raises(asyncio.CancelledError):
        await main._background_update_loop()

    assert len(attempts) == 2
    assert delays == [1.0, 0.25]
    assert warnings[0][0] == "Error in background update"
    assert warnings[0][1]["extra_fields"] == {
        "error": "transient update failure",
        "error_count": 1,
        "update_count": 0,
    }


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
