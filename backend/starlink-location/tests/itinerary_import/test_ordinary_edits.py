"""An imported leg must support the same edit APIs as a manual leg."""

from datetime import timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission import routes_v2, storage

from .test_creation_api import importer, kml_bytes, pdf_bytes, wait  # noqa: F401


@pytest.fixture
def ordinary(importer):  # noqa: F811 - imported pytest fixture
    client, service = importer
    op = service.start(pdf_bytes(), [("r.kml", kml_bytes())], "edit")
    result = wait(client, op.id)
    assert result["state"] == "committed", result
    app = FastAPI()
    app.state.itinerary_import_service = service
    app.include_router(routes_v2.router)
    app.dependency_overrides[routes_v2.get_route_manager] = (
        lambda: service.route_manager
    )
    app.dependency_overrides[routes_v2.get_poi_manager] = lambda: service.poi_manager
    with TestClient(app) as api:
        yield api, service, storage.load_mission_v2(op.mission_id)


def test_takeoff_and_transport_edits_rebuild_timeline_without_optimizer(ordinary):
    api, service, mission = ordinary
    leg = mission.legs[0]
    route = service.route_manager.get_route(leg.route_id)
    leg.adjusted_departure_time = route.timing_profile.departure_time + timedelta(
        hours=1
    )
    leg.transports.initial_ka_satellite_ids = ["invented-ka"]
    response = api.put(
        f"/api/v2/missions/{mission.id}/legs/{leg.id}", json=leg.model_dump(mode="json")
    )
    assert response.status_code == 200, response.text
    assert not response.json().get("warnings"), response.json()
    saved = storage.load_mission_v2(mission.id).legs[0]
    assert saved.transports.initial_ka_satellite_ids == ["invented-ka"]
    assert saved.transports.initial_x_satellite_id == "X-invented"
    timeline = storage.load_mission_timeline(leg.id, parent_mission_id=mission.id)
    assert timeline.segments[0].start_time == leg.adjusted_departure_time


def test_ordinary_route_replacement_replaces_hash_and_keeps_plan(ordinary):
    api, service, mission = ordinary
    leg = mission.legs[0]
    old = leg.route_id
    response = api.put(
        f"/api/v2/missions/{mission.id}/legs/{leg.id}/route",
        files={"file": ("new.kml", kml_bytes().replace(b"1,0,10000", b"2,0,10000"))},
    )
    assert response.status_code == 200, response.text
    saved = storage.load_mission_v2(mission.id).legs[0]
    assert saved.route_id != old
    assert saved.transports.initial_x_satellite_id == "X-invented"
    assert (
        service.route_manager.get_route(saved.route_id).content_hash
        != service.route_manager.get_route(old).content_hash
    )
    assert not response.json().get("warnings"), response.json()


def test_active_imported_route_requires_deactivation(ordinary):
    api, _service, mission = ordinary
    mission.legs[0].is_active = True
    storage.save_mission_v2(mission)
    r = api.put(
        f"/api/v2/missions/{mission.id}/legs/{mission.legs[0].id}/route",
        files={"file": ("new.kml", kml_bytes())},
    )
    assert r.status_code == 409


def test_foreign_anchor_cannot_be_reused_on_replacement():
    from app.mission.itinerary_import.rebind import rebind
    from app.mission.planning.match import _anchor

    from .test_ar import fixture

    _leg, old = fixture()
    anchor = _anchor(old, 1, 0, old.points[1].expected_arrival_time, "p1")
    new = old.model_copy(deep=True)
    new.content_hash = "b" * 64
    new.route_id = "new-route"
    new.points[1].longitude = 40
    with pytest.raises(ValueError, match="uniquely remapped"):
        rebind(anchor, old, new)


@pytest.mark.parametrize("enabled", [False, True])
def test_initial_satellite_edit_preserves_omitted_starshield(ordinary, enabled):
    """Older leg editors omit Starshield while replacing transport fields."""
    from app.satellites.catalog import Satellite, get_satellite_catalog

    api, _service, mission = ordinary
    get_satellite_catalog().add_satellite(Satellite("WGS8", "X", longitude=10))
    leg = mission.legs[0]
    leg.transports.starshield_enabled = enabled
    storage.save_mission_v2(mission)
    payload = leg.model_dump(mode="json")
    payload["transports"]["initial_x_satellite_id"] = "WGS8"
    del payload["transports"]["starshield_enabled"]
    response = api.put(f"/api/v2/missions/{mission.id}/legs/{leg.id}", json=payload)
    assert response.status_code == 200, response.text
    saved = storage.load_mission_v2(mission.id).legs[0]
    assert saved.transports.initial_x_satellite_id == "WGS8"
    assert saved.transports.starshield_enabled is enabled
    assert not response.json().get("warnings"), response.json()
    assert storage.load_mission_timeline(leg.id, parent_mission_id=mission.id)
