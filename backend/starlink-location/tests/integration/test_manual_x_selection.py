"""Manual selection, storage failures and mission ownership through the real API."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import active_x_link
from app.mission import storage
from app.mission.dependencies import get_poi_manager, get_route_manager
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.models.poi import POICreate
from app.satellites.routes import router as satellites_router
from app.services.poi_manager import POIManager

URL = "/api/active-x-link"


@pytest.fixture
def client(tmp_path, monkeypatch, coordinator):
    from app.services.x_band_selection import XBandSelectionStore

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    pois = POIManager(tmp_path / "pois.json")
    for name, transport, longitude in [
        ("X-A", "X", 30),
        ("X-B", "X", -70),
        ("Ka-A", "Ka", 60),
    ]:
        pois.create_poi(
            POICreate(
                name=name,
                icon=transport,
                category="satellite",
                latitude=0,
                longitude=longitude,
            )
        )
    app = FastAPI()
    app.state.x_band_selection_store = XBandSelectionStore(tmp_path / "selection.json")
    app.state.coordinator = coordinator
    app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: None
    )
    app.dependency_overrides[get_poi_manager] = lambda: pois
    app.include_router(active_x_link.router)
    app.include_router(satellites_router)
    with TestClient(app) as test_client:
        yield test_client


def select(client, satellite_id):
    return client.put(f"{URL}/selection", json={"satellite_id": satellite_id})


def set_mission(active, satellite_id="X-B"):
    storage.save_mission_v2(
        Mission(
            id="manual-test",
            name="Manual test",
            legs=[
                MissionLeg(
                    id="manual-leg",
                    name="Leg",
                    route_id="missing-route",
                    is_active=active,
                    transports=TransportConfig(initial_x_satellite_id=satellite_id),
                )
            ],
        )
    )


def test_switch_and_clear_update_all_active_link_consumers(client):
    assert client.get(URL).json()["satellite_id"] is None
    for name, longitude in [("X-A", 30), ("X-B", -70)]:
        response = select(client, name)
        assert response.status_code == 200
        data = client.get(URL).json()
        assert data["satellite_id"] == data["manual_satellite_id"] == name
        assert data["selection_source"] == "manual"
        assert data["links"][0]["satellite_id"] == name
        assert data["coordinates"][1]["longitude"] == longitude
        filtered = client.get(URL, params={"state": "warning"}).json()
        assert filtered["satellite_id"] == name
    assert select(client, None).status_code == 200
    assert client.get(URL).json()["satellite_id"] is None
    assert client.get(URL).json()["links"] == []


def test_persists_across_new_store_instances(client, tmp_path):
    from app.services.x_band_selection import XBandSelectionStore

    assert select(client, "X-A").status_code == 200
    client.app.state.x_band_selection_store = XBandSelectionStore(
        tmp_path / "selection.json"
    )
    assert client.get(URL).json()["satellite_id"] == "X-A"


def test_selection_does_not_require_telemetry(client):
    client.app.state.coordinator = None
    assert select(client, "X-A").status_code == 200
    data = client.get(URL).json()
    assert data["satellite_id"] == "X-A"
    assert data["coordinates"] == []
    assert data["state"] is None


def test_missing_mission_telemetry_does_not_revert_to_initial_or_manual_selection(
    client,
):
    assert select(client, "X-A").status_code == 200
    set_mission(True)
    client.app.state.coordinator = None
    data = client.get(URL).json()
    assert data["satellite_id"] is None
    assert data["selection_source"] == "mission"
    assert data["manual_satellite_id"] == "X-A"


def test_mission_overrides_and_restores_manual_selection(client):
    assert select(client, "X-A").status_code == 200
    set_mission(True)
    data = client.get(URL).json()
    assert data["satellite_id"] == "X-B"
    assert data["selection_source"] == "mission"
    assert data["manual_satellite_id"] == "X-A"
    assert select(client, "X-B").status_code == 409
    assert select(client, None).status_code == 409
    set_mission(False)
    assert client.get(URL).json()["satellite_id"] == "X-A"


def test_mission_without_satellite_never_falls_back_to_manual(client):
    assert select(client, "X-A").status_code == 200
    set_mission(True, "")
    data = client.get(URL).json()
    assert data["selection_source"] == "mission"
    assert data["satellite_id"] is None
    assert select(client, "X-B").status_code == 409


@pytest.mark.parametrize("name", ["missing", "Ka-A"])
def test_rejects_unknown_and_non_x_satellites_without_changing_selection(client, name):
    assert select(client, "X-A").status_code == 200
    assert select(client, name).status_code == 422
    assert client.get(URL).json()["satellite_id"] == "X-A"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"satellite_id": ""},
        {"satellite_id": " "},
        {"satellite_id": 1},
        {"satellite_id": "X-A", "extra": True},
    ],
)
def test_strict_payload(client, payload):
    assert client.put(f"{URL}/selection", json=payload).status_code == 422
    assert client.get(URL).json()["satellite_id"] is None


def test_removed_or_changed_satellite_is_no_longer_selected(client):
    assert select(client, "X-A").status_code == 200
    assert (
        client.put("/api/satellites/X-A", json={"transport": "Ka"}).status_code == 200
    )
    data = client.get(URL).json()
    assert data["satellite_id"] is None
    assert data["manual_selection_invalid"] is True
    assert data["links"] == []
    assert select(client, "X-B").status_code == 200
    assert client.delete("/api/satellites/X-B").status_code == 204
    assert client.get(URL).json()["satellite_id"] is None
    assert select(client, None).status_code == 200
    assert client.get(URL).json()["manual_selection_invalid"] is False


def test_save_failure_preserves_previous_selection(client, monkeypatch, tmp_path):
    assert select(client, "X-A").status_code == 200

    def fail_replace(*args):
        raise PermissionError("read only")

    monkeypatch.setattr("app.services.x_band_selection.os.replace", fail_replace)
    assert select(client, "X-B").status_code == 503
    assert client.get(URL).json()["satellite_id"] == "X-A"
    assert list(tmp_path.glob("*.tmp")) == []


def test_response_failure_does_not_commit_a_selection_reported_as_failed(client):
    assert select(client, "X-A").status_code == 200

    def unavailable_route():
        raise OSError("route state unavailable")

    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=unavailable_route
    )
    assert select(client, "X-B").status_code == 503
    client.app.dependency_overrides[get_route_manager] = lambda: SimpleNamespace(
        get_active_route=lambda: None
    )
    assert client.get(URL).json()["satellite_id"] == "X-A"


@pytest.mark.parametrize("contents", ["{", '{"satellite_id": 3}'])
def test_corrupt_storage_is_unavailable_and_not_overwritten(client, tmp_path, contents):
    (tmp_path / "selection.json").write_text(contents)
    assert client.get(URL).status_code == 503
    assert select(client, "X-A").status_code == 503
    assert (tmp_path / "selection.json").read_text() == contents


@pytest.mark.parametrize("contents", ["{", '{"satellite_id": 3}'])
def test_mission_selection_survives_unreadable_manual_settings(
    client, tmp_path, contents
):
    set_mission(True)
    (tmp_path / "selection.json").write_text(contents)
    response = client.get(URL)
    assert response.status_code == 200
    assert response.json()["satellite_id"] == "X-B"
    assert response.json()["selection_source"] == "mission"
    assert response.json()["manual_selection_unavailable"] is True
    assert select(client, "X-A").status_code == 409
    assert (tmp_path / "selection.json").read_text() == contents
    set_mission(False)
    assert client.get(URL).status_code == 503
