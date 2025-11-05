"Unit tests for RouteETACalculator convenience methods."

from datetime import datetime, timedelta, timezone

import pytest

from app.models.route import (
    ParsedRoute,
    RouteMetadata,
    RoutePoint,
    RouteTimingProfile,
    RouteWaypoint,
)
from app.services.route_eta_calculator import (
    RouteETACalculator,
    clear_eta_cache,
    cleanup_eta_cache,
)


def _build_sample_route() -> ParsedRoute:
    """Create a simple three-point route with timing metadata for tests."""
    now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
    metadata = RouteMetadata(
        name="Test Route",
        description=None,
        file_path="test-route.kml",
        imported_at=now,
        point_count=3,
    )

    points = [
        RoutePoint(
            latitude=40.0000,
            longitude=-75.0000,
            altitude=0.0,
            sequence=0,
            expected_segment_speed_knots=200.0,
            expected_arrival_time=now,
        ),
        RoutePoint(
            latitude=40.5000,
            longitude=-75.0000,
            altitude=0.0,
            sequence=1,
            expected_segment_speed_knots=220.0,
            expected_arrival_time=now + timedelta(minutes=15),
        ),
        RoutePoint(
            latitude=41.0000,
            longitude=-75.0000,
            altitude=0.0,
            sequence=2,
            expected_segment_speed_knots=230.0,
            expected_arrival_time=now + timedelta(minutes=30),
        ),
    ]

    waypoints = [
        RouteWaypoint(
            name="Departure",
            description=None,
            style_url=None,
            latitude=40.0000,
            longitude=-75.0000,
            altitude=None,
            order=0,
            role="departure",
            expected_arrival_time=now,
        ),
        RouteWaypoint(
            name="Arrival",
            description=None,
            style_url=None,
            latitude=41.0000,
            longitude=-75.0000,
            altitude=None,
            order=1,
            role="arrival",
            expected_arrival_time=now + timedelta(minutes=30),
        ),
    ]

    timing_profile = RouteTimingProfile(
        departure_time=now,
        arrival_time=now + timedelta(minutes=30),
        total_expected_duration_seconds=1800.0,
        has_timing_data=True,
        segment_count_with_timing=2,
    )

    return ParsedRoute(
        metadata=metadata,
        points=points,
        waypoints=waypoints,
        timing_profile=timing_profile,
    )


def test_get_route_progress_with_timing_profile():
    """Route progress should report reasonable distances and timing values."""
    route = _build_sample_route()
    calculator = RouteETACalculator(route)

    # Position near the second point.
    progress = calculator.get_route_progress(
        current_lat=40.55,
        current_lon=-75.0,
    )

    assert progress["current_waypoint_name"] in {"Arrival", "Departure"}
    assert 0 < progress["progress_percent"] < 100
    assert progress["total_route_distance_meters"] > 0
    assert progress["expected_total_duration_seconds"] == pytest.approx(1800.0)
    assert progress["expected_duration_remaining_seconds"] is not None


def test_calculate_eta_to_waypoint_respects_speed():
    """ETA to waypoint should use provided segment speed and include expected arrival."""
    route = _build_sample_route()
    calculator = RouteETACalculator(route)

    eta = calculator.calculate_eta_to_waypoint(
        waypoint_index=1,
        current_lat=40.1,
        current_lon=-75.0,
    )

    assert eta["waypoint_name"] == "Arrival"
    assert eta["estimated_speed_knots"] > 0
    assert eta["distance_remaining_meters"] > 0
    assert eta["estimated_time_remaining_seconds"] is not None
    assert eta["expected_arrival_time"] is not None


def test_calculate_eta_to_location_fallback_speed():
    """ETA to arbitrary location should fall back to average speed when timing present."""
    route = _build_sample_route()
    calculator = RouteETACalculator(route)

    eta = calculator.calculate_eta_to_location(
        target_lat=41.0,
        target_lon=-75.0,
        current_lat=40.0,
        current_lon=-75.0,
    )

    assert eta["distance_to_target_meters"] > 0
    assert eta["estimated_speed_knots"] > 0
    assert eta["estimated_time_remaining_seconds"] is not None


def test_project_poi_to_route_returns_progress():
    """Projection helper should yield bounded progress percentage and small distance for on-route POI."""
    route = _build_sample_route()
    calculator = RouteETACalculator(route)

    projection = calculator.project_poi_to_route(40.5, -75.0)
    assert projection["projected_route_progress"] >= 0
    assert projection["projected_route_progress"] <= 100
    assert projection["distance_to_route_meters"] < 1000


def test_cache_is_cleared_between_runs():
    """Ensure global cache can be cleared to avoid test interference."""
    route = _build_sample_route()
    calculator = RouteETACalculator(route)
    calculator.calculate_eta_to_location(41.0, -75.0, 40.0, -75.0)  # populate cache
    clear_eta_cache()
    # Subsequent cleanup should remove nothing.
    assert cleanup_eta_cache() == 0
