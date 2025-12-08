"""Unit tests for route timing functionality."""

from datetime import datetime, timedelta
from app.models.route import RoutePoint, RouteWaypoint
from app.services.kml import (
    extract_timestamp_from_description,
    haversine_distance,
    calculate_segment_speeds,
    assign_waypoint_timestamps_to_points,
)


class TestHaversineDistance:
    """Test haversine distance calculation."""

    def test_same_point(self):
        """Distance between same point should be zero."""
        distance = haversine_distance(40.7128, -74.0060, 40.7128, -74.0060)
        assert distance < 1  # Near zero (floating point)

    def test_new_york_to_los_angeles(self):
        """Test known distance between NYC and LA."""
        # NYC: 40.7128°N, 74.0060°W
        # LA: 34.0522°N, 118.2437°W
        distance = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
        # Approximate distance is 3944 km = 3,944,000 meters
        assert 3900000 < distance < 4000000, f"Got {distance} meters"

    def test_zero_distance_same_location(self):
        """Zero distance for identical locations."""
        distance = haversine_distance(0, 0, 0, 0)
        assert distance < 1

    def test_antipodal_points(self):
        """Distance across Earth should be approximately π * Earth radius."""
        # From north pole to south pole
        distance = haversine_distance(90, 0, -90, 0)
        # Should be approximately 20,036 km (Earth circumference / 2)
        assert 19000000 < distance < 21000000


class TestSegmentSpeedCalculation:
    """Test segment speed calculation."""

    def test_simple_two_point_route(self):
        """Calculate speed for simple two-point route."""
        # Create two points with timestamps
        start_time = datetime(2025, 10, 27, 16, 51, 13)
        end_time = datetime(2025, 10, 27, 17, 2, 13)  # 11 minutes = 660 seconds

        # Points are approximately 20 nm apart (37 km)
        point1 = RoutePoint(
            latitude=37.0,
            longitude=-122.0,
            altitude=10000,
            sequence=0,
            expected_arrival_time=start_time,
        )
        point2 = RoutePoint(
            latitude=37.01,  # Small lat difference
            longitude=-121.98,  # Small lon difference
            altitude=10000,
            sequence=1,
            expected_arrival_time=end_time,
        )

        points = [point1, point2]
        calculate_segment_speeds(points)

        # Point 2 should have a calculated speed
        assert point2.expected_segment_speed_knots is not None
        assert point2.expected_segment_speed_knots > 0

    def test_no_calculation_without_both_timestamps(self):
        """No speed calculated if either point lacks timestamp."""
        point1 = RoutePoint(
            latitude=37.0,
            longitude=-122.0,
            altitude=10000,
            sequence=0,
            expected_arrival_time=datetime(2025, 10, 27, 16, 51, 13),
        )
        point2 = RoutePoint(
            latitude=37.01,
            longitude=-121.98,
            altitude=10000,
            sequence=1,
            expected_arrival_time=None,  # No timestamp
        )

        points = [point1, point2]
        calculate_segment_speeds(points)

        # Point 2 should not have a speed
        assert point2.expected_segment_speed_knots is None

    def test_no_calculation_with_zero_time_delta(self):
        """No speed calculated if time delta is zero."""
        same_time = datetime(2025, 10, 27, 16, 51, 13)

        point1 = RoutePoint(
            latitude=37.0,
            longitude=-122.0,
            altitude=10000,
            sequence=0,
            expected_arrival_time=same_time,
        )
        point2 = RoutePoint(
            latitude=37.01,
            longitude=-121.98,
            altitude=10000,
            sequence=1,
            expected_arrival_time=same_time,  # Same time
        )

        points = [point1, point2]
        calculate_segment_speeds(points)

        # Point 2 should not have a speed (time delta is zero)
        assert point2.expected_segment_speed_knots is None

    def test_realistic_flight_speeds(self):
        """Test realistic flight speed calculation."""
        # Simulate two points 100 km apart, 12 minutes apart
        # Expected speed: 100 km / 12 min = 500 km/h ≈ 270 knots

        start_time = datetime(2025, 10, 27, 16, 51, 13)
        end_time = start_time + timedelta(minutes=12)

        # Approximate points 100 km apart
        # 1 degree latitude ≈ 111 km
        point1 = RoutePoint(
            latitude=37.0,
            longitude=-122.0,
            altitude=10000,
            sequence=0,
            expected_arrival_time=start_time,
        )
        point2 = RoutePoint(
            latitude=37.9,  # About 100 km north
            longitude=-122.0,
            altitude=10000,
            sequence=1,
            expected_arrival_time=end_time,
        )

        points = [point1, point2]
        calculate_segment_speeds(points)

        # Check speed is reasonable for flight
        assert point2.expected_segment_speed_knots is not None
        # Expect around 270 knots (100 km / 12 min / 0.5144 km/knot)
        assert 200 < point2.expected_segment_speed_knots < 400


class TestWaypointTimestampAssignment:
    """Test assignment of waypoint timestamps to route points."""

    def test_nearest_point_assignment(self):
        """Assign timestamp to nearest route point."""
        waypoint = RouteWaypoint(
            name="TEST",
            description="Time Over Waypoint: 2025-10-27 16:51:13Z",
            style_url=None,
            latitude=37.0,
            longitude=-122.0,
            altitude=None,
            order=0,
            role="waypoint",
            expected_arrival_time=datetime(2025, 10, 27, 16, 51, 13),
        )

        # Create points, one very close to waypoint
        points = [
            RoutePoint(
                latitude=36.0,
                longitude=-121.0,
                altitude=10000,
                sequence=0,
            ),
            RoutePoint(
                latitude=37.0001,  # Very close to waypoint
                longitude=-122.0001,
                altitude=10000,
                sequence=1,
            ),
            RoutePoint(
                latitude=38.0,
                longitude=-123.0,
                altitude=10000,
                sequence=2,
            ),
        ]

        waypoints = [waypoint]
        assign_waypoint_timestamps_to_points(points, waypoints)

        # Nearest point (index 1) should get the timestamp
        assert points[1].expected_arrival_time is not None
        assert points[1].expected_arrival_time == waypoint.expected_arrival_time
        # Other points should not
        assert points[0].expected_arrival_time is None
        assert points[2].expected_arrival_time is None

    def test_skip_distant_waypoints(self):
        """Don't assign timestamp to waypoint farther than 1000m."""
        waypoint = RouteWaypoint(
            name="FAR",
            description="Time Over Waypoint: 2025-10-27 16:51:13Z",
            style_url=None,
            latitude=37.0,
            longitude=-122.0,
            altitude=None,
            order=0,
            role="waypoint",
            expected_arrival_time=datetime(2025, 10, 27, 16, 51, 13),
        )

        # Create point far from waypoint (> 1000m)
        points = [
            RoutePoint(
                latitude=37.02,  # About 2.2 km away
                longitude=-122.0,
                altitude=10000,
                sequence=0,
            ),
        ]

        waypoints = [waypoint]
        assign_waypoint_timestamps_to_points(points, waypoints)

        # Point should not get assigned timestamp (too far)
        assert points[0].expected_arrival_time is None

    def test_no_crash_without_timestamps(self):
        """Handle waypoints without timestamps gracefully."""
        waypoint = RouteWaypoint(
            name="TEST",
            description="No timing data here",
            style_url=None,
            latitude=37.0,
            longitude=-122.0,
            altitude=None,
            order=0,
            role="waypoint",
            expected_arrival_time=None,  # No timestamp
        )

        points = [
            RoutePoint(
                latitude=37.0,
                longitude=-122.0,
                altitude=10000,
                sequence=0,
            ),
        ]

        waypoints = [waypoint]
        # Should not crash
        assign_waypoint_timestamps_to_points(points, waypoints)

        assert points[0].expected_arrival_time is None


class TestTimestampExtraction:
    """Integration tests for timestamp extraction from descriptions."""

    def test_extract_from_flight_plan_description(self):
        """Extract timestamp from flight plan waypoint description."""
        description = (
            "Daniel K Inouye International\n Time Over Waypoint: 2025-10-27 16:51:13Z"
        )
        timestamp = extract_timestamp_from_description(description)

        assert timestamp is not None
        assert timestamp == datetime(2025, 10, 27, 16, 51, 13)

    def test_extract_with_minimal_description(self):
        """Extract from minimal description with just timestamp."""
        description = " Time Over Waypoint: 2025-10-27 17:10:26Z"
        timestamp = extract_timestamp_from_description(description)

        assert timestamp is not None
        assert timestamp == datetime(2025, 10, 27, 17, 10, 26)

    def test_none_for_missing_timestamp(self):
        """Return None when timestamp not found."""
        description = "Airport name only, no timing"
        timestamp = extract_timestamp_from_description(description)

        assert timestamp is None


class TestCompleteTimingPipeline:
    """Test complete timing extraction pipeline."""

    def test_pipeline_handles_mixed_timing_data(self):
        """Test pipeline works with partial timing information."""
        # Some waypoints have timestamps
        waypoints = [
            RouteWaypoint(
                name="A",
                description="Time Over Waypoint: 2025-10-27 16:51:13Z",
                style_url=None,
                latitude=37.0,
                longitude=-122.0,
                altitude=None,
                order=0,
                role="departure",
                expected_arrival_time=datetime(2025, 10, 27, 16, 51, 13),
            ),
            RouteWaypoint(
                name="B",
                description="No timing",
                style_url=None,
                latitude=37.01,
                longitude=-121.99,
                altitude=None,
                order=1,
                role="waypoint",
                expected_arrival_time=None,
            ),
        ]

        points = [
            RoutePoint(latitude=37.0, longitude=-122.0, altitude=10000, sequence=0),
            RoutePoint(latitude=37.01, longitude=-121.99, altitude=10000, sequence=1),
        ]

        # Run pipeline - should not crash with partial data
        assign_waypoint_timestamps_to_points(points, waypoints)
        calculate_segment_speeds(points)

        # First point should have timestamp
        assert points[0].expected_arrival_time is not None
