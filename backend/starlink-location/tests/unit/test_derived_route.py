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
