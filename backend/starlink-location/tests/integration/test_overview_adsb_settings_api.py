import pytest
from app.api import overview_adsb
from app.services.overview_adsb_settings import AdsbSettingsStore
from fastapi import FastAPI
from fastapi.testclient import TestClient

URL = "/api/overview-adsb/settings"


@pytest.fixture
def settings_api(tmp_path):
    path = tmp_path / "a.json"
    store = AdsbSettingsStore(path)
    overview_adsb.set_overview_adsb_runtime(store, None)
    app = FastAPI()
    app.include_router(overview_adsb.router)
    with TestClient(app) as client:
        yield client, path, store
    overview_adsb.set_overview_adsb_runtime(None, None)


def test_partial_settings_api(settings_api):
    client, _, _ = settings_api
    assert client.get(URL).json()["revision"] == 0
    result = client.put(URL, json={"include_hexes": [" 00ab12 ", "00AB12"]})
    assert result.status_code == 200
    assert result.json()["include_hexes"] == ["00AB12"]
    assert client.put(URL, json={"enabled": True}).json()["revision"] == 2


@pytest.mark.parametrize(
    "changes",
    [
        {},
        {"enabled": None},
        {"enabled": 1},
        {"enabled": "true"},
        {"mode": "all"},
        {"mode": None},
        {"include_hexes": None},
        {"include_hexes": "00AB12"},
        *[
            {"include_hexes": [v]}
            for v in ["12345", "1234567", "~AB1234", "ZZ1234", 12, True]
        ],
        {"exclude_hexes": [None]},
        {"callsign_substrings": [1]},
        {"callsign_substrings": "RCH"},
        {"callsign_substrings": None},
        {"revision": 9},
        {"unknown": True},
    ],
)
def test_invalid_updates_return_422_without_changing_disk(settings_api, changes):
    client, path, _ = settings_api
    client.put(URL, json={"enabled": True})
    before = path.read_bytes()
    assert client.put(URL, json=changes).status_code == 422
    assert path.read_bytes() == before


def test_corrupt_settings_return_503_without_replacement(settings_api):
    client, path, _ = settings_api
    path.write_text("{broken")
    assert client.get(URL).status_code == 503
    assert client.put(URL, json={"enabled": True}).status_code == 503
    assert path.read_text() == "{broken"


def test_failed_save_returns_503(settings_api, monkeypatch):
    client, path, _ = settings_api
    client.put(URL, json={"enabled": True})
    before = path.read_bytes()

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr("app.services.overview_adsb_settings.os.replace", fail)
    assert client.put(URL, json={"enabled": False}).status_code == 503
    assert path.read_bytes() == before


def test_uninitialized_store_returns_503(settings_api):
    client, _, _ = settings_api
    overview_adsb.set_overview_adsb_runtime(None, None)
    assert client.get(URL).status_code == 503
