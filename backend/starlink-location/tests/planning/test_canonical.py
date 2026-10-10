from app.mission.models import MissionLeg
from app.mission.timeline_preparation import prepare_mission_timeline

from .test_policy import scenario


def test_policy_canonical_reload_matches_intervals_and_cost(monkeypatch):
    inputs, draft, context, evaluate, manager, pois, _ = scenario(monkeypatch)
    from app.mission.planning.inputs import draft_to_mission_leg

    leg = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    leg = MissionLeg.model_validate_json(leg.model_dump_json())
    artifacts = prepare_mission_timeline(
        leg, manager, pois, discover_coverage=False, include_samples=True
    )
    expected = evaluate(inputs, draft, context)
    assert artifacts.planning_evaluation == expected
    assert (
        sum(
            (s.end_time - s.start_time).total_seconds()
            for s in artifacts.timeline.segments
            if s.x_state != "available"
        )
        == expected.outage_seconds
    )
    assert (
        artifacts.timeline.segments[0].metadata["planning_policy"]
        == "prefer_starshield_v1"
    )


def test_repeated_kml_bind_api_reload_canonical_equivalence(
    service, tmp_path, monkeypatch
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.mission.planning.models import ExpectedLeg, PlanningDraft
    from app.mission.planning.routes import router
    from app.satellites.rules import ConstraintConfig
    from app.services.route_manager import RouteManager

    from .test_match import kml_fixture, utc
    from .test_policy import planning_api
    from .test_store import create

    scenario(monkeypatch)  # finite configured real catalog
    view, _ = create(
        service,
        leg_updates={
            "departure_time": utc("09:00:00"),
            "arrival_time": utc("12:00:00"),
        },
    )
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    path = f"/api/v2/missions/planning/missions/{view.mission.id}/legs/card-1"
    with TestClient(app) as client:
        preview = client.post(
            path + "/route-previews",
            data={"expected_revision": 1},
            files={
                "file": (
                    "synthetic.kml",
                    kml_fixture(tmp_path).read_bytes(),
                    "application/vnd.google-earth.kml+xml",
                )
            },
        )
        assert preview.status_code == 200, preview.text
        response = client.post(
            path + "/route",
            json={
                "expected_revision": 1,
                "preview_id": preview.json()["preview_id"],
                "discrepancy_acknowledgments": [
                    e["code"] for e in preview.json()["discrepancy_errors"]
                ],
            },
        )
        assert response.status_code == 200, response.text
        leg = ExpectedLeg.model_validate(response.json()["expected_legs"][0]["leg"])
    manager = RouteManager(
        service.store.route_manager.routes_dir,
        profile_resolver=service.sources.resolve_profile,
    )
    manager.reload_all_routes()
    route = manager.get_route(leg.route.route_id)
    assert route.points[1].expected_arrival_time == utc("10:00:20")
    assert route.points[3].expected_arrival_time == utc("11:00:40")
    draft = PlanningDraft(
        permitted_satellite_ids=("SOUTH", "WEST"), initial_x_satellite_id="SOUTH"
    )
    build, grid, evaluate = planning_api()
    inputs = build(leg, draft, manager, service.store.poi_manager, ConstraintConfig())
    context = grid(inputs, draft)
    from app.mission.planning.inputs import draft_to_mission_leg

    # Save/reopen retains the seed grid and the operational switch.
    draft.evaluation_context = context
    with TestClient(app) as client:
        saved = client.put(
            path + "/draft",
            json={"expected_revision": 2, "draft": draft.model_dump(mode="json")},
        )
        assert saved.status_code == 200, saved.text
    reloaded = service.store.read(view.mission.id).expected_legs[0].leg.draft
    assert reloaded.evaluation_context == context
    installed = MissionLeg.model_validate_json(
        draft_to_mission_leg(
            inputs, reloaded, context, leg_id="installed"
        ).model_dump_json()
    )
    artifacts = prepare_mission_timeline(
        installed,
        manager,
        service.store.poi_manager,
        include_samples=True,
        discover_coverage=False,
    )
    assert artifacts.planning_evaluation == evaluate(inputs, draft, context)
    at = {i.start_time: i for i in artifacts.planning_evaluation.intervals}
    assert at[utc("10:00:20")].longitude == at[utc("11:00:40")].longitude == 1
    assert at[utc("10:00:20")].heading_degrees != at[utc("11:00:40")].heading_degrees
    from app.mission.models import XTransition
    from app.mission.planning.match import _candidates
    from app.services.active_x_handoff import _project_transitions

    transitions = [
        XTransition(
            id=str(n),
            latitude=0,
            longitude=1,
            target_satellite_id="WEST",
            anchor=_candidates(t, "second", route)[0],
        )
        for n, t in enumerate((utc("10:00:20"), utc("11:00:40")))
    ]
    # Rebuild through real export capture, which re-resolves catalog and routes.
    from app.mission import storage
    from app.mission.exporter.snapshot import capture_export_snapshot
    from app.mission.models import Mission
    from app.satellites import catalog

    monkeypatch.setattr(
        "app.mission.exporter.snapshot_inputs.get_satellite_catalog",
        catalog.get_satellite_catalog,
    )
    storage.save_mission_v2(Mission(id="export-proof", name="Proof", legs=[installed]))
    snapshot = capture_export_snapshot(
        "export-proof", manager, service.store.poi_manager
    )
    assert snapshot.legs[0].preparation_origin == "rebuilt", snapshot.legs[0].warnings
    import json

    exported = json.loads(snapshot.legs[0].timeline_json)
    assert [s["metadata"]["planning_interval"] for s in exported["segments"]] == [
        i.model_dump(mode="json") for i in artifacts.planning_evaluation.intervals
    ]
    projected = _project_transitions(route, transitions)
    assert projected[1][0] > projected[0][0]


from .test_store import service as service_fixture

service = service_fixture


def test_customer_projection_prefers_policy_evidence_over_raw_conflict(monkeypatch):
    import json

    from app.mission.exporter.customer_projection import project_briefing_leg
    from app.mission.exporter.snapshot import LegSnapshot
    from app.mission.planning.inputs import draft_to_mission_leg

    for enabled, expected in ((True, "Down"), (False, "Up")):
        inputs, draft, context, _evaluate, manager, pois, _ = scenario(
            monkeypatch, starshield_enabled=enabled
        )
        leg = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
        artifacts = prepare_mission_timeline(
            leg, manager, pois, discover_coverage=False
        )
        snapshot = LegSnapshot(
            leg_id=leg.id,
            leg_json=leg.model_dump_json().encode(),
            effective_route_json=artifacts.route.model_dump_json().encode(),
            timeline_json=artifacts.timeline.model_dump_json().encode(),
            source_records=(),
            resolved_restrictions=(),
            utc_bounds=(inputs.start_time, inputs.end_time),
            preparation_origin="rebuilt",
            warnings=(),
        )
        result = project_briefing_leg(snapshot)
        assert all(i.decisions[2].value == expected for i in result.intervals)
        assert all(
            i.decisions[1].value == ("Up" if enabled else "Down")
            for i in result.intervals
        )
        assert "owned_relative_path" not in json.dumps(leg.model_dump(mode="json"))


def test_planning_canonical_rejects_changed_transports_and_satellite(monkeypatch):
    import pytest

    from app.mission.planning.inputs import draft_to_mission_leg
    from app.mission.timeline_builder.calculator import TimelineComputationError
    from app.satellites import catalog

    inputs, draft, context, _, manager, pois, _ = scenario(monkeypatch)
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    leg.transports.starshield_enabled = False
    with pytest.raises(TimelineComputationError, match="transport inputs changed"):
        prepare_mission_timeline(leg, manager, pois, discover_coverage=False)
    leg.transports.starshield_enabled = True
    catalog.get_satellite_catalog().get_satellite("SOUTH").longitude = 50
    with pytest.raises(TimelineComputationError, match="positions changed"):
        prepare_mission_timeline(leg, manager, pois, discover_coverage=False)


def test_effective_splice_and_longitude_wrap_share_geometry(monkeypatch):
    from app.mission.models import ManualAARTrack, ManualRouteSplice
    from app.mission.planning.grid import build_context
    from app.mission.planning.inputs import build_inputs, draft_to_mission_leg
    from app.models.route import ParsedRoute
    from app.satellites.rules import ConstraintConfig

    inputs, draft, _, _, manager, pois, leg = scenario(
        monkeypatch, seconds=7200, starshield_enabled=False
    )
    route = manager.get_route("owned")
    route.points[0].longitude = 179
    route.points[1].longitude = -179
    draft.manual_aar_tracks = [
        ManualAARTrack(
            id="track",
            name="Deviation",
            points=[
                {"latitude": 10.1, "longitude": 179.5},
                {"latitude": 10.1, "longitude": -179.5},
            ],
        )
    ]
    draft.manual_route_splice = ManualRouteSplice(
        enabled_track_id="track", speed_knots=450
    )
    inputs = build_inputs(leg, draft, manager, pois, ConstraintConfig())
    context = build_context(inputs, draft)
    assert len(ParsedRoute.model_validate_json(inputs.route_json).points) > 2
    installed = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    artifacts = prepare_mission_timeline(
        installed, manager, pois, discover_coverage=False, include_samples=True
    )
    assert all(abs(i.longitude) > 178 for i in artifacts.planning_evaluation.intervals)
    assert (
        artifacts.route.points
        == ParsedRoute.model_validate_json(inputs.route_json).points
    )


def test_planning_preserves_captured_ka_coverage(monkeypatch):
    from app.mission import timeline_service
    from app.satellites.coverage import CoverageSampler

    monkeypatch.setattr(timeline_service, "_COVERAGE_SAMPLER", CoverageSampler())
    inputs, draft, context, evaluate, manager, pois, _ = scenario(monkeypatch)
    result = evaluate(inputs, draft, context)
    assert result.intervals[0].physical_ka_state == "degraded"
    from app.mission.planning.inputs import draft_to_mission_leg

    artifacts = prepare_mission_timeline(
        draft_to_mission_leg(inputs, draft, context, leg_id="installed"),
        manager,
        pois,
        discover_coverage=False,
    )
    assert artifacts.planning_evaluation == result


def test_selected_unavailable_splice_retains_legacy_no_overlay(monkeypatch):
    from app.mission.models import ManualAARTrack, ManualRouteSplice

    track = ManualAARTrack(
        id="remote",
        name="Remote",
        points=[{"latitude": 40, "longitude": 100}, {"latitude": 41, "longitude": 100}],
    )
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch,
        starshield_enabled=False,
        manual_aar_tracks=[track],
        manual_route_splice=ManualRouteSplice(enabled_track_id="remote"),
    )
    assert inputs.overlays == ()
    assert evaluate(inputs, draft, context).outage_seconds == 0


def test_splice_with_source_anchored_swap_uses_shared_occurrence_time(monkeypatch):
    from app.mission.models import ManualAARTrack, ManualRouteSplice
    from app.mission.planning.grid import build_context
    from app.mission.planning.inputs import build_inputs, draft_to_mission_leg
    from app.satellites.rules import ConstraintConfig

    from .test_grid import swap

    inputs, draft, _, _, manager, pois, leg = scenario(
        monkeypatch, seconds=7200, swaps=[swap()]
    )
    draft.manual_aar_tracks = [
        ManualAARTrack(
            id="track",
            name="Deviation",
            points=[
                {"latitude": 10.0025, "longitude": 0.001},
                {"latitude": 10.0075, "longitude": 0.001},
            ],
        )
    ]
    draft.manual_route_splice = ManualRouteSplice(
        enabled_track_id="track", speed_knots=450
    )
    inputs = build_inputs(leg, draft, manager, pois, ConstraintConfig())
    context = build_context(inputs, draft)
    installed = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    artifacts = prepare_mission_timeline(
        installed, manager, pois, discover_coverage=False
    )
    from datetime import timedelta

    from .test_policy import START

    assert artifacts.x_assignments[1][0] == START + timedelta(seconds=1830)


def test_cached_released_conflict_never_becomes_down_from_text(monkeypatch):
    from app.mission.exporter.customer_projection import project_briefing_leg
    from app.mission.exporter.snapshot import LegSnapshot
    from app.mission.planning.inputs import draft_to_mission_leg

    inputs, draft, context, _, manager, pois, _ = scenario(
        monkeypatch, starshield_enabled=False
    )
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="installed")
    artifacts = prepare_mission_timeline(leg, manager, pois, discover_coverage=False)
    snapshot = LegSnapshot(
        leg_id=leg.id,
        leg_json=leg.model_dump_json().encode(),
        effective_route_json=artifacts.route.model_dump_json().encode(),
        timeline_json=artifacts.timeline.model_dump_json().encode(),
        source_records=(),
        resolved_restrictions=(),
        utc_bounds=(inputs.start_time, inputs.end_time),
        preparation_origin="cached",
        warnings=(),
    )
    result = project_briefing_leg(snapshot)
    assert all(i.decisions[2].value != "Down" for i in result.intervals)
    assert all(i.decisions[1].value == "Down" for i in result.intervals)
