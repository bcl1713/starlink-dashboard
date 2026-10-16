"""Independent UTC interval controls; height is intentionally absent."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS

import pytest

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.models.route_sigmets import IntersectionSpan

BASE = datetime(2026, 10, 30, tzinfo=timezone.utc)
MS = int(BASE.timestamp() * 1000)


def route(times=(BASE, BASE + timedelta(minutes=10))):
    return ParsedRoute(
        metadata=RouteMetadata(
            name="Timing", file_path="test.kml", point_count=len(times)
        ),
        points=[
            RoutePoint(longitude=i, latitude=0, expected_arrival_time=t)
            for i, t in enumerate(times)
        ],
    )


def span(start=0.25, end=0.75, segment=0):
    return IntersectionSpan(
        segment_index=segment,
        start_fraction=start,
        end_fraction=end,
        entry=[0.0, 0.0],
        exit=[1.0, 0.0],
        boundary_error_m=0.0,
    )


def evaluate(times=(BASE, BASE + timedelta(minutes=10)), spans=None, validity=None):
    from app.services.aviation_weather.route_encounters import (
        capture_encounter_plan,
        evaluate_encounters,
    )

    plan = capture_encounter_plan(route(times), "a" * 64, "ordinary", None)
    return evaluate_encounters(
        plan, spans or [span()], *(validity or (MS, MS + 600000))
    )


def test_fractional_passage_exact_utc():
    result = evaluate()
    assert result.status == "overlap" and result.unknown_count == 0
    assert (result.spans[0].entry_ms, result.spans[0].exit_ms) == (
        MS + 150000,
        MS + 450000,
    )
    assert result.spans[0].reason is None


@pytest.mark.parametrize(
    "start,end,validity,status",
    [
        (0.25, 0.25, (150000, 300000), "overlap"),
        (0.25, 0.25, (0, 150000), "no-overlap"),
        (0.1, 0.25, (150000, 300000), "overlap"),
        (0.0, 1.0, (600000, 700000), "overlap"),
    ],
)
def test_closed_passage_half_open_validity(start, end, validity, status):
    assert (
        evaluate(
            spans=[span(start, end)], validity=tuple(MS + v for v in validity)
        ).status
        == status
    )


def test_midnight_and_millisecond_before_expiry():
    result = evaluate((BASE - timedelta(minutes=5), BASE + timedelta(minutes=5)))
    assert result.spans[0].entry_ms == MS - 150000
    assert (
        evaluate(
            (BASE, BASE + timedelta(milliseconds=1)), [span(0.0, 0.0)], (MS, MS + 1)
        ).status
        == "overlap"
    )


@pytest.mark.parametrize(
    "times,reason",
    [
        ((None, BASE), "missing-timing"),
        ((BASE.replace(tzinfo=None), BASE), "invalid-timing"),
        ((BASE, BASE), "invalid-timing"),
        ((BASE + timedelta(seconds=1), BASE), "invalid-timing"),
    ],
)
def test_missing_or_invalid_times_are_unknown(times, reason):
    result = evaluate(times)
    assert result.status == "unknown" and result.unknown_count == 1
    assert result.spans[0].entry_ms is None and result.spans[0].exit_ms is None
    assert result.spans[0].reason == reason


def test_unknown_and_disjoint_spans_keep_one_to_one_evidence():
    result = evaluate(spans=[span(), span(segment=3)])
    assert result.status == "overlap" and result.unknown_count == 1
    assert result.spans[1].reason == "ambiguous-association"
    assert (
        evaluate(
            spans=[span(), span(segment=3)], validity=(MS + 900000, MS + 1000000)
        ).status
        == "unknown"
    )
    assert evaluate(spans=[span(0.0, 0.1), span(0.9, 1.0)]).unknown_count == 0


def test_unavailable_plan_is_explicit():
    from app.services.aviation_weather.route_encounters import evaluate_encounters

    assert (
        evaluate_encounters(None, [span()], MS, MS + 600000).spans[0].reason
        == "unavailable-plan"
    )


def test_capture_revision_changes_only_with_timing_and_is_frozen():
    from app.services.aviation_weather.route_context import select_route_context

    value = route()
    manager = NS(get_active_route_id=lambda: "test", get_active_route=lambda: value)
    first = select_route_context(manager, None)
    assert first.encounter_plan is not None
    original = first.encounter_plan
    value.points[1].altitude = 12345
    value.metadata.name = "Renamed"
    assert (
        select_route_context(manager, None).encounter_plan.revision == original.revision
    )
    value.points[1].expected_arrival_time += timedelta(minutes=1)
    third = select_route_context(manager, None)
    assert third.context_key == first.context_key
    assert third.encounter_plan.revision != original.revision
    assert original.times_ms[1] == MS + 600000
    with pytest.raises(ValueError):
        original.revision = "b" * 64


def test_altitude_free_kml_retains_waypoint_timing():
    from pathlib import Path

    from app.services.aviation_weather.route_encounters import (
        capture_encounter_plan,
        evaluate_encounters,
    )
    from app.services.kml_parser import parse_kml_file

    value = parse_kml_file(
        Path(__file__).parents[1] / "fixtures/route-sigmets/altitude-free-timing.kml"
    )
    assert all(point.altitude is None for point in value.points)
    plan = capture_encounter_plan(value, "a" * 64, "ordinary", None)
    assert plan.times_ms == (MS, MS + 600000, MS + 1200000, MS + 1800000)
    result = evaluate_encounters(plan, [span()], MS, MS + 600000)
    assert result.status == "overlap"
    for point in value.points:
        point.altitude = 10000
    assert (
        capture_encounter_plan(value, "a" * 64, "ordinary", None).revision
        == plan.revision
    )
