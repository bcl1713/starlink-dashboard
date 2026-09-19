from fastapi import FastAPI
from starlette.requests import Request
from app.mission.dependencies import get_overview_clock_settings_store
from app.services.overview_clock_settings import OverviewClockSettingsStore


def test_returns_the_clock_settings_store_from_application_state(tmp_path):
    app = FastAPI()
    store = OverviewClockSettingsStore(
        tmp_path / "overview-clock-settings.json",
    )
    app.state.overview_clock_settings_store = store
    request = Request(
        {
            "type": "http",
            "app": app,
        }
    )
    assert get_overview_clock_settings_store(request) is store
