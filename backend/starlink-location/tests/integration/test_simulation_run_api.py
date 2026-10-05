"""HTTP preview, transaction, strict validation and restart contracts."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.simulation_run import router
from app.mission.dependencies import (
    get_overview_clock_settings_store,
    get_poi_manager,
    get_route_manager,
)
from app.mission.models import Mission
from app.mission.routes_v2 import router as mission_router
from app.mission.storage import load_mission_v2, save_mission_v2
from app.services.overview_clock_settings import OverviewClockSettingsStore
from app.simulation.run_runtime import SimulationRunRuntime
from app.simulation.run_service import SimulationRunService
from tests.unit.simulation_run_fixtures import Clocks, timed_plan_sources


@pytest.fixture
def api(tmp_path, isolate_mission_storage, coordinator):
    leg, routes, pois = timed_plan_sources(tmp_path)
    save_mission_v2(Mission(id="mission-1", name="Replay", legs=[leg]))
    clocks = Clocks()
    app = FastAPI()
    app.include_router(router)
    app.include_router(mission_router)
    service = SimulationRunService(
        SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation"),
        routes,
        pois,
    )
    coordinator.set_route_manager(routes)
    service.coordinator = coordinator
    service.publish = lambda telemetry, tick: None
    app.state.simulation_run_service = service
    app.dependency_overrides[get_route_manager] = lambda: routes
    app.dependency_overrides[get_poi_manager] = lambda: pois
    app.dependency_overrides[get_overview_clock_settings_store] = (
        lambda: OverviewClockSettingsStore(tmp_path / "clocks.json")
    )
    return TestClient(app), service, clocks


LEG = "/api/v2/missions/mission-1/legs/leg-1"
PACING = {"mode": "target_runtime", "runtime_seconds": 120}


def preview(client):
    return client.post(LEG + "/simulation/preview", json=PACING)


def start(client):
    p = preview(client)
    assert p.status_code == 200, p.text
    return client.post(
        LEG + "/activate",
        json={"simulation": {"pacing": PACING, "plan_token": p.json()["plan_token"]}},
    )


def test_preview_and_repeated_get_have_no_writes(api, tmp_path):
    client, service, _clocks = api
    before = service.poi_manager.pois_file.read_bytes()
    a, b = preview(client), preview(client)
    assert a.status_code == 200 and a.json() == b.json()
    assert a.json()["effective_multiplier"] == 10
    assert a.headers["cache-control"] == "no-store"
    assert not load_mission_v2("mission-1").legs[0].is_active
    assert service.poi_manager.pois_file.read_bytes() == before
    for _ in range(10):
        assert client.get("/api/simulation/run").json()["state"] == "idle"
    assert service.runtime.status().revision == 0


def test_live_activation_rejects_without_simulation_coordinator(api):
    client, service, _clocks = api
    service.runtime.set_service_mode("live")
    service.coordinator = None
    response = client.post(
        "/api/v2/missions/mission-1/legs/leg-1/activate",
        json={
            "simulation": {
                "pacing": {"mode": "multiplier", "multiplier": 10},
                "plan_token": "a" * 64,
            }
        },
    )
    assert response.status_code == 409
    assert service.runtime.status().run is None
    assert not load_mission_v2("mission-1").legs[0].is_active


def test_start_and_effective_geometry(api):
    client, service, clocks = api
    response = start(client)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == "success" and data["active_leg_id"] == "leg-1"
    assert data["simulation_run"]["state"] == "running"
    assert load_mission_v2("mission-1").legs[0].is_active
    assert service.coordinator.get_current_telemetry().position.longitude == 0
    run_id = data["simulation_run"]["run"]["run_id"]
    geometry = client.get("/api/simulation/run/" + run_id + "/route")
    assert geometry.status_code == 200
    assert len(geometry.json()["route"]["points"]) == 3
    assert (
        geometry.json()["route"]["points"][0]["expected_arrival_time"]
        == "2025-01-01T01:00:00Z"
    )
    clocks.advance(120)
    service.collect(service.coordinator, service.publish)
    assert client.get("/api/simulation/run").json()["state"] == "completed"
    assert load_mission_v2("mission-1").legs[0].is_active


def test_live_mode_rejects_pacing_before_mutation(api):
    client, service, _clocks = api
    p = preview(client).json()
    service.runtime.set_service_mode("live")
    assert preview(client).status_code == 409
    assert (
        client.post(
            LEG + "/activate",
            json={"simulation": {"pacing": PACING, "plan_token": p["plan_token"]}},
        ).status_code
        == 409
    )
    assert not load_mission_v2("mission-1").legs[0].is_active
    assert service.route_manager.get_active_route_id() is None


def test_changed_plan_token_rejects_before_activation(api):
    client, service, _clocks = api
    p = preview(client).json()
    service.route_manager.get_route("replay").points[1].longitude = 0.9
    response = client.post(
        LEG + "/activate",
        json={"simulation": {"pacing": PACING, "plan_token": p["plan_token"]}},
    )
    assert response.status_code == 409
    assert service.status().state == "idle"
    assert not load_mission_v2("mission-1").legs[0].is_active


def test_failed_start_preserves_running_leg(api):
    client, service, _clocks = api
    assert start(client).status_code == 200
    before = service.status().run
    poi_bytes = service.poi_manager.pois_file.read_bytes()

    def fail(*args):
        raise RuntimeError("initial publication failed")

    service.publish = fail
    assert start(client).status_code == 500
    assert service.status().run == before
    assert service.poi_manager.pois_file.read_bytes() == poi_bytes
    assert load_mission_v2("mission-1").legs[0].is_active


def test_bodyless_activation_retains_legacy_contract(api):
    client, service, _clocks = api
    assert start(client).status_code == 200
    response = client.post(LEG + "/activate")
    assert response.status_code == 200
    assert response.json() == {"status": "success", "active_leg_id": "leg-1"}
    assert service.status().state == "idle"
    assert client.post(LEG + "/activate", json={}).status_code == 200


def test_unavailable_runtime_and_missing_leg_errors(api):
    client, _service, _clocks = api
    assert (
        client.post(
            LEG.replace("leg-1", "missing") + "/simulation/preview", json=PACING
        ).status_code
        == 404
    )
    del client.app.state.simulation_run_service
    assert client.get("/api/simulation/run").status_code == 503


@pytest.mark.parametrize(
    "pacing",
    [
        {"mode": "multiplier", "multiplier": True},
        {"mode": "target_runtime", "runtime_seconds": "120"},
        {**PACING, "multiplier": 10},
    ],
)
def test_strict_input_errors(api, pacing):
    client, service, _clocks = api
    assert client.post(LEG + "/simulation/preview", json=pacing).status_code == 422
    assert service.status().state == "idle"


def test_restart_has_new_incarnation(api):
    client, service, clocks = api
    old = start(client).json()["simulation_run"]
    from app.mission.storage import reconcile_active_legs_on_startup

    reconcile_active_legs_on_startup()
    client.app.state.simulation_run_service = SimulationRunService(
        SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation"),
        service.route_manager,
        service.poi_manager,
    )
    new = client.get("/api/simulation/run").json()
    assert new["runtime_id"] != old["runtime_id"]
    assert new["state"] == "idle" and new["run"] is None
    assert not load_mission_v2("mission-1").legs[0].is_active


def test_deactivation_and_edit_conflict(api):
    client, service, _clocks = api
    assert start(client).status_code == 200
    leg = load_mission_v2("mission-1").legs[0]
    assert client.put(LEG, json=leg.model_dump(mode="json")).status_code == 409
    assert client.post("/api/v2/missions/mission-1/legs/deactivate").status_code == 200
    assert service.status().state == "cancelled"
    assert client.put(LEG, json=leg.model_dump(mode="json")).status_code == 200
