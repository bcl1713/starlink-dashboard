"""Sanitized count shapes pin the actual retained map marker-capacity boundary.

These fixtures contain no operational route/evaluation data. The private probe
must separately reproduce the predicate on original production inputs.
"""

import importlib.util
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest

from app.mission.exporter.customer_projection import (
    BriefingInterval,
    BriefingLeg,
    UsabilityDecision,
)
from app.mission.exporter.snapshot import LegSnapshot
from app.mission.exporter.snapshot_inputs import canonical_json

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/customer_briefing"


def boundary(name):
    recipe = json.loads((FIXTURES / f"{name}.json").read_bytes())
    start = datetime.fromisoformat(recipe["departure"]).astimezone(timezone.utc)
    duration = timedelta(minutes=recipe["windowCount"])
    end = start + duration
    points = [
        {
            "latitude": 20 + i / (recipe["pointCount"] - 1),
            "longitude": -30 + i / (recipe["pointCount"] - 1),
            "sequence": i,
            "occurrence_id": f"toy-occurrence-{i}",
            "expected_arrival_time": (
                start + duration * i / (recipe["pointCount"] - 1)
            ).isoformat(),
        }
        for i in range(recipe["pointCount"])
    ]
    route = canonical_json({"points": points, "ingestion_profile": "planning_v1"})
    captured = LegSnapshot(
        name,
        canonical_json({"id": name}),
        route,
        None,
        (),
        (),
        (start, end),
        "rebuilt",
        (),
    )
    decisions = (
        UsabilityDecision("Down", "synthetic-risk", ()),
        UsabilityDecision("Up", "synthetic-basis", ()),
        UsabilityDecision("Up", "synthetic-basis", ()),
    )
    windows = tuple(
        BriefingInterval(
            f"{name}-window-{i+1:03d}",
            i + 1,
            start + timedelta(minutes=i),
            start + timedelta(minutes=i + 1),
            decisions,
            "At Risk",
            (),
            (f"toy-source-{i}",),
            ("Synthetic risk",),
            (),
            ("Starshield", "X-Band MILSATCOM"),
        )
        for i in range(recipe["windowCount"])
    )
    projection = BriefingLeg(
        name, (start, end), windows, windows, (), (), "Synthetic basis", None
    )
    return captured, projection, recipe


def probe():
    spec = importlib.util.spec_from_file_location(
        "map_probe", ROOT / "tools/acceptance/itinerary-planning/map_probe.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_boundary(name):
    captured, projected, recipe = boundary(name)
    original = sha256(captured.effective_route_json).hexdigest()
    result = probe().probe_snapshot(captured, projected)
    assert result["failed_predicate"] == recipe["expectedPredicate"]
    assert result["point_count"] == recipe["pointCount"]
    assert result["marker_count"] == recipe["windowCount"]
    assert result["route_sha256"] == original
    assert sha256(captured.effective_route_json).hexdigest() == original
    assert len({row.id for row in projected.coordination_rows}) == recipe["windowCount"]
    assert all(
        a.end_time == b.start_time
        for a, b in zip(projected.intervals, projected.intervals[1:])
    )
    assert projected.intervals[0].start_time == projected.utc_bounds[0]
    assert projected.intervals[-1].end_time == projected.utc_bounds[1]


def test_real_leg_one_map_boundary():
    check_boundary("map-density-one")


def test_real_leg_three_map_boundary():
    check_boundary("map-density-three")


def test_retained_successful_leg_is_negative_control():
    check_boundary("map-density-two")


def test_repeated_positions_keep_distinct_window_identity():
    from app.mission.exporter.map_inputs import build_map_input

    captured, projected, _ = boundary("map-density-two")
    route = json.loads(captured.effective_route_json)
    for point in route["points"]:
        point["latitude"], point["longitude"] = 0, 0
    captured = replace(captured, effective_route_json=canonical_json(route))
    before = captured.effective_route_json
    scene, reasons = build_map_input(captured, projected)
    assert scene is not None and not reasons
    assert [marker["id"] for marker in scene["markers"]] == [
        row.id for row in projected.coordination_rows
    ]
    assert len(
        {
            scene["route"][marker["routeIndex"]]["timestamp"]
            for marker in scene["markers"]
        }
    ) == len(projected.coordination_rows)
    assert {(point["latitude"], point["longitude"]) for point in scene["route"]} == {
        (0, 0)
    }
    assert captured.effective_route_json == before


@pytest.mark.parametrize("name", ["map-density-one", "map-density-three"])
def test_overview_preserves_every_canonical_window_anchor(name):
    from app.mission.exporter import map_inputs

    assert hasattr(
        map_inputs, "prepare_map_input"
    ), "Specific scene eligibility contract is absent"
    captured, projected, _ = boundary(name)
    before = captured.effective_route_json
    result = map_inputs.prepare_map_input(captured, projected, include_markers=False)
    assert result.scene is not None and not result.diagnostics
    assert result.scene["markers"] == []
    timestamps = {point["timestamp"] for point in result.scene["route"]}
    assert all(
        row.start_time.isoformat().replace("+00:00", "Z") in timestamps
        for row in projected.coordination_rows
    )
    assert captured.effective_route_json == before
