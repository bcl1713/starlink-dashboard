"""Saved itinerary plans retain canonical validation during paced replay."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.simulation_run import router as simulation_router
from app.mission.models import ManualAARTrack, ManualRouteSplice, MissionLeg
from app.mission.planning.grid import build_context
from app.mission.planning.inputs import build_inputs, draft_to_mission_leg
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.simulation_run import MultiplierPacing
from app.satellites.rules import ConstraintConfig
from app.services.kml.parser import parse_kml_file
from app.simulation.run_plan import SimulationValidationError, prepare_mission_run
from app.simulation.run_runtime import SimulationRunRuntime
from app.simulation.run_service import SimulationRunService
from tests.unit.simulation_run_fixtures import Clocks

from . import test_proposals
from .test_grid import swap
from .test_match import kml_fixture, utc
from .test_policy import START, scenario
from .test_reviewed_save import confirmed, review

prepared = test_proposals.prepared
service = test_proposals.service


def installed_sources(
    monkeypatch, tmp_path, basis="planning_kml", *, invalid_speed=False
):
    _, draft, _, _, manager, pois, expected = scenario(monkeypatch, seconds=7200)
    if basis in {"planning_kml", "adjusted_departure"}:
        route = parse_kml_file(kml_fixture(tmp_path), profile="planning_v1")
        manager = SimpleNamespace(get_route=lambda _: route)
        expected.route = expected.route.model_copy(
            update={"route_id": route.route_id, "content_hash": route.content_hash}
        )
    if basis == "adjusted_departure":
        draft.adjusted_departure_time = utc("09:15:00")
    if basis in {"manual_splice", "manual_splice_inferred", "sparse_manual_splice"}:
        if basis == "manual_splice":
            draft.swaps = [swap()]
        else:
            source = manager.get_route(expected.route.route_id)
            middle = source.points[0].model_copy(
                update={
                    "latitude": 10.005,
                    "sequence": 1,
                    "occurrence_id": "middle",
                    "expected_arrival_time": (
                        None
                        if basis == "sparse_manual_splice"
                        else START + timedelta(seconds=720)
                    ),
                }
            )
            source.points.insert(1, middle)
            source.points[-1].sequence = 2
            source.metadata.point_count = 3
            if basis == "sparse_manual_splice":
                # Valid declared metadata must survive the unavailable-timing
                # fallback as well as repeated, read-only simulation previews.
                for point in source.points[1:]:
                    point.expected_segment_speed_knots = 1
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
            enabled_track_id="track",
            speed_knots=450 if basis == "manual_splice" else None,
        )
    if invalid_speed:
        manager.get_route(expected.route.route_id).points[
            1
        ].expected_segment_speed_knots = 1
    inputs = build_inputs(expected, draft, manager, pois, ConstraintConfig())
    context = build_context(inputs, draft)
    installed = MissionLeg.model_validate_json(
        draft_to_mission_leg(
            inputs, draft, context, leg_id="installed"
        ).model_dump_json()
    )
    return installed, manager, pois


@pytest.mark.parametrize(
    "basis",
    [
        "planning_kml",
        "adjusted_departure",
        "manual_splice",
        "manual_splice_inferred",
        "sparse_manual_splice",
        "missing_speeds",
    ],
)
def test_saved_planning_leg_replays_without_changing_plan(monkeypatch, tmp_path, basis):
    leg, routes, pois = installed_sources(monkeypatch, tmp_path, basis)
    source = routes.get_route(leg.route_id)
    source_before, leg_before = source.model_dump(), leg.model_dump()
    ordinary = prepare_mission_timeline(leg, routes, pois, discover_coverage=False)
    pacing = MultiplierPacing(mode="multiplier", multiplier=10)
    plan = prepare_mission_run("mission", leg, pacing, routes, pois)
    repeated = prepare_mission_run("mission", leg, pacing, routes, pois)

    assert plan.preview.plan_token == repeated.preview.plan_token
    assert plan.artifacts.planning_evaluation == ordinary.planning_evaluation
    assert plan.artifacts.timeline.segments == ordinary.timeline.segments
    assert plan.artifacts.x_assignments == ordinary.x_assignments
    assert plan.preview.planned_departure == ordinary.projector.start_time
    assert plan.preview.planned_arrival == ordinary.projector.end_time
    assert [(p.latitude, p.longitude) for p in plan.artifacts.route.points] == [
        (p.latitude, p.longitude) for p in ordinary.route.points
    ]
    for replay_point, planned_point in zip(
        plan.artifacts.route.points, ordinary.route.points
    ):
        if planned_point.expected_arrival_time is not None:
            assert (
                replay_point.expected_arrival_time
                == planned_point.expected_arrival_time
            )
    assert all(
        p.expected_segment_speed_knots is not None
        for p in plan.artifacts.route.points[1:]
    )
    assert source.model_dump() == source_before
    assert leg.model_dump() == leg_before
    if basis == "adjusted_departure":
        assert plan.preview.planned_departure == utc("09:15:00")
        assert plan.preview.planned_arrival == utc("12:15:00")
        assert plan.preview.flight_duration_seconds == 10800
    if basis == "manual_splice":
        assert any(p.longitude == 0.001 for p in plan.artifacts.route.points)
        assert plan.artifacts.x_assignments[1][0] == START + timedelta(seconds=1830)
    if basis == "sparse_manual_splice":
        assert len(plan.artifacts.route.points) == 3
        assert plan.artifacts.route.points[
            1
        ].expected_arrival_time == START + timedelta(seconds=3600)


@pytest.mark.parametrize("changed", ["geometry", "timing", "speed"])
def test_simulation_rejects_actual_changes_to_saved_planning_route(
    monkeypatch, tmp_path, changed
):
    leg, routes, pois = installed_sources(monkeypatch, tmp_path)
    point = routes.get_route(leg.route_id).points[1]
    if changed == "geometry":
        point.longitude += 0.01
    elif changed == "timing":
        point.expected_arrival_time += timedelta(seconds=1)
    else:
        point.expected_segment_speed_knots = 1
    with pytest.raises(SimulationValidationError):
        prepare_mission_run(
            "mission",
            leg,
            MultiplierPacing(mode="multiplier", multiplier=10),
            routes,
            pois,
        )


def test_matching_planning_snapshot_still_requires_valid_simulation_speed(
    monkeypatch, tmp_path
):
    leg, routes, pois = installed_sources(monkeypatch, tmp_path, invalid_speed=True)
    assert prepare_mission_timeline(leg, routes, pois).planning_evaluation is not None
    with pytest.raises(SimulationValidationError, match="Segment speed contradicts"):
        prepare_mission_run(
            "mission",
            leg,
            MultiplierPacing(mode="multiplier", multiplier=10),
            routes,
            pois,
        )


def test_reviewed_itinerary_leg_previews_through_simulation_api(prepared):
    planning, view = confirmed(prepared)
    saved = planning.save_reviewed(view.mission.id, "card-1", review(planning, view))
    leg = saved.mission.legs[0]
    app = FastAPI()
    app.include_router(simulation_router)
    clocks = Clocks()
    service = SimulationRunService(
        SimulationRunRuntime(clocks.monotonic, clocks.utc_now, "simulation"),
        planning.store.route_manager,
        planning.store.poi_manager,
    )
    app.state.simulation_run_service = service
    with TestClient(app) as client:
        response = client.post(
            f"/api/v2/missions/{view.mission.id}/legs/{leg.id}/simulation/preview",
            json={"mode": "multiplier", "multiplier": 10},
        )
    assert response.status_code == 200, response.text
    assert response.json()["flight_duration_seconds"] == 10800
    assert response.json()["expected_runtime_seconds"] == 1080
    assert service.status().state == "idle"
    assert not planning.store.read(view.mission.id).mission.legs[0].is_active
