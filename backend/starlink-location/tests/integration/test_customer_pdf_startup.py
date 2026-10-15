"""An optional derived PDF cache must not prevent the core API starting."""

import asyncio
import sqlite3

from fastapi.testclient import TestClient

import main
from app.mission.slide_cache import coordinator
from app.services.route_manager import RouteManager


def test_optional_pdf_startup_failure_preserves_core_api(monkeypatch):
    attempts = []

    def broken_start(*_):
        attempts.append(True)
        raise sqlite3.DatabaseError("Derived cache corrupt")

    async def idle_background(_):
        await asyncio.Event().wait()

    monkeypatch.setattr(coordinator, "start_runtime", broken_start)
    monkeypatch.setattr(main, "_background_updates_enabled", True)
    monkeypatch.setattr(main, "_background_update_loop", idle_background)
    monkeypatch.setattr(RouteManager, "start_watching", lambda _: None)
    with TestClient(main.app) as client:
        assert attempts
        assert main.app.state.coordinator is not None
        assert main.app.state.route_manager is not None
        assert main.app.state.poi_manager is not None
        assert not hasattr(main.app.state, "customer_pdf_coordinator")
        assert client.get("/health").status_code == 200
        assert client.get("/api/v2/missions").status_code == 200
    assert main._background_task is None
