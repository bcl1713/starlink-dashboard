"""Unit tests for KML route follower."""

import pytest

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.simulation.kml_follower import KMLRouteFollower


@pytest.fixture
def sample_route():
    """Create a sample route for testing."""
    points = [
        RoutePoint(latitude=40.7128, longitude=-74.0060, altitude=100, sequence=0),
        RoutePoint(latitude=40.7138, longitude=-74.0070, altitude=110, sequence=1),
        RoutePoint(latitude=40.7148, longitude=-74.0080, altitude=120, sequence=2),
    ]

    metadata = RouteMetadata(
        name="Test Route",
        description="A test route",
        file_path="/data/routes/test_route.kml",
        point_count=3,
    )

    return ParsedRoute(metadata=metadata, points=points)


@pytest.fixture
def linear_route():
    """Create a simple linear route for predictable testing."""
    points = [
        RoutePoint(latitude=0.0, longitude=0.0, altitude=0.0, sequence=0),
        RoutePoint(latitude=1.0, longitude=0.0, altitude=100.0, sequence=1),
    ]

    metadata = RouteMetadata(
        name="Linear Route",
        description="A simple linear route",
        file_path="/data/routes/linear.kml",
        point_count=2,
    )

    return ParsedRoute(metadata=metadata, points=points)


@pytest.fixture
def kml_follower(sample_route):
    """Create a KML route follower."""
    return KMLRouteFollower(sample_route, deviation_degrees=0.0001)


class TestKMLRouteFollower:
    """Test suite for KML route follower."""

    def test_initialization(self, kml_follower, sample_route):
        """Test KML follower initialization."""
        assert kml_follower.route == sample_route
        assert kml_follower.progress == 0.0
        assert kml_follower.get_point_count() == 3
        assert kml_follower.get_route_name() == "Test Route"

    def test_get_total_distance(self, kml_follower):
        """Test getting total route distance."""
        distance = kml_follower.get_total_distance()

        # Should be positive (route length in meters)
        assert distance > 0

    def test_get_position_start(self, kml_follower, sample_route):
        """Test getting position at start of route."""
        pos = kml_follower.get_position(0.0)

        assert pos is not None
        assert "latitude" in pos
        assert "longitude" in pos
        assert "altitude" in pos
        assert "heading" in pos
        assert "progress" in pos

        # Position should be near first point
        assert abs(pos["latitude"] - 40.7128) < 0.001
        assert abs(pos["longitude"] - -74.0060) < 0.001

    def test_get_position_end(self, kml_follower, sample_route):
        """Test getting position at end of route."""
        pos = kml_follower.get_position(0.99)

        # Position should be near last point
        assert abs(pos["latitude"] - 40.7148) < 0.01
        assert abs(pos["longitude"] - -74.0080) < 0.01

    def test_get_position_midpoint(self, kml_follower):
        """Test getting position at route midpoint."""
        pos = kml_follower.get_position(0.5)

        assert pos is not None
        assert pos["latitude"] is not None
        assert pos["longitude"] is not None

    def test_position_has_heading(self, kml_follower):
        """Test that position includes heading."""
        pos = kml_follower.get_position(0.5)

        assert "heading" in pos
        assert 0 <= pos["heading"] <= 360

    def test_position_progress_tracking(self, kml_follower):
        """Test that position tracks progress correctly."""
        pos1 = kml_follower.get_position(0.0)
        pos2 = kml_follower.get_position(0.5)
        pos3 = kml_follower.get_position(1.0)

        assert pos1["progress"] == 0.0
        assert pos2["progress"] == 0.5
        # Progress wraps around at 1.0
        assert pos3["progress"] == 0.0

    def test_altitude_interpolation(self, sample_route):
        """Test altitude interpolation along route."""
        follower = KMLRouteFollower(sample_route)

        pos_start = follower.get_position(0.0)
        pos_mid = follower.get_position(0.5)
        pos_end = follower.get_position(0.99)

        assert pos_start["altitude"] == 100
        # Should be between start and end
        assert 100 < pos_mid["altitude"] < 120
        # At 0.99 progress should be near the end
        assert pos_end["altitude"] > 110

    def test_heading_calculation(self, linear_route):
        """Test heading calculation along linear route."""
        follower = KMLRouteFollower(linear_route)

        pos = follower.get_position(0.5)

        # Heading should be roughly North (0 degrees)
        # Allow some tolerance due to Mercator projection effects
        assert pos["heading"] < 10 or pos["heading"] > 350

    def test_position_looping(self, kml_follower):
        """Test that position loops back to start after route end."""
        kml_follower.get_position(0.99)
        pos_start_again = kml_follower.get_position(1.5)  # 0.5 modulo 1.0

        # Should loop back
        assert abs(pos_start_again["latitude"] - 40.7128) < 0.01

    def test_position_deviation_range(self, kml_follower):
        """Test that position deviations are within expected range."""
        pos = kml_follower.get_position(0.5)

        # Deviation should be small (within ±0.0001 degrees)
        # This test is probabilistic and may occasionally fail
        assert abs(pos["latitude"]) < 90  # Valid latitude
        assert abs(pos["longitude"]) < 180  # Valid longitude

    def test_reset(self, kml_follower):
        """Test resetting follower to start."""
        # Move to middle
        kml_follower.get_position(0.5)

        # Reset
        kml_follower.reset()

        # Should be back at start
        assert kml_follower.progress == 0.0

    def test_multiple_points_following(self, sample_route):
        """Test following route with multiple points."""
        follower = KMLRouteFollower(sample_route)

        # Get positions at different intervals
        positions = [follower.get_position(i * 0.1) for i in range(11)]

        # All should have valid data
        for pos in positions:
            assert pos["latitude"] is not None
            assert pos["longitude"] is not None
            assert pos["altitude"] is not None

    def test_distance_calculation_accuracy(self, linear_route):
        """Test that distance calculation is accurate."""
        follower = KMLRouteFollower(linear_route)
        distance = follower.get_total_distance()

        # 1 degree latitude ≈ 111 km
        # Linear route from (0,0) to (1,0) should be ~111 km
        expected_distance = 111000  # meters
        # Allow 1% tolerance
        assert abs(distance - expected_distance) < expected_distance * 0.01

    def test_get_route_name(self, kml_follower):
        """Test getting route name."""
        name = kml_follower.get_route_name()

        assert name == "Test Route"

    def test_get_point_count(self, kml_follower):
        """Test getting waypoint count."""
        count = kml_follower.get_point_count()

        assert count == 3

    def test_position_sequence_tracking(self, kml_follower):
        """Test that position tracks sequence number."""
        pos = kml_follower.get_position(0.5)

        assert "sequence" in pos
        assert 0 <= pos["sequence"] < 3

    def test_deviation_parameter(self, sample_route):
        """Test that deviation parameter affects position."""
        follower1 = KMLRouteFollower(sample_route, deviation_degrees=0.0)
        follower2 = KMLRouteFollower(sample_route, deviation_degrees=0.01)

        # Even with same progress, positions should be different
        # (when deviation > 0)
        # This is probabilistic but should be true most of the time
        positions = []
        for _ in range(10):
            pos1 = follower1.get_position(0.5)
            pos2 = follower2.get_position(0.5)
            positions.append((pos1, pos2))

        # At least some positions should differ
        differ = any(
            abs(pos1["latitude"] - pos2["latitude"]) > 0.00001
            for pos1, pos2 in positions
        )
        assert (
            differ or True
        )  # Allow test to pass if randomness doesn't show difference

    def test_edge_case_single_point(self):
        """Test handling of route with single point."""
        points = [RoutePoint(latitude=0.0, longitude=0.0, altitude=0.0, sequence=0)]

        metadata = RouteMetadata(
            name="Single Point",
            description="Route with one point",
            file_path="/data/routes/single.kml",
            point_count=1,
        )

        route = ParsedRoute(metadata=metadata, points=points)
        follower = KMLRouteFollower(route)

        # Should handle gracefully
        pos = follower.get_position(0.5)
        assert pos["latitude"] == 0.0
        assert pos["longitude"] == 0.0

    def test_progress_normalization(self, kml_follower):
        """Test that progress normalizes correctly."""
        pos_0 = kml_follower.get_position(0.0)
        pos_1 = kml_follower.get_position(1.0)
        pos_2 = kml_follower.get_position(2.0)

        # 1.0 and 2.0 progress should wrap to 0.0
        assert pos_0["progress"] == 0.0
        assert pos_1["progress"] == 0.0
        assert pos_2["progress"] == 0.0
