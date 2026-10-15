"""Pacing validation and read-only effective planning contracts."""

from datetime import timedelta

import pytest
from pydantic import TypeAdapter, ValidationError

from app.models.simulation_run import PacingInput
from app.simulation.run_plan import (
    SimulationValidationError,
    normalize_pacing,
    prepare_mission_run,
)
from tests.unit.simulation_run_fixtures import BASE, timed_plan_sources


def multiplier_input(value):
    return TypeAdapter(PacingInput).validate_python(
        {"mode": "multiplier", "multiplier": value}
    )


def target_input(value):
    return TypeAdapter(PacingInput).validate_python(
        {"mode": "target_runtime", "runtime_seconds": value}
    )


def test_120_seconds_matches_10x():
    a = normalize_pacing(multiplier_input(10), 1200)
    b = normalize_pacing(target_input(120), 1200)
    assert a.effective_multiplier == b.effective_multiplier == 10
    assert a.expected_runtime_seconds == b.expected_runtime_seconds == 120


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "multiplier", "multiplier": v}
        for v in [True, "10", float("nan"), float("inf"), 0, -1, 0.099, 1000.001]
    ]
    + [
        {"mode": "target_runtime", "runtime_seconds": 0.999},
        {"mode": "multiplier", "multiplier": 1, "runtime_seconds": 120},
        {"mode": "multiplier", "multiplier": 1, "unknown": 1},
        {"mode": "other", "multiplier": 1},
    ],
)
def test_strict_pacing_rejects_invalid_input(payload):
    with pytest.raises(ValidationError):
        TypeAdapter(PacingInput).validate_python(payload)


@pytest.mark.parametrize("value,expected", [(0.1, 12000), (1, 1200), (1000, 1.2)])
def test_inclusive_multiplier_boundaries(value, expected):
    assert (
        normalize_pacing(multiplier_input(value), 1200).expected_runtime_seconds
        == expected
    )


def test_target_limit_and_unsupported_derivation():
    assert normalize_pacing(target_input(1), 1000).effective_multiplier == 1000
    for duration in (1200, float("inf"), 0, -1, 1e-320):
        with pytest.raises(SimulationValidationError):
            normalize_pacing(target_input(1), duration)


def prepare(sources, pacing=None):
    leg, routes, pois = sources
    return prepare_mission_run(
        "mission-1", leg, pacing or multiplier_input(10), routes, pois
    )


def files(path):
    return {
        str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()
    }


def test_preview_is_read_only_and_stable(tmp_path):
    sources = timed_plan_sources(tmp_path)
    original = sources[1].get_route("replay").model_dump()
    before = files(tmp_path)
    a, b = prepare(sources), prepare(sources)
    assert a.preview.plan_token == b.preview.plan_token
    assert files(tmp_path) == before
    assert sources[1].get_active_route() is None
    assert sources[1].get_route("replay").model_dump() == original
    assert a.preview.planned_departure == BASE + timedelta(hours=1)
    assert a.preview.planned_arrival == BASE + timedelta(hours=1, seconds=1200)
    assert a.artifacts.route is not sources[1].get_route("replay")


@pytest.mark.parametrize(
    "fault",
    [
        "untimed",
        "zero_duration",
        "decreasing",
        "equal",
        "outside",
        "nan",
        "zero_distance",
        "speed",
    ],
)
def test_rejects_invalid_effective_timing(tmp_path, fault):
    sources = timed_plan_sources(tmp_path)
    route = sources[1].get_route("replay")
    if fault == "untimed":
        route.timing_profile = None
        for p in route.points:
            p.expected_arrival_time = None
    elif fault == "zero_duration":
        route.timing_profile.arrival_time = BASE
        for p in route.points:
            p.expected_arrival_time = BASE
    elif fault == "decreasing":
        route.points[1].expected_arrival_time = BASE - timedelta(seconds=1)
    elif fault == "equal":
        route.points[1].expected_arrival_time = BASE
    elif fault == "outside":
        route.points[1].expected_arrival_time = BASE + timedelta(seconds=1300)
    elif fault == "nan":
        route.points[1].latitude = float("nan")
    elif fault == "zero_distance":
        for p in route.points:
            p.longitude = 0
    elif fault == "speed":
        route.points[1].expected_segment_speed_knots = 1
    with pytest.raises(SimulationValidationError):
        prepare(sources)


def test_sparse_anchors_share_timeline_interpolation(tmp_path):
    sources = timed_plan_sources(tmp_path)
    route = sources[1].get_route("replay")
    route.points[1].expected_arrival_time = None
    plan = prepare(sources)
    start = BASE + timedelta(hours=1)
    assert plan.artifacts.route.points[1].expected_arrival_time == start + timedelta(
        seconds=600
    )
    assert plan.artifacts.projector.timestamp_for_distance(
        plan.artifacts.projector.total_distance / 2
    ) == start + timedelta(seconds=600)
    assert route.points[1].expected_arrival_time is None


def test_plan_token_changes_only_with_semantic_inputs(tmp_path):
    sources = timed_plan_sources(tmp_path)
    a = prepare(sources)
    sources[0].updated_at += timedelta(days=1)
    sources[1].get_route("replay").metadata.imported_at += timedelta(days=1)
    assert prepare(sources).preview.plan_token == a.preview.plan_token
    assert (
        prepare(sources, multiplier_input(2)).preview.plan_token != a.preview.plan_token
    )
    sources[1].get_route("replay").points[1].longitude = 0.9
    assert prepare(sources).preview.plan_token != a.preview.plan_token


def test_adjusted_effective_route(tmp_path):
    from app.mission.models import (
        ManualAARTrack,
        ManualAARTrackPoint,
        ManualRouteSplice,
    )

    sources = timed_plan_sources(tmp_path)
    leg, routes, _ = sources
    leg.transports.manual_aar_tracks = [
        ManualAARTrack(
            id="track",
            name="Diversion",
            points=[
                ManualAARTrackPoint(latitude=0.1, longitude=0.3),
                ManualAARTrackPoint(latitude=0.1, longitude=1.7),
            ],
        )
    ]
    leg.transports.manual_route_splice = ManualRouteSplice(
        enabled_track_id="track", speed_knots=400
    )
    plan = prepare(sources)
    assert plan.artifacts.projector.start_time == BASE + timedelta(hours=1)
    assert any(point.latitude == 0.1 for point in plan.artifacts.route.points)
    assert all(point.latitude == 0 for point in routes.get_route("replay").points)
    assert plan.artifacts.timeline.segments[-1].end_time == plan.preview.planned_arrival
