import main
from app.api import overview_clock_settings
from fastapi.testclient import TestClient


def test_initializes_the_persistent_overview_clock_settings_store(
    monkeypatch,
    tmp_path,
):
    original_store = main._overview_clock_settings_store
    overview_clock_settings.set_overview_clock_settings_store(None)
    monkeypatch.setattr(
        main,
        "OVERVIEW_CLOCK_SETTINGS_PATH",
        tmp_path / "overview-clock-settings.json",
    )
    try:
        main.initialize_overview_clock_settings_runtime()
        assert main._overview_clock_settings_store is not None
        assert overview_clock_settings._overview_clock_settings_store is (
            main._overview_clock_settings_store
        )
        assert [
            {
                "label": clock.label,
                "time_zone": clock.time_zone,
            }
            for clock in main._overview_clock_settings_store.get_clocks()
        ] == [
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
    finally:
        overview_clock_settings.set_overview_clock_settings_store(None)
        main._overview_clock_settings_store = original_store


def test_lifespan_exposes_and_cleans_up_clock_settings_runtime(
    monkeypatch,
    tmp_path,
):
    original_store = main._overview_clock_settings_store
    overview_clock_settings.set_overview_clock_settings_store(None)
    monkeypatch.setattr(
        main,
        "OVERVIEW_CLOCK_SETTINGS_PATH",
        tmp_path / "overview-clock-settings.json",
    )
    try:
        with TestClient(main.app) as client:
            response = client.get("/api/overview-clocks/settings")
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
        assert main._overview_clock_settings_store is None
        assert overview_clock_settings._overview_clock_settings_store is None
    finally:
        overview_clock_settings.set_overview_clock_settings_store(None)
        main._overview_clock_settings_store = original_store


def test_lifespan_exposes_and_cleans_up_clock_settings_store_on_app_state(
    monkeypatch,
    tmp_path,
):
    original_store = main._overview_clock_settings_store
    monkeypatch.setattr(
        main,
        "OVERVIEW_CLOCK_SETTINGS_PATH",
        tmp_path / "overview-clock-settings.json",
    )
    try:
        with TestClient(main.app):
            assert main.app.state.overview_clock_settings_store is (
                main._overview_clock_settings_store
            )
        assert not hasattr(main.app.state, "overview_clock_settings_store")
    finally:
        main._overview_clock_settings_store = original_store
