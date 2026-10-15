import copy
import importlib
from datetime import timedelta
from pathlib import Path

import pytest

from app.mission.exporter.customer_projection import project_briefing_leg
from tests.unit.customer_briefing_fixtures import fixture, snapshot


def test_supported_untimed_vertex_fixture_retains_bounds_and_reasoned_map_fallback(
    tmp_path,
):
    from app.mission.exporter.map_inputs import build_map_input
    from app.mission.timeline_builder.calculator import derive_mission_window
    from app.services.kml_parser import parse_kml_file

    source = (
        Path(__file__).resolve().parents[4]
        / "tools/acceptance/customer-briefing/production_seed.py"
    )
    spec = importlib.util.spec_from_file_location("production_seed", source)
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    path = tmp_path / "untimed-vertex.kml"
    path.write_bytes(seed.kml(seed.BASE, timedelta(hours=4), untimed_middle=True))
    route = parse_kml_file(path)
    assert derive_mission_window(route) == (seed.BASE, seed.BASE + timedelta(hours=4))
    assert route.points[1].expected_arrival_time is None
    data = fixture("composition-assessed")
    data["route"] = route.model_dump(mode="json")
    captured = snapshot(data)
    scene, reasons = build_map_input(captured, project_briefing_leg(captured))
    assert scene is None
    assert reasons and "timing" in reasons[0].lower()
    from app.mission.exporter.map_inputs import prepare_map_input

    assert (
        prepare_map_input(captured, project_briefing_leg(captured)).diagnostics[0].code
        == "route_timing_missing"
    )


def test_map_input_preserves_exact_outage_markers_and_dateline():
    name = "app.mission.exporter.map_inputs"
    assert importlib.util.find_spec(name), "pure map contract absent"
    build = importlib.import_module(name).build_map_input
    captured = snapshot(fixture("composition-assessed"))
    before = captured.effective_route_json
    projection = project_briefing_leg(captured)
    raw, warnings = build(captured, projection)
    assert not warnings
    red = next(
        i for i in projection.intervals if i.posture == "Communications unavailable"
    )
    marker = next(m for m in raw["markers"] if m["id"] == red.id)
    point = raw["route"][marker["routeIndex"]]
    assert point["timestamp"] == "2026-10-25T16:25:00Z"
    assert 48 < point["latitude"] < 57
    assert captured.effective_route_json == before
    data = fixture("composition-assessed")
    points = data["route"]["points"]
    for n, point in enumerate(points):
        point["latitude"] = 20
        point["longitude"] = [170, 179, -179, -170][n]
    cap = snapshot(data)
    raw, warnings = build(cap, project_briefing_leg(cap))
    assert not warnings
    mid = next(p for p in raw["route"] if p["timestamp"] == "2026-10-25T16:25:00Z")
    assert abs(mid["longitude"]) > 179


@pytest.mark.parametrize(
    "case", ["coincident", "conflicting", "backward", "stationary"]
)
def test_map_timing_normalization_preserves_positions_and_rejects_ambiguity(case):
    from app.mission.exporter.map_inputs import build_map_input

    data = fixture("composition-assessed")
    points = data["route"]["points"]
    if case == "stationary":
        points[1]["latitude"] = points[0]["latitude"]
        points[1]["longitude"] = points[0]["longitude"]
    else:
        duplicate = copy.deepcopy(points[0])
        if case == "conflicting":
            duplicate["longitude"] += 1
        elif case == "backward":
            duplicate["expected_arrival_time"] = "2026-10-25T13:59:59Z"
        points.insert(1, duplicate)
    captured = snapshot(data)
    original = captured.effective_route_json
    scene, reasons = build_map_input(captured, project_briefing_leg(captured))
    if case in {"conflicting", "backward"}:
        assert scene is None and reasons
    else:
        assert scene is not None
        assert len({p["timestamp"] for p in scene["route"]}) == len(scene["route"])
        first = scene["route"][0]
        if case == "stationary":
            assert any(
                p["timestamp"] != first["timestamp"]
                and p["latitude"] == first["latitude"]
                and p["longitude"] == first["longitude"]
                for p in scene["route"]
            )
        else:
            assert any("coincident" in reason for reason in reasons)
    assert captured.effective_route_json == original


@pytest.mark.parametrize(
    "code",
    [
        "route_missing",
        "route_timing_missing",
        "route_timing_non_increasing",
        "route_bounds_mismatch",
        "route_coordinates_invalid",
        "route_antipodal_segment",
        "route_point_limit",
        "route_marker_limit",
        "window_position_unavailable",
    ],
)
def test_map_failures_have_specific_codes(code):
    from dataclasses import replace

    from app.mission.exporter import map_inputs
    from tests.unit.test_map_real_input_boundaries import boundary

    assert hasattr(
        map_inputs, "prepare_map_input"
    ), "Specific map diagnostics are absent"
    captured, projected, _ = boundary(
        "map-density-one" if code == "route_marker_limit" else "map-density-two"
    )
    import json

    route = json.loads(captured.effective_route_json)
    points = route["points"]
    if code == "route_timing_missing":
        points[1]["expected_arrival_time"] = None
    elif code == "route_timing_non_increasing":
        points[1]["expected_arrival_time"] = points[0]["expected_arrival_time"]
    elif code == "route_bounds_mismatch":
        projected = replace(
            projected,
            utc_bounds=(
                projected.utc_bounds[0] + timedelta(seconds=1),
                projected.utc_bounds[1],
            ),
        )
    elif code == "route_coordinates_invalid":
        points[1]["latitude"] = 91
    elif code == "route_antipodal_segment":
        points[0]["latitude"], points[0]["longitude"] = 0, 0
        points[1]["latitude"], points[1]["longitude"] = 0, 180
    elif code == "route_point_limit":
        route["points"] = points * 201
    elif code == "window_position_unavailable":
        projected = replace(
            projected,
            coordination_rows=(
                replace(
                    projected.coordination_rows[0],
                    start_time=projected.utc_bounds[0] - timedelta(minutes=1),
                ),
            ),
        )
    captured = replace(
        captured,
        effective_route_json=(
            None if code == "route_missing" else json.dumps(route).encode()
        ),
    )
    before = captured.effective_route_json
    result = map_inputs.prepare_map_input(captured, projected)
    assert result.scene is None
    assert result.diagnostics[0].code == code
    assert result.diagnostics[0].severity == "error"
    assert result.diagnostics[0].message
    assert captured.effective_route_json == before
