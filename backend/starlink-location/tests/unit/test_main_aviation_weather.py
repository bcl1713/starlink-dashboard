"""Optional aviation initialization never prevents the real core lifespan."""

from fastapi.testclient import TestClient

import main


def test_optional_startup_repairs_legacy_settings_before_serving(tmp_path, monkeypatch):
    import json

    path = tmp_path / "aviation-weather.json"
    path.write_text(
        json.dumps(
            {
                "winds": True,
                "temperature": True,
                "metar": False,
                "taf": False,
                "sigmet": False,
                "revision": 7,
            }
        )
    )
    monkeypatch.setattr(
        main, "OVERVIEW_WEATHER_SETTINGS_PATH", tmp_path / "overview-weather.json"
    )
    monkeypatch.setenv("GFS_ARTIFACT_PATH", str(tmp_path / "gfs"))
    monkeypatch.setenv("GFS_MAILBOX_PATH", str(tmp_path / "mailbox"))
    monkeypatch.setattr(main, "_background_updates_enabled", False)
    with TestClient(main.app):
        saved = json.loads(path.read_bytes())
        assert saved["revision"] == 8
        assert saved["winds"] and not saved["temperature"]
        demand = json.loads((tmp_path / "mailbox/demand.json").read_bytes())
        assert demand["revision"] == 8 and not demand["owners"]


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


def test_optional_route_sigmet_constructor_failure_preserves_core(monkeypatch):
    monkeypatch.setattr(main, "_background_updates_enabled", False)

    def unavailable(*args, **kwargs):
        raise OSError("private notice fixture failure")

    monkeypatch.setattr(main, "RouteSigmetService", unavailable)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/status").status_code == 200
        assert client.get("/api/aviation-weather/v1/settings").status_code == 200
        response = client.get("/api/aviation-weather/v1/route-sigmets")
        assert response.status_code == 503 and "private" not in response.text


def test_route_runtime_failure_preserves_health_and_shutdown_closes_matching_first(
    tmp_path, monkeypatch
):
    from app.services.aviation_weather import route_decode
    from app.services.overview_weather.protocol import WeatherUnavailable

    monkeypatch.setattr(main, "_background_updates_enabled", False)
    monkeypatch.setattr(
        main, "OVERVIEW_WEATHER_SETTINGS_PATH", tmp_path / "overview.json"
    )
    monkeypatch.setenv("GFS_ARTIFACT_PATH", str(tmp_path / "gfs"))
    monkeypatch.setenv("GFS_MAILBOX_PATH", str(tmp_path / "mailbox"))
    order = []
    original_route_close = main.RouteSigmetService.aclose
    original_weather_close = main.AviationWeatherService.aclose

    async def fail(self):
        raise WeatherUnavailable()

    async def unexpected(*args, **kwargs):
        raise AssertionError("Startup must not start source or geometry work")

    async def route_close(self):
        order.append("matching")
        await original_route_close(self)

    async def weather_close(self):
        order.append("bulletins")
        await original_weather_close(self)

    monkeypatch.setattr(main.RouteSigmetService, "read", fail)
    monkeypatch.setattr(main.RouteSigmetService, "aclose", route_close)
    monkeypatch.setattr(main.AviationWeatherService, "aclose", weather_close)
    monkeypatch.setattr(main.AwcTransport, "fetch", unexpected)
    monkeypatch.setattr(route_decode, "evaluate_in_worker", unexpected)
    with TestClient(main.app) as client:
        response = client.get("/api/aviation-weather/v1/route-sigmets")
        assert response.status_code == 503
        assert client.get("/health").status_code == 200
        assert client.get("/api/status").status_code == 200
    assert order == ["matching", "bulletins"]
