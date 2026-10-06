import httpx
from fastapi import FastAPI

from app.api import overview_weather
from tests.fixtures.weather_streams import WeatherStreams, http_response
from tests.unit.test_overview_weather_service import metadata, service_for


def weather_app(service, store):
    app = FastAPI()
    app.state.overview_weather_service = service
    app.state.overview_weather_settings_store = store
    app.include_router(overview_weather.router)
    return app


async def test_api_defaults_saves_errors_headers_and_legacy_404(tmp_path):
    streams = WeatherStreams(http_response(metadata()))
    service, store = service_for(tmp_path, streams)
    app = weather_app(service, store)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        response = await client.get("/api/overview-weather/settings")
        assert response.json() == {"enabled": False, "revision": 0}
        assert response.headers["cache-control"] == "no-store"
        for update in [{}, {"enabled": 1}, {"revision": 2}, {"enabled": "true"}]:
            assert (
                await client.put("/api/overview-weather/settings", json=update)
            ).status_code == 422
        assert (
            await client.get("/api/overview-weather/radar/1/2/0/0.png")
        ).status_code == 404
        assert streams.dials == []
        assert (
            await client.put("/api/overview-weather/settings", json={"enabled": True})
        ).json()["revision"] == 1
        assert (await client.get("/api/overview-weather/frame")).json()[
            "state"
        ] == "ready"
        assert (
            await client.get("/api/overview-weather/radar/1/2/0/0.png")
        ).status_code == 404
        assert (
            await client.get("/api/overview-weather/radar/1/3/0/0.png")
        ).status_code == 404
        assert (
            await client.get("/api/weather/radar/rainviewer/2/0/0.png")
        ).status_code == 404
        store._path.write_text("{bad")
        bad = await client.get("/api/overview-weather/settings")
        assert bad.status_code == 503
        assert "{bad" not in bad.text
    await service.aclose()


def test_optional_weather_initialization_failure_keeps_core_api(tmp_path, monkeypatch):
    from unittest.mock import Mock

    from fastapi.testclient import TestClient

    import main

    monkeypatch.setattr(
        main, "OVERVIEW_WEATHER_SETTINGS_PATH", tmp_path / "settings.json"
    )
    monkeypatch.setattr(
        main, "WeatherService", Mock(side_effect=RuntimeError("fixture failure"))
    )
    # Real application lifespan establishes the core coordinator before health.
    with TestClient(main.app) as client:
        assert client.get("/api/overview-weather/frame").status_code == 503
        assert client.get("/api/overview-weather/settings").json()["enabled"] is False
        assert client.get("/api/weather/radar/rainviewer/2/0/0.png").status_code == 404
        assert client.get("/health").status_code == 200
