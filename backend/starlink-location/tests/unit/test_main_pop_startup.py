"""Live advisory startup preserves optional archive failure isolation."""

import sqlite3

import pytest

import main
from app.api import status as status_api
from app.models.config import SimulationConfig
from app.services.flight_events import live_adapter


@pytest.mark.asyncio
async def test_archive_sqlite_failure_preserves_live_startup_and_pop_status(
    monkeypatch,
):
    config = SimulationConfig(mode="live")

    class LocalLiveCoordinator(main.SimulationCoordinator):
        def __init__(self, config):
            super().__init__(config)
            self.client = None

    def unavailable(_path):
        raise sqlite3.OperationalError("fixture archive unavailable")

    monkeypatch.setattr(main.ConfigManager, "load", lambda self: config)
    monkeypatch.setattr(main, "LiveCoordinator", LocalLiveCoordinator)
    monkeypatch.setattr(main, "refresh_ground_entry_point_metrics", lambda: None)
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    monkeypatch.setattr(live_adapter, "FlightEventRuntime", unavailable)
    try:
        await main.startup_event()
        assert main.app.state.flight_event_runtime is None
        response = await status_api.status()
        assert "pop_forecast" in response
        assert main.app.state.pop_status_service is not None
    finally:
        await main.shutdown_event()
