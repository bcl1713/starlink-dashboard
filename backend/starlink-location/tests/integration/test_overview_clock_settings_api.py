from app.api import overview_clock_settings
from app.services.overview_clock_settings import OverviewClockSettingsStore
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_clock_settings_returns_503_until_its_store_is_initialized():
    overview_clock_settings.set_overview_clock_settings_store(None)
    app = FastAPI()
    app.include_router(overview_clock_settings.router)
    response = TestClient(app).get("/api/overview-clocks/settings")
    assert response.status_code == 503
    assert response.json() == {
        "detail": "Overview clock settings are not yet initialized",
    }


def test_clock_settings_returns_the_four_persisted_clock_records(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview-clock-settings.json")
    overview_clock_settings.set_overview_clock_settings_store(store)
    try:
        app = FastAPI()
        app.include_router(overview_clock_settings.router)
        response = TestClient(app).get("/api/overview-clocks/settings")
    finally:
        overview_clock_settings.set_overview_clock_settings_store(None)
    assert response.status_code == 200
    assert response.json() == {
        "clocks": [
            {
                "label": "Zulu / UTC",
                "time_zone": "UTC",
            },
            {
                "label": "Washington, DC",
                "time_zone": "America/New_York",
            },
            {
                "label": "Omaha, NE",
                "time_zone": "America/Chicago",
            },
            {
                "label": "Tokyo, JP",
                "time_zone": "Asia/Tokyo",
            },
        ]
    }


def test_clock_settings_put_persists_the_complete_edited_collection(tmp_path):
    path = tmp_path / "overview_clock_settings.json"
    store = OverviewClockSettingsStore(path)
    overview_clock_settings.set_overview_clock_settings_store(store)
    payload = {
        "clocks": [
            {
                "label": "Zulu / UTC",
                "time_zone": "UTC",
            },
            {
                "label": "Houston, TX",
                "time_zone": "America/Chicago",
            },
            {
                "label": "Omaha, NE",
                "time_zone": "America/Chicago",
            },
            {
                "label": "Tokyo, JP",
                "time_zone": "Asia/Tokyo",
            },
        ]
    }
    try:
        app = FastAPI()
        app.include_router(overview_clock_settings.router)
        response = TestClient(app).put(
            "/api/overview-clocks/settings",
            json=payload,
        )
    finally:
        overview_clock_settings.set_overview_clock_settings_store(None)
    assert response.status_code == 200
    assert response.json() == payload
    assert [
        {
            "label": clock.label,
            "time_zone": clock.time_zone,
        }
        for clock in OverviewClockSettingsStore(path).get_clocks()
    ] == payload["clocks"]


def test_clock_settings_put_rejects_a_non_four_clock_collection(tmp_path):
    store = OverviewClockSettingsStore(tmp_path / "overview_clock_settings.json")
    overview_clock_settings.set_overview_clock_settings_store(store)
    try:
        app = FastAPI()
        app.include_router(overview_clock_settings.router)
        response = TestClient(
            app,
            raise_server_exceptions=False,
        ).put(
            "/api/overview-clocks/settings",
            json={
                "clocks": [
                    {
                        "label": "Zulu / UTC",
                        "time_zone": "UTC",
                    },
                    {
                        "label": "Washington, DC",
                        "time_zone": "America/New_York",
                    },
                    {
                        "label": "Omaha, NE",
                        "time_zone": "America/Chicago",
                    },
                ]
            },
        )
    finally:
        overview_clock_settings.set_overview_clock_settings_store(None)
    assert response.status_code == 422
    assert response.json() == {"detail": "Exactly four clocks are required"}
