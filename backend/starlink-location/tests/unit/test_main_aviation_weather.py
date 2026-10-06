"""Optional aviation initialization never prevents the real core lifespan."""

from fastapi.testclient import TestClient

import main


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
