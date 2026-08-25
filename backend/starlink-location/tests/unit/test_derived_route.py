"""Tests for immutable Manual AR derived-route estimates."""

from datetime import datetime, timedelta, timezone

from app.mission.derived_route import build_derived_route_estimate, derived_route_for_estimate
from app.mission.timeline_builder.calculator import RouteTemporalProjector
from app.mission.models import (
    ManualAARTrack,
    ManualAARTrackPoint,
    ManualRouteSplice,
    TransportConfig,
)
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteTimingProfile


def _route(points: list[tuple[float, float]]) -> ParsedRoute:
    start = datetime(2026, 8, 25, 12, 0, tzinfo=timezone.utc)
    return ParsedRoute(
        metadata=RouteMetadata(name="planned", file_path="planned.kml", point_count=len(points)),
        points=[
            RoutePoint(
                latitude=latitude,
                longitude=longitude,
                sequence=index,
                expected_arrival_time=start + timedelta(hours=index),
                expected_segment_speed_knots=500.0 if index else None,
            )
            for index, (latitude, longitude) in enumerate(points)
        ],
        timing_profile=RouteTimingProfile(
            departure_time=start,
            arrival_time=start + timedelta(hours=len(points) - 1),
            has_timing_data=True,
        ),
    )


def _track(points: list[tuple[float, float]]) -> ManualAARTrack:
    return ManualAARTrack(
        id="ar-1",
        name="Manual AR",
        points=[ManualAARTrackPoint(latitude=lat, longitude=lon) for lat, lon in points],
    )


def test_builds_forward_estimate_without_mutating_source_route():
    route = _route([(0, 0), (0, 2), (0, 4)])
    original = route.model_dump(mode="json")

    estimate = build_derived_route_estimate(route, _track([(0.2, 1), (0.2, 3)]))

    assert estimate.available is True
    assert estimate.estimated is True
    assert estimate.leave_anchor is not None
    assert estimate.rejoin_anchor is not None
    assert estimate.leave_anchor.progress_nm < estimate.rejoin_anchor.progress_nm
    assert estimate.derived_distance_nm > 0
    assert estimate.delta_seconds != 0
    assert route.model_dump(mode="json") == original
    assert {point.provenance for point in estimate.points} >= {
        "planned",
        "entry_connector",
        "manual_track",
        "exit_connector",
    }


def test_antimeridian_splice_uses_short_connector_and_not_world_span():
    route = _route([(10, 179), (10, -179), (10, -177)])
    estimate = build_derived_route_estimate(
        route, _track([(10.1, 179.5), (10.1, -178.5)])
    )

    assert estimate.available is True
    assert estimate.leave_anchor is not None
    assert estimate.leave_anchor.connector_nm < 20
    assert estimate.rejoin_anchor is not None
    assert estimate.rejoin_anchor.connector_nm < 20


def test_remote_or_reverse_track_returns_planned_no_feasible_splice():
    route = _route([(0, 0), (0, 2), (0, 4)])

    estimate = build_derived_route_estimate(route, _track([(20, 1), (20, 3)]))

    assert estimate.available is False
    assert estimate.unavailable_reason == "no_feasible_splice"
    assert estimate.delta_seconds == 0
    assert estimate.points == []


def test_persists_only_explicit_manual_route_splice_input():
    splice = ManualRouteSplice(enabled_track_id="ar-1", speed_knots=480.0)
    config = TransportConfig(initial_x_satellite_id="X-1", manual_route_splice=splice)

    assert config.manual_route_splice.enabled_track_id == "ar-1"
    assert "derived" not in config.model_dump_json().lower()


def test_feasible_estimate_builds_piecewise_route_with_one_downstream_shift():
    route = _route([(0, 0), (0, 2), (0, 4)])
    estimate = build_derived_route_estimate(route, _track([(1, 1), (1, 3)]))

    derived = derived_route_for_estimate(route, estimate)

    assert derived is not route
    assert derived.points[0].expected_arrival_time == route.points[0].expected_arrival_time
    assert derived.points[-1].expected_arrival_time == (
        route.points[-1].expected_arrival_time
        + timedelta(seconds=estimate.delta_seconds)
    )
    projector = RouteTemporalProjector(
        derived,
        derived.timing_profile.departure_time,
        derived.timing_profile.arrival_time,
    )
    assert projector.timestamp_for_distance(projector.total_distance) == (
        route.points[-1].expected_arrival_time
        + timedelta(seconds=estimate.delta_seconds)
    )


def test_uses_local_speed_before_global_speed_for_diversion():
    route = _route([(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)])
    route.points[1].expected_segment_speed_knots = 400.0
    route.points[2].expected_segment_speed_knots = 400.0
    route.points[3].expected_segment_speed_knots = 700.0
    route.points[4].expected_segment_speed_knots = 700.0

    estimate = build_derived_route_estimate(route, _track([(0.2, 1.2), (0.2, 1.8)]))

    assert estimate.available is True
    assert estimate.speed_knots == 400.0
    assert estimate.speed_source == "local_weighted_median"


def test_invalid_anchor_override_returns_explicit_unavailable_result():
    route = _route([(0, 0), (0, 2), (0, 4)])
    override = ManualRouteSplice(
        enabled_track_id="ar-1",
        leave_segment_index=1,
        leave_fraction=0.8,
        rejoin_segment_index=0,
        rejoin_fraction=0.2,
    )

    estimate = build_derived_route_estimate(
        route, _track([(0.2, 1), (0.2, 3)]), override
    )

    assert estimate.available is False
    assert estimate.unavailable_reason == "invalid_splice_override"


def test_out_of_order_anchor_times_use_calculated_replaced_duration():
    route = _route([(0, 0), (0, 2), (0, 4)])
    route.points[2].expected_arrival_time = route.points[1].expected_arrival_time

    estimate = build_derived_route_estimate(route, _track([(0.2, 1), (0.2, 3)]))

    assert estimate.available is True
    assert "distance/speed" in " ".join(estimate.warnings)
    assert estimate.planned_duration_seconds > 0


def test_zero_length_source_segments_are_ignored_without_mutating_route():
    route = _route([(0, 0), (0, 0), (0, 2), (0, 4)])
    original = route.model_dump(mode="json")

    estimate = build_derived_route_estimate(route, _track([(0.2, 1), (0.2, 3)]))

    assert estimate.available is True
    assert estimate.leave_anchor is not None
    assert estimate.leave_anchor.segment_index != 0
    assert route.model_dump(mode="json") == original


def test_uses_labelled_500_knot_fallback_without_speed_or_profile():
    route = _route([(0, 0), (0, 2), (0, 4)])
    route.timing_profile = None
    for point in route.points:
        point.expected_segment_speed_knots = None

    estimate = build_derived_route_estimate(route, _track([(0.2, 1), (0.2, 3)]))

    assert estimate.available is True
    assert estimate.speed_knots == 500.0
    assert estimate.speed_source == "fallback_500kt"


def test_feasible_override_uses_explicit_speed_and_remains_deterministic():
    route = _route([(0, 0), (0, 2), (0, 4)])
    override = ManualRouteSplice(
        enabled_track_id="ar-1",
        leave_segment_index=0,
        leave_fraction=0.5,
        rejoin_segment_index=1,
        rejoin_fraction=0.5,
        speed_knots=450.0,
    )
    track = _track([(0.2, 1), (0.2, 3)])

    first = build_derived_route_estimate(route, track, override)
    second = build_derived_route_estimate(route, track, override)

    assert first.available is True
    assert first.speed_knots == 450.0
    assert first.speed_source == "operator_override"
    assert first.as_dict() == second.as_dict()
