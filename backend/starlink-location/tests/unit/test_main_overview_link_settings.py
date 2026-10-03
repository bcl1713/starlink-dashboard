from fastapi.testclient import TestClient

import main
from app.api import overview_link_settings

URL = "/api/overview-links/settings"


def test_initializes_and_registers_link_settings_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(
        main, "OVERVIEW_LINK_SETTINGS_PATH", tmp_path / "settings/links.json"
    )
    monkeypatch.setattr(main, "_overview_link_settings_store", None)
    try:
        main.initialize_overview_link_settings_runtime()
        store = main._overview_link_settings_store
        assert store is not None
        assert overview_link_settings._overview_link_settings_store is store
        assert main.app.state.overview_link_settings_store is store
        assert store.get().starshield_link_enabled is True
        assert store.get().x_band_link_enabled is True
    finally:
        overview_link_settings.set_overview_link_settings_store(None)
        del main.app.state.overview_link_settings_store


def test_lifespan_exposes_persists_and_cleans_up_link_settings(monkeypatch, tmp_path):
    path = tmp_path / "settings/overview-links.json"
    monkeypatch.setattr(main, "OVERVIEW_LINK_SETTINGS_PATH", path)
    saved = {"starshield_link_enabled": False, "x_band_link_enabled": False}
    with TestClient(main.app) as client:
        assert client.get(URL).json() == {
            "starshield_link_enabled": True,
            "x_band_link_enabled": True,
        }
        assert (
            main.app.state.overview_link_settings_store
            is main._overview_link_settings_store
        )
        assert client.put(URL, json=saved).status_code == 200
    assert main._overview_link_settings_store is None
    assert overview_link_settings._overview_link_settings_store is None
    assert not hasattr(main.app.state, "overview_link_settings_store")
    with TestClient(main.app) as client:
        assert client.get(URL).json() == saved
    assert main._overview_link_settings_store is None
    assert overview_link_settings._overview_link_settings_store is None
