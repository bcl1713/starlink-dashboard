"""Real paced replay status retains selected capability after equipment actions."""

import json

import pytest

from app.mission import storage
from app.mission.planning.service import PlanningService
from app.mission.planning.store import PlanningStore
from tests.integration import test_simulation_pop_status as source
from tests.planning import test_proposals as managed

api = source.api
pop_api = source.pop_api
service = managed.service


@pytest.fixture
def prepared(service, tmp_path, monkeypatch):
    # This imported planning fixture runs outside planning/conftest.py's scope.
    from app.mission.planning.deadlines import shutdown_workers, start_workers

    start_workers()
    try:
        yield managed.prepared.__wrapped__(service, tmp_path, monkeypatch)
    finally:
        shutdown_workers()


@pytest.fixture
def availability_status(pop_api, monkeypatch, tmp_path, request):
    client, service, clocks, pops, sites = pop_api
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
    monkeypatch.setattr("app.mission.timeline_service._COVERAGE_SAMPLER", None)
    app = client.app
    app.state.route_manager = service.route_manager
    app.state.poi_manager = service.poi_manager
    app.state.coordinator = service.coordinator
    app.state.planning_service = PlanningService(
        PlanningStore(storage.MISSIONS_DIR, service.route_manager, service.poi_manager)
    )
    if getattr(request, "param", None) == "custom-x":
        from app.models.poi import POICreate

        service.poi_manager.create_poi(
            POICreate(
                name="Custom-status-X", latitude=0, longitude=180, category="satellite"
            )
        )
        mission = storage.load_mission_v2("mission-1")
        mission.legs[0].transports.initial_x_satellite_id = "Custom-status-X"
        storage.save_mission_v2(mission)
    if getattr(request, "param", None) == "missing-profile":
        service.route_manager.get_route("replay").timing_profile = None
    source.start_paced(client, 1)
    return client, service, clocks, pops, sites


def command(client, transport, action, key):
    path = "/api/v2/missions/mission-1/availability"
    current = client.get(path).json()
    result = client.post(
        path + "/actions",
        json={
            "expected_revision": current["revision"],
            "command_id": key,
            "transport": transport,
            "action": action,
            "expected_simulation_run_id": current["simulation_run_id"],
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize("transport", ["X", "Ka", "Ku"])
@pytest.mark.parametrize(
    "availability_status",
    [None, "missing-profile"],
    indirect=True,
    ids=["profile", "timed-points-only"],
)
def test_paced_status_keeps_selected_continuity_after_failure_and_restore(
    availability_status, transport
):
    client, service, clocks, pops, _ = availability_status
    accepted = service.runtime.selected_plan()
    accepted_revision = accepted.artifacts.call_capabilities.input_revision
    accepted_route = accepted.artifacts.route.model_dump()
    raw_route = service.route_manager.get_route("replay").model_dump()
    assert accepted.artifacts.route.timing_profile is not None
    baseline = client.get("/api/status").json()
    assert baseline["pop_forecast"]["status"] == "ready"
    assert baseline["call_continuity"] is not None
    field = {"X": "x", "Ka": "ka", "Ku": "starshield"}[transport]
    baseline_capability = [
        (span.start_utc, span.end_utc, getattr(span, field))
        for span in pops._replay_capability_cache[1].spans
    ]
    assert (
        command(client, transport, "unavailable", "fail-" + transport)["effective"][
            transport
        ]
        is False
    )
    failed = client.get("/api/status").json()
    assert failed["transport_availability"][transport] is False
    assert failed["call_continuity"] is not None
    assert all(
        getattr(span, field) == "unavailable"
        for span in pops._replay_capability_cache[1].spans
        if span.end_utc > service.status().run.simulation_time
    )
    intervals = failed["call_continuity"]["intervals"]
    assert intervals and all(
        transport not in i["usable_alternatives"] for i in intervals
    )
    canonical = client.get("/api/v2/missions/mission-1/legs/leg-1/timeline").json()
    assert (
        canonical["statistics"]["_transport_availability"]["simulation_run_id"] is None
    )
    assert canonical["statistics"]["_transport_availability"]["failures"] == []
    command(client, transport, "restore", "restore-" + transport)
    restored = client.get("/api/status").json()
    assert restored["transport_availability"][transport] is True
    assert restored["call_continuity"] is not None
    assert [
        (span.start_utc, span.end_utc, getattr(span, field))
        for span in pops._replay_capability_cache[1].spans
    ] == baseline_capability
    if raw_route["timing_profile"] is None:
        cached_key = pops._replay_capability_cache[0]
        clocks.advance(10)
        service.collect(service.coordinator, service.publish)
        continued = client.get("/api/status").json()
        assert continued["call_continuity"] is not None
        assert pops._replay_capability_cache[0] == cached_key
        assert continued["call_continuity"]["intervals"][0][
            "start_utc"
        ] == service.status().run.simulation_time.isoformat().replace("+00:00", "Z")
    assert service.runtime.selected_plan() is accepted
    assert accepted.artifacts.call_capabilities.input_revision == accepted_revision
    assert accepted.artifacts.route.model_dump() == accepted_route
    assert service.route_manager.get_route("replay").model_dump() == raw_route


def test_selected_status_cache_reuses_and_invalidates_real_inputs(
    availability_status, monkeypatch
):
    from app.mission import timeline_preparation, timeline_service
    from app.satellites.coverage import CoverageSampler

    client, service, clocks, pops, sites = availability_status
    calls = []
    prepare = timeline_preparation.prepare_mission_timeline

    def counted(*args, **kwargs):
        calls.append(True)
        return prepare(*args, **kwargs)

    monkeypatch.setattr(timeline_preparation, "prepare_mission_timeline", counted)
    first = client.get("/api/status").json()
    assert first["call_continuity"] is not None
    # Real adjusted departure and phase publication leave the accepted projector valid.
    plan = service.runtime.selected_plan()
    assert (
        plan.artifacts.projector.start_time
        == storage.load_mission_v2("mission-1").legs[0].adjusted_departure_time
    )
    assert plan.artifacts.projector.start_time.hour == 1
    command(client, "Ka", "unavailable", "cache-fail")
    calls.clear()
    failed = client.get("/api/status").json()
    assert failed["call_continuity"] is not None
    assert len(calls) == 1
    assert (
        service.route_manager.get_route("replay").timing_profile.flight_status
        == "in_flight"
    )
    assert plan.artifacts.route.timing_profile.flight_status == "pre_departure"
    for _ in range(4):
        assert (
            client.get("/api/status").json()["call_continuity"]
            == failed["call_continuity"]
        )
    clocks.advance(10)
    service.collect(service.coordinator, service.publish)
    advanced = client.get("/api/status").json()
    assert advanced["call_continuity"] is not None
    assert advanced["call_continuity"]["intervals"][0][
        "start_utc"
    ] == service.status().run.simulation_time.isoformat().replace("+00:00", "Z")
    assert len(calls) == 1
    command(client, "Ka", "restore", "cache-restore")
    calls.clear()
    restored = client.get("/api/status").json()
    assert restored["call_continuity"] is not None
    assert any(
        "Ka" in i["usable_alternatives"]
        for i in restored["call_continuity"]["intervals"]
    )
    assert len(calls) == 1
    client.get("/api/status")
    assert len(calls) == 1
    sites([("a", 0, -1), ("b", 0, 2)])
    assert client.get("/api/status").json()["call_continuity"] is not None
    assert len(calls) == 2
    # Current source content changes invalidate RF capability even with unchanged commands.
    from pathlib import Path

    coverage = Path("data/sat_coverage/commka.geojson")
    old_sampler = CoverageSampler(coverage)
    raw = json.loads(coverage.read_text())
    raw["features"][0]["geometry"]["coordinates"][0][1][0] = 6
    coverage.write_text(json.dumps(raw))
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", old_sampler)
    assert client.get("/api/status").json()["call_continuity"] is None
    assert pops._replay_capability_cache is None
    assert len(calls) == 2
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", None)
    assert client.get("/api/status").json()["call_continuity"] is not None
    assert len(calls) == 3
    client.get("/api/status")
    assert len(calls) == 3


@pytest.mark.parametrize("field", ["geometry", "timing"])
def test_selected_status_rejects_changed_accepted_route_inputs(
    availability_status, field
):
    from datetime import timedelta

    client, service, _, pops, _ = availability_status
    assert client.get("/api/status").json()["call_continuity"] is not None
    route = service.route_manager.get_route("replay")
    original = route.model_copy(deep=True)
    if field == "geometry":
        route.points[1].latitude += 0.1
    else:
        route.points[1].expected_arrival_time += timedelta(seconds=1)
    changed = client.get("/api/status").json()
    assert changed["call_continuity"] is None
    assert pops._replay_capability_cache is None
    service.route_manager._routes["replay"] = original
    assert client.get("/api/status").json()["call_continuity"] is not None


def test_selected_status_new_run_and_real_mode_switch_discard_old_projection(
    availability_status, monkeypatch
):
    from app.api import config as config_api

    client, service, _, pops, _ = availability_status
    command(client, "Ka", "unavailable", "old-run-fail")
    assert client.get("/api/status").json()["call_continuity"] is not None
    previous_run = service.status().run.run_id
    previous_cache = pops._replay_capability_cache
    source.start_paced(client, 2)
    assert service.status().run.run_id != previous_run
    status = client.get("/api/status").json()
    assert status["transport_availability"]["Ka"] is True
    assert status["call_continuity"] is not None
    assert pops._replay_capability_cache[0] != previous_cache[0]
    monkeypatch.setattr(config_api, "_coordinator", service.coordinator)
    client.app.include_router(config_api.router)
    config = service.coordinator.config.model_dump(mode="json")
    switched = client.post("/api/config", json={**config, "mode": "live"})
    assert switched.status_code == 200
    live = client.get("/api/status").json()
    assert live["transport_availability"]["Ka"] is True
    assert live["pop_observation"]["source"] == "live"
    assert pops._replay_capability_cache is None
    canonical = client.get("/api/v2/missions/mission-1/legs/leg-1/timeline").json()
    assert (
        canonical["statistics"]["_transport_availability"]["simulation_run_id"] is None
    )
    live_failure = command(client, "Ka", "unavailable", "live-run-failure")
    assert live_failure["simulation_run_id"] is None
    assert client.get("/api/status").json()["transport_availability"]["Ka"] is False
    assert (
        client.post("/api/config", json={**config, "mode": "simulation"}).status_code
        == 200
    )
    source.start_paced(client, 1)
    restarted = client.get("/api/status").json()
    assert restarted["call_continuity"] is not None
    assert restarted["transport_availability"]["Ka"] is True
    canonical = client.get("/api/v2/missions/mission-1/legs/leg-1/timeline").json()
    snapshot = canonical["statistics"]["_transport_availability"]
    assert snapshot["simulation_run_id"] is None
    assert len(snapshot["failures"]) == 1
    assert snapshot["failures"][0]["transport"] == "Ka"
    assert snapshot["failures"][0]["end"] is None


def test_selected_status_missing_sources_remain_unknown(
    availability_status, monkeypatch
):
    from pathlib import Path

    from app.mission import timeline_service

    client, service, _, pops, _ = availability_status
    assert client.get("/api/status").json()["call_continuity"] is not None
    Path("data/sat_coverage/commka.geojson").unlink()
    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", None)
    missing_ka = client.get("/api/status").json()
    assert missing_ka["call_continuity"] is not None
    assert all(
        "Ka" not in i["usable_alternatives"]
        for i in missing_ka["call_continuity"]["intervals"]
    )
    assert any(span.ka == "unknown" for span in pops._replay_capability_cache[1].spans)
    service.coordinator.config.pop.catalog_path.write_text('{"sites": []}')
    missing_pop = client.get("/api/status").json()
    assert missing_pop["pop_forecast"]["status"] == "unavailable"
    assert missing_pop["call_continuity"] is None


def test_all_failed_status_classifies_remaining_outage_and_ka_restore(
    availability_status,
):
    client, _, _, _, _ = availability_status
    for key in ["X", "Ka", "Ku"]:
        command(client, key, "unavailable", "all-" + key)
    down = client.get("/api/status").json()
    assert down["call_continuity"] is not None
    assert down["call_continuity"]["intervals"]
    assert all(
        i["classification"] == "existing_outage"
        for i in down["call_continuity"]["intervals"]
    )
    command(client, "Ka", "restore", "all-restore-Ka")
    restored = client.get("/api/status").json()
    assert restored["call_continuity"] is not None
    assert all(
        "Ka" in i["usable_alternatives"]
        for i in restored["call_continuity"]["intervals"]
    )
    assert restored["call_continuity"]["planned_communications_outage_seconds"] == 0


@pytest.mark.parametrize("availability_status", ["custom-x"], indirect=True)
def test_selected_refresh_preserves_custom_poi_x_geometry(
    availability_status, monkeypatch
):
    from app.mission.availability_context import snapshot_for_leg
    from app.mission.timeline_preparation import prepare_mission_timeline
    from app.services.pop.catalog import load_catalog

    client, service, _, pops, _ = availability_status
    plan = service.runtime.selected_plan()
    assert any(
        span.x == "unavailable" for span in plan.artifacts.call_capabilities.spans
    )
    command(client, "Ka", "unavailable", "custom-x-refresh")
    status = client.get("/api/status").json()
    assert status["call_continuity"] is not None
    mission = storage.load_mission_v2("mission-1")
    selected = snapshot_for_leg(
        mission, mission.legs[0], run_id=service.status().run.run_id
    )
    direct = prepare_mission_timeline(
        mission.legs[0],
        service.route_manager,
        service.poi_manager,
        parent_mission_id=mission.id,
        normalize_for_simulation=True,
        availability=selected,
        pop_catalog=load_catalog(service.coordinator.config.pop.catalog_path),
    )
    assert any(span.x == "unavailable" for span in direct.call_capabilities.spans)
    assert [
        (s.start_utc, s.end_utc, s.x) for s in pops._replay_capability_cache[1].spans
    ] == [(s.start_utc, s.end_utc, s.x) for s in direct.call_capabilities.spans]

    from app.mission import timeline_preparation
    from app.models.poi import POIUpdate

    calls = []
    prepare = timeline_preparation.prepare_mission_timeline

    def counted(*args, **kwargs):
        calls.append(True)
        return prepare(*args, **kwargs)

    monkeypatch.setattr(timeline_preparation, "prepare_mission_timeline", counted)
    for _ in range(2):
        assert client.get("/api/status").json()["call_continuity"] is not None
    assert calls == []
    old_key = pops._replay_capability_cache[0]
    point = service.poi_manager.find_global_poi_by_name("Custom-status-X")
    service.poi_manager.update_poi(point.id, POIUpdate(longitude=20))
    assert client.get("/api/status").json()["call_continuity"] is not None
    assert len(calls) == 1
    assert pops._replay_capability_cache[0] != old_key
    # POI-only geometry remains unknown when no independent catalog certifies Up.
    assert all(span.x == "unknown" for span in pops._replay_capability_cache[1].spans)
    changed = prepare_mission_timeline(
        mission.legs[0],
        service.route_manager,
        service.poi_manager,
        parent_mission_id=mission.id,
        normalize_for_simulation=True,
        availability=selected,
        pop_catalog=load_catalog(service.coordinator.config.pop.catalog_path),
    )
    assert [
        (s.start_utc, s.end_utc, s.x) for s in pops._replay_capability_cache[1].spans
    ] == [(s.start_utc, s.end_utc, s.x) for s in changed.call_capabilities.spans]
    client.get("/api/status")
    assert len(calls) == 1
    edited_key = pops._replay_capability_cache[0]
    assert service.poi_manager.delete_poi(point.id)
    assert client.get("/api/status").json()["call_continuity"] is not None
    assert len(calls) == 2
    assert pops._replay_capability_cache[0] != edited_key
    assert all(span.x == "unknown" for span in pops._replay_capability_cache[1].spans)
    client.get("/api/status")
    assert len(calls) == 2


def test_managed_projection_keeps_permitted_poi_sources_and_duplicate_validation(
    prepared,
):
    from app.mission.active_context import resolve_active_mission_leg_context
    from app.mission.availability_context import snapshot_for_leg
    from app.mission.pop_status import PopStatusService
    from app.models.poi import POICreate
    from app.models.simulation_run import MultiplierPacing
    from app.simulation.run_runtime import SimulationRunRuntime
    from app.simulation.run_service import SimulationRunService
    from tests.planning.test_reviewed_save import review
    from tests.unit.simulation_run_fixtures import Clocks

    planner, view = prepared
    points = planner.store.poi_manager
    points.create_poi(
        POICreate(name="SOUTH", latitude=0, longitude=0, category="satellite", icon="X")
    )
    points.create_poi(
        POICreate(
            name="WEST", latitude=0, longitude=-25, category="satellite", icon="X"
        )
    )
    view = planner.store.read(view.mission.id)
    published = planner.save_reviewed(view.mission.id, "card-1", review(planner, view))
    parent = published.mission
    leg = parent.legs[0]
    assert leg.transports.initial_x_satellite_id == "SOUTH"
    assert leg.transports.x_transitions == []
    assert {s.satellite_id for s in leg.transports.planning_inputs.satellites} == {
        "SOUTH",
        "WEST",
    }
    leg.is_active = True
    storage.save_mission_v2(parent)
    planner.store.route_manager.activate_route(leg.route_id)
    clocks = Clocks()
    runtime = SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation")
    run_service = SimulationRunService(runtime, planner.store.route_manager, points)
    try:
        plan = run_service.prepare_plan(
            parent.id, leg, MultiplierPacing(mode="multiplier", multiplier=1)
        )
        runtime.commit_tick(runtime.prepare_start(plan))
        run_id = runtime.status().run.run_id
        context = {
            "route": plan.artifacts.route,
            "projector": plan.artifacts.projector,
            "simulation_run_id": run_id,
            "mission_id": parent.id,
            "leg_id": leg.id,
        }
        active = resolve_active_mission_leg_context(planner.store.route_manager).context
        selected = snapshot_for_leg(active.parent_mission, active.leg, run_id=run_id)
        pops = PopStatusService(planner.store.route_manager, poi_manager=points)
        assert pops._replay_capabilities(active, context, None, selected) is not None
        duplicate = points.create_poi(
            POICreate(
                name="west", latitude=0, longitude=-25, category="satellite", icon="X"
            )
        )
        assert pops._replay_capabilities(active, context, None, selected) is None
        assert pops._replay_capability_cache is None
        assert points.delete_poi(duplicate.id)
        assert pops._replay_capabilities(active, context, None, selected) is not None
    finally:
        run_service.close()
