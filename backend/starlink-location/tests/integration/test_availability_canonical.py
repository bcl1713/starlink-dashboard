"""Canonical live profiles remain separate from selected replay projections."""

import json
from datetime import datetime, timedelta

from app.api import config as config_api
from app.mission import storage
from app.mission.availability_context import snapshot_for_leg
from app.mission.availability_pois import project_current_pois
from app.mission.exporter.snapshot import capture_export_snapshot
from app.mission.exporter.snapshot_views import SnapshotViews
from app.mission.planning.service import PlanningService
from app.mission.planning.store import PlanningStore
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.poi import POICreate
from app.models.simulation_run import MultiplierPacing
from app.simulation.coordinator import SimulationCoordinator
from app.simulation.run_runtime import SimulationRunRuntime
from app.simulation.run_service import SimulationRunService
from tests.integration import test_transport_availability_routes as availability_routes

NOW = availability_routes.NOW
availability_api = availability_routes.availability_api


def test_real_run_actions_keep_canonical_files_and_live_fallback_separate(
    availability_api, monkeypatch, default_config, tmp_path
):
    client, app, store, mission = availability_api
    monkeypatch.chdir(tmp_path)
    coverage = tmp_path / "data/sat_coverage"
    coverage.mkdir(parents=True)
    (coverage / "commka.geojson").write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"satellite_id": "AOR"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [[-5, -5], [5, -5], [5, 5], [-5, 5], [-5, -5]]
                            ],
                        },
                    }
                ],
            }
        )
    )
    point = store.poi_manager.create_poi(
        POICreate(
            name="Future Ka transition",
            kind="ka_transition",
            latitude=0.8,
            longitude=0,
            mission_id=mission.id,
            route_id="route-one",
            expected_arrival_time=NOW + timedelta(minutes=45),
        ),
        generated_source="mission-timeline",
    )
    coordinator = SimulationCoordinator(default_config)
    app.state.coordinator = coordinator
    del app.state.availability_source_mode
    monkeypatch.setattr(config_api, "_coordinator", coordinator)
    app.include_router(config_api.router)
    elapsed = [0.0]

    def new_service():
        runtime = SimulationRunRuntime(lambda: elapsed[0], lambda: NOW, "simulation")
        service = SimulationRunService(runtime, store.route_manager, store.poi_manager)
        service.coordinator = coordinator
        app.state.simulation_run_service = service
        return service

    def start(service):
        parent = storage.load_mission_v2(mission.id)
        plan = service.prepare_plan(
            mission.id,
            parent.legs[0],
            MultiplierPacing(mode="multiplier", multiplier=1),
        )
        service.runtime.commit_tick(service.runtime.prepare_start(plan))
        return service.status().run.run_id

    def act(action, key):
        current = client.get(f"/api/v2/missions/{mission.id}/availability").json()
        response = client.post(
            f"/api/v2/missions/{mission.id}/availability/actions",
            json={
                "expected_revision": current["revision"],
                "command_id": key,
                "transport": "Ka",
                "action": action,
                "expected_simulation_run_id": current["simulation_run_id"],
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def canonical(enabled):
        response = client.get(f"/api/v2/missions/{mission.id}/legs/leg-1/timeline")
        assert response.status_code == 200
        timeline = response.json()
        snapshot = timeline["statistics"]["_transport_availability"]
        assert snapshot["simulation_run_id"] is None
        assert (
            all(window["transport"] != "Ka" for window in snapshot["failures"])
            if enabled
            else snapshot["failures"]
        )
        assert all(
            (segment["ka_state"] != "offline") == enabled
            for segment in timeline["segments"]
            if datetime.fromisoformat(segment["end_time"]) > NOW + timedelta(minutes=10)
        )
        assert store.poi_manager.get_poi(point.id).transport_active is enabled
        return timeline

    def selected(service, enabled):
        parent = storage.load_mission_v2(mission.id)
        run = service.status().run
        snapshot = snapshot_for_leg(parent, parent.legs[0], run_id=run.run_id)
        assert snapshot.resolve(run.simulation_time)["Ka"] is enabled
        current = project_current_pois(
            store.poi_manager.list_pois(mission_id=mission.id),
            store.route_manager,
            run_service=service,
        )
        assert next(p for p in current if p.id == point.id).transport_active is enabled
        artifacts = prepare_mission_timeline(
            parent.legs[0],
            store.route_manager,
            store.poi_manager,
            parent_mission_id=parent.id,
            availability=snapshot,
        )
        assert (
            artifacts.timeline.statistics["_transport_availability"][
                "simulation_run_id"
            ]
            == run.run_id
        )
        assert all(
            (segment.ka_state != "offline") == enabled
            for segment in artifacts.timeline.segments
        )

    service = new_service()
    first_run = start(service)
    assert act("unavailable", "sim-failure")["effective"]["Ka"] is False
    canonical(True)
    selected(service, False)
    assert act("restore", "sim-restore")["effective"]["Ka"] is True
    canonical(True)
    selected(service, True)
    act("unavailable", "sim-failure-again")
    # Reopen storage readers and replace the real runtime, as at restart.
    app.state.planning_service = PlanningService(
        PlanningStore(storage.MISSIONS_DIR, store.route_manager, store.poi_manager)
    )
    service = new_service()
    assert start(service) != first_run
    assert (
        client.get(f"/api/v2/missions/{mission.id}/availability").json()["effective"][
            "Ka"
        ]
        is True
    )
    canonical(True)
    selected(service, True)
    live = client.post(
        "/api/config",
        json=default_config.model_copy(update={"mode": "live"}).model_dump(mode="json"),
    )
    assert live.status_code == 200
    canonical(True)
    assert act("unavailable", "live-failure")["effective"]["Ka"] is False
    canonical(False)
    # A fresh selected run ignores live failure while canonical saved files retain it.
    switched = client.post("/api/config", json=default_config.model_dump(mode="json"))
    assert switched.status_code == 200
    service = new_service()
    start(service)
    selected(service, True)
    canonical(False)
    monkeypatch.setattr(
        "app.mission.exporter.snapshot.prepare_mission_timeline",
        lambda *a, **k: (_ for _ in ()).throw(
            ValueError("synthetic source unavailable")
        ),
    )
    exported = capture_export_snapshot(
        mission.id, store.route_manager, store.poi_manager
    )
    saved = SnapshotViews(exported).timeline("leg-1")
    assert saved.statistics["_transport_availability"]["simulation_run_id"] is None
    assert all(
        segment.ka_state == "offline"
        for segment in saved.segments
        if segment.start_time >= NOW + timedelta(minutes=10)
    )
    assert len(storage.load_mission_v2(mission.id).availability.history) == 4
