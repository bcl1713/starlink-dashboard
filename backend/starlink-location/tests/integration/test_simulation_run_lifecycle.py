"""Failure points, route/config changes, and owning deletion contracts."""

import pytest

from app.mission.storage import get_leg_timeline_path, load_mission_v2, save_mission_v2
from app.services.flight_state import get_flight_state_manager
from tests.integration.test_simulation_run_api import LEG, api, start

__all__ = ["api"]


@pytest.mark.parametrize(
    "failure", ["persistence", "route", "pois", "timeline", "first_frame"]
)
def test_start_failure_restores_affected_pois_route_flight_and_flags(
    api, monkeypatch, failure
):
    client, service, _clocks = api
    assert start(client).status_code == 200
    prior_run = service.status().run
    prior_pois = service.poi_manager.pois_file.read_bytes()
    prior_flight = get_flight_state_manager().checkpoint()
    prior_telemetry = service.coordinator.get_current_telemetry().model_dump()
    original_mission = load_mission_v2("mission-1")
    target = original_mission.legs[0].model_copy(
        deep=True, update={"id": "second-leg", "route_id": "second", "is_active": False}
    )
    original_mission.legs.append(target)
    service.route_manager._routes["second"] = service.route_manager.get_route(
        "replay"
    ).model_copy(deep=True)
    save_mission_v2(original_mission)
    import app.mission.leg_activation as activation

    objects = {
        "persistence": (activation, "save_mission_v2"),
        "route": (service.route_manager, "activate_route"),
        "pois": (activation, "publish_mission_pois"),
        "timeline": (activation, "save_mission_timeline"),
        "first_frame": (service, "publish"),
    }
    owner, name = objects[failure]
    original = getattr(owner, name)
    attempts = 0

    def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("Injected " + failure + " failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, fail_once)
    path = LEG.replace("leg-1", "second-leg")
    preview = client.post(
        path + "/simulation/preview", json={"mode": "multiplier", "multiplier": 10}
    )
    response = client.post(
        path + "/activate",
        json={
            "simulation": {
                "pacing": {"mode": "multiplier", "multiplier": 10},
                "plan_token": preview.json()["plan_token"],
            }
        },
    )
    assert response.status_code == 500, response.text
    assert service.status().run == prior_run
    assert service.route_manager.get_active_route_id() == "replay"
    assert service.poi_manager.pois_file.read_bytes() == prior_pois
    assert get_flight_state_manager().checkpoint() == prior_flight
    assert service.coordinator.get_current_telemetry().model_dump() == prior_telemetry
    assert [leg.id for leg in load_mission_v2("mission-1").legs if leg.is_active] == [
        "leg-1"
    ]
    assert not get_leg_timeline_path("second-leg", "mission-1").exists()


@pytest.mark.parametrize("path", [LEG, "/api/v2/missions/mission-1"])
def test_owning_deletion_cancels_run(api, path):
    client, service, _clocks = api
    assert start(client).status_code == 200
    rejected = client.delete(path)
    assert rejected.status_code == 409
    assert service.status().state == "running"
    assert client.post("/api/v2/missions/mission-1/legs/deactivate").status_code == 200
    response = client.delete(path)
    assert response.status_code == 204, response.text
    assert service.status().state == "cancelled"
    assert service.runtime.selected_plan() is None


def test_route_replacement_rejected_before_writes(api):
    client, service, _clocks = api
    assert start(client).status_code == 200
    before = service.route_manager.get_route("replay").model_dump()
    response = client.put(
        LEG + "/route",
        files={"file": ("new.kml", b"<kml/>", "application/vnd.google-earth.kml+xml")},
    )
    assert response.status_code == 409, response.text
    assert service.route_manager.get_route("replay").model_dump() == before
    assert service.status().state == "running"


@pytest.mark.parametrize("operation", ["activate", "deactivate", "delete"])
def test_direct_route_changes_cancel_pacing(api, operation):
    from app.api.routes.delete import router as deletion
    from app.api.routes.management import router as management

    client, service, _clocks = api
    client.app.include_router(management, prefix="/api/routes")
    client.app.include_router(deletion, prefix="/api/routes")
    assert start(client).status_code == 200
    if operation == "delete":
        response = client.delete("/api/routes/replay")
    elif operation == "activate":
        response = client.post("/api/routes/replay/activate")
    else:
        response = client.post("/api/routes/deactivate")
    assert response.status_code in (200, 204), response.text
    assert service.status().state == "cancelled"
    assert service.runtime.frame() is None


@pytest.mark.parametrize("method", ["post", "put"])
def test_configuration_replacement_cancels_and_updates_confirmed_mode(
    api, monkeypatch, method
):
    from app.api import config

    client, service, _clocks = api
    client.app.include_router(config.router)
    monkeypatch.setattr(config, "_coordinator", service.coordinator)
    assert start(client).status_code == 200
    payload = service.coordinator.get_config().model_dump(mode="json")
    payload["mode"] = "live"
    response = getattr(client, method)("/api/config", json=payload)
    assert response.status_code == 200, response.text
    assert service.status().service_mode == "live"
    assert service.status().state == "cancelled"
    assert (
        client.post(
            LEG + "/simulation/preview", json={"mode": "multiplier", "multiplier": 10}
        ).status_code
        == 409
    )


def test_failed_ordinary_activation_preserves_prior_run(api, monkeypatch):
    import app.mission.routes_v2 as routes

    client, service, _clocks = api
    assert start(client).status_code == 200
    before = service.status().run

    def fail(*args, **kwargs):
        raise RuntimeError("legacy timeline unavailable")

    monkeypatch.setattr(routes, "build_mission_timeline", fail)
    assert client.post(LEG + "/activate").status_code == 500
    assert service.status().run == before


def test_shutdown_leaves_no_replay_work(api):
    client, service, clocks = api
    assert start(client).status_code == 200
    service.close()
    clocks.advance(1000)
    assert service.runtime.prepare_tick() is None
    assert service.runtime.selected_plan() is None
    assert service.status().state == "cancelled"
