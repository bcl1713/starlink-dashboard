import main
from app.api import overview_adsb
from fastapi.testclient import TestClient


def test_initializes_and_registers_adsb_runtime(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OVERVIEW_ADSB_SETTINGS_PATH", tmp_path / "adsb.json")
    main.initialize_overview_adsb_runtime()
    try:
        assert main.app.state.overview_adsb_settings_store.get().enabled is False
        assert overview_adsb._store is main.app.state.overview_adsb_settings_store
    finally:
        overview_adsb.set_overview_adsb_runtime(None, None)
        del main.app.state.overview_adsb_settings_store


def test_lifespan_persists_and_cleans_up_adsb(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "OVERVIEW_ADSB_SETTINGS_PATH", tmp_path / "adsb.json")
    with TestClient(main.app) as client:
        assert (
            client.put(
                "/api/overview-adsb/settings", json={"include_hexes": ["00AB12"]}
            ).status_code
            == 200
        )
    assert overview_adsb._store is None
    assert not hasattr(main.app.state, "overview_adsb_settings_store")
    with TestClient(main.app) as client:
        assert client.get("/api/overview-adsb/settings").json()["include_hexes"] == [
            "00AB12"
        ]
