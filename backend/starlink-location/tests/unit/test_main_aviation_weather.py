"""Optional aviation initialization never prevents the real core lifespan."""

import main
from fastapi.testclient import TestClient


def test_optional_aviation_constructor_failure_preserves_core_health(monkeypatch):
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    monkeypatch.delattr(main.app.state, "aviation_weather_service", raising=False)
    monkeypatch.delattr(
        main.app.state, "aviation_weather_settings_store", raising=False
    )

    def unavailable(_path):
        raise OSError("private fixture settings failure")

    monkeypatch.setattr(main, "AviationSettingsStore", unavailable)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/status").status_code == 200
        response = client.get("/api/aviation-weather/v1/catalog")
        assert response.status_code == 503
        assert response.json() == {"detail": "Aviation weather unavailable"}
    assert not hasattr(main.app.state, "aviation_weather_service")


def test_optional_gfs_constructor_failure_preserves_bulletins_and_core(monkeypatch):
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    monkeypatch.delattr(main.app.state, "aviation_gfs_bridge", raising=False)

    def unavailable(*args, **kwargs):
        raise OSError("private fixture mailbox failure")

    monkeypatch.setattr(main, "GfsBridge", unavailable)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/status").status_code == 200
        assert client.get("/api/aviation-weather/v1/settings").status_code == 200
        catalog = client.get("/api/aviation-weather/v1/catalog")
        assert catalog.status_code == 200
        assert catalog.json()["products"][-2]["state"] == "off"
    assert not hasattr(main.app.state, "aviation_gfs_bridge")
