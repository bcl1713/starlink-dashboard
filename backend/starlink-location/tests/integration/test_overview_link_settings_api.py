import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import overview_link_settings
from app.services.overview_link_settings import OverviewLinkSettingsStore

VISIBLE_DEFAULTS = {
    "operational_clocks_enabled": True,
    "arrival_panel_enabled": True,
    "planned_satellite_panel_enabled": True,
    "map_status_enabled": True,
    "legend_enabled": True,
    "latency_panel_enabled": True,
    "downlink_panel_enabled": True,
    "uplink_panel_enabled": True,
    "packet_loss_panel_enabled": True,
    "obstruction_panel_enabled": True,
    "aircraft_marker_enabled": True,
    "planned_route_enabled": True,
    "poi_markers_enabled": True,
    "ground_entry_point_enabled": True,
    "configured_satellites_enabled": True,
}

URL = "/api/overview-links/settings"


@pytest.fixture
def client(tmp_path):
    store = OverviewLinkSettingsStore(tmp_path / "overview-links.json")
    overview_link_settings.set_overview_link_settings_store(store)
    app = FastAPI()
    app.include_router(overview_link_settings.router)
    with TestClient(app) as test_client:
        yield test_client
    overview_link_settings.set_overview_link_settings_store(None)


def test_get_returns_default_full_pair(client):
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "starshield_link_enabled": True,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }


@pytest.mark.parametrize("starshield", [True, False])
@pytest.mark.parametrize("x_band", [True, False])
def test_put_returns_and_persists_all_pairs(client, starshield, x_band):
    payload = {
        "starshield_link_enabled": starshield,
        "x_band_link_enabled": x_band,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    response = client.put(URL, json=payload)
    assert response.status_code == 200
    assert response.json() == payload
    assert client.get(URL).json() == payload


def test_partial_put_preserves_other_viewers_saved_switch(client):
    first = client.put(URL, json={"starshield_link_enabled": False})
    assert first.json() == {
        "starshield_link_enabled": False,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    second = client.put(URL, json={"x_band_link_enabled": False})
    assert second.status_code == 200
    assert second.json() == {
        "starshield_link_enabled": False,
        "x_band_link_enabled": False,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"unknown": True},
        {"starshield_link_enabled": False, "unknown": True},
        {"starshield_link_enabled": None},
        {"x_band_link_enabled": None},
        {"starshield_link_enabled": "false"},
        {"x_band_link_enabled": "true"},
        {"starshield_link_enabled": 0},
        {"starshield_link_enabled": 1},
        {"x_band_link_enabled": 0.0},
        {"x_band_link_enabled": 1.0},
        {"starshield_link_enabled": []},
        {"x_band_link_enabled": {}},
        None,
        [],
    ],
)
def test_invalid_updates_return_422_and_preserve_last_confirmed_pair(client, payload):
    saved = {
        "starshield_link_enabled": False,
        "x_band_link_enabled": False,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    assert client.put(URL, json=saved).status_code == 200
    response = client.put(URL, json=payload)
    assert response.status_code == 422
    assert client.get(URL).json() == saved


@pytest.mark.parametrize("method", ["get", "put"])
def test_uninitialized_store_returns_503(client, method):
    overview_link_settings.set_overview_link_settings_store(None)
    response = (
        client.get(URL)
        if method == "get"
        else client.put(URL, json={"starshield_link_enabled": False})
    )
    assert response.status_code == 503


@pytest.mark.parametrize("contents", ["{", '{"starshield_link_enabled": 0}'])
@pytest.mark.parametrize("method", ["get", "put"])
def test_invalid_disk_settings_return_503_without_replacement(
    client, tmp_path, contents, method
):
    path = tmp_path / "overview-links.json"
    path.write_text(contents)
    response = (
        client.get(URL)
        if method == "get"
        else client.put(URL, json={"starshield_link_enabled": False})
    )
    assert response.status_code == 503
    assert path.read_text() == contents


def test_failed_write_returns_503_and_keeps_last_confirmed_pair(client, monkeypatch):
    saved = {
        "starshield_link_enabled": False,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    assert client.put(URL, json=saved).status_code == 200

    def fail_replace(*args):
        raise PermissionError("settings directory unavailable")

    monkeypatch.setattr("app.services.overview_link_settings.os.replace", fail_replace)
    assert client.put(URL, json={"x_band_link_enabled": False}).status_code == 503
    assert client.get(URL).json() == saved


def test_failed_read_returns_503(client, tmp_path):
    # A directory in place of the file is an actual filesystem read failure.
    (tmp_path / "overview-links.json").mkdir()
    assert client.get(URL).status_code == 503
    assert client.put(URL, json={"x_band_link_enabled": False}).status_code == 503


def test_orbital_partial_updates_and_interleaved_viewers(client):
    assert client.put(URL, json={"starshield_link_enabled": False}).status_code == 200
    assert client.put(URL, json={"orbital_traffic_enabled": True}).json() == {
        "starshield_link_enabled": False,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": True,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    assert client.put(URL, json={"x_band_link_enabled": False}).json() == {
        "starshield_link_enabled": False,
        "x_band_link_enabled": False,
        "orbital_traffic_enabled": True,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }


@pytest.mark.parametrize("value", [None, "true", 1])
def test_orbital_update_is_strict(client, value):
    before = client.get(URL).json()
    assert client.put(URL, json={"orbital_traffic_enabled": value}).status_code == 422
    assert client.get(URL).json() == before


def test_forward_compatible_saved_settings_remain_editable(client, tmp_path):
    path = tmp_path / "overview-links.json"
    saved = {
        "starshield_link_enabled": False,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": True,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
        "future_preference": {"display": "constellation"},
    }
    path.write_text(json.dumps(saved))
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json() == {
        "starshield_link_enabled": False,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": True,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    response = client.put(URL, json={"x_band_link_enabled": False})
    assert response.status_code == 200
    assert response.json() == {
        "starshield_link_enabled": False,
        "x_band_link_enabled": False,
        "orbital_traffic_enabled": True,
        "aircraft_history_enabled": True,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    assert json.loads(path.read_text()) == {**saved, "x_band_link_enabled": False}
    assert client.put(URL, json={"future_preference": False}).status_code == 422
    assert json.loads(path.read_text()) == {**saved, "x_band_link_enabled": False}


def test_aircraft_history_partial_update_preserves_other_layers(client):
    assert client.get(URL).json()["aircraft_history_enabled"] is True
    response = client.put(URL, json={"aircraft_history_enabled": False})
    assert response.status_code == 200
    assert response.json() == {
        "starshield_link_enabled": True,
        "x_band_link_enabled": True,
        "orbital_traffic_enabled": False,
        "aircraft_history_enabled": False,
        "country_borders_enabled": False,
        "state_borders_enabled": False,
        **VISIBLE_DEFAULTS,
    }
    client.put(URL, json={"orbital_traffic_enabled": True})
    assert client.get(URL).json()["aircraft_history_enabled"] is False
    assert (
        client.put(URL, json={"aircraft_history_enabled": True}).json()[
            "aircraft_history_enabled"
        ]
        is True
    )


@pytest.mark.parametrize("value", [None, "false", 0])
def test_aircraft_history_api_rejects_non_booleans(client, value):
    assert client.put(URL, json={"aircraft_history_enabled": False}).status_code == 200
    assert client.put(URL, json={"aircraft_history_enabled": value}).status_code == 422
    assert client.get(URL).json()["aircraft_history_enabled"] is False


def test_boundary_layers_default_off_and_merge_independently(client, tmp_path):
    initial = client.get(URL).json()
    assert initial["country_borders_enabled"] is False
    assert initial["state_borders_enabled"] is False
    assert client.put(URL, json={"country_borders_enabled": True}).status_code == 200
    assert client.put(URL, json={"state_borders_enabled": True}).status_code == 200
    assert client.put(URL, json={"country_borders_enabled": False}).status_code == 200
    saved = client.get(URL).json()
    assert saved == {**initial, "state_borders_enabled": True}
    # Recreate the process-owned store against the same file.
    overview_link_settings.set_overview_link_settings_store(
        OverviewLinkSettingsStore(tmp_path / "overview-links.json")
    )
    assert client.get(URL).json() == saved


@pytest.mark.parametrize("field", ["country_borders_enabled", "state_borders_enabled"])
@pytest.mark.parametrize("value", [None, "true", 1, []])
def test_boundary_layers_require_boolean_confirmation(client, field, value):
    before = client.get(URL).json()
    assert client.put(URL, json={field: value}).status_code == 422
    assert client.get(URL).json() == before


VISIBILITY_FIELDS = [
    "operational_clocks_enabled",
    "arrival_panel_enabled",
    "planned_satellite_panel_enabled",
    "map_status_enabled",
    "legend_enabled",
    "latency_panel_enabled",
    "downlink_panel_enabled",
    "uplink_panel_enabled",
    "packet_loss_panel_enabled",
    "obstruction_panel_enabled",
    "aircraft_marker_enabled",
    "planned_route_enabled",
    "poi_markers_enabled",
    "ground_entry_point_enabled",
    "configured_satellites_enabled",
]


@pytest.mark.parametrize("field", VISIBILITY_FIELDS)
def test_visibility_preferences_default_visible_and_survive_restart(
    client, tmp_path, field
):
    before = client.get(URL).json()
    assert before[field] is True
    response = client.put(URL, json={field: False})
    assert response.status_code == 200
    assert response.json() == {**before, field: False}
    overview_link_settings.set_overview_link_settings_store(
        OverviewLinkSettingsStore(tmp_path / "overview-links.json")
    )
    assert client.get(URL).json() == {**before, field: False}
    assert client.put(URL, json={field: True}).json() == before


@pytest.mark.parametrize("field", VISIBILITY_FIELDS)
@pytest.mark.parametrize("value", [None, "false", 0])
def test_visibility_updates_require_boolean_confirmation(client, field, value):
    before = client.get(URL).json()
    assert client.put(URL, json={field: value}).status_code == 422
    assert client.get(URL).json() == before
