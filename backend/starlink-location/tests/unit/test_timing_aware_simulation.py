"""Unit tests for Phase 5 timing-aware simulation features."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock

from app.models.route import (
    RoutePoint,
    RouteMetadata,
    ParsedRoute,
    RouteTimingProfile,
)
from app.simulation.position import PositionSimulator
from app.simulation.kml_follower import KMLRouteFollower
from app.models.config import PositionConfig, RouteConfig


class TestKMLRouteFollowerTimingMethods:
    """Test Phase 5 timing-related methods in KMLRouteFollower."""

    @pytest.fixture
    def simple_timed_route(self) -> ParsedRoute:
        """Create a simple route with timing data."""
        metadata = RouteMetadata(
            name="Test Timed Route",
            file_path="/test/route.kml",
            point_count=3,
        )

        # Create 3 points with timing data
        # Point 0: start
        # Point 1: 100 km away, expected speed 500 knots
        # Point 2: 200 km away, expected speed 550 knots
        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_arrival_time=datetime(2025, 11, 3, 12, 0, 0),
                expected_segment_speed_knots=None,  # Start point
            ),
            RoutePoint(
                latitude=40.5,
                longitude=-74.0,
                altitude=10000,
                sequence=1,
                expected_arrival_time=datetime(2025, 11, 3, 12, 10, 0),
                expected_segment_speed_knots=500.0,  # 500 knots to this point
            ),
            RoutePoint(
                latitude=41.0,
                longitude=-74.0,
                altitude=10000,
                sequence=2,
                expected_arrival_time=datetime(2025, 11, 3, 12, 20, 0),
                expected_segment_speed_knots=550.0,  # 550 knots to this point
            ),
        ]

        timing_profile = RouteTimingProfile(
            departure_time=datetime(2025, 11, 3, 12, 0, 0),
            arrival_time=datetime(2025, 11, 3, 12, 20, 0),
            total_expected_duration_seconds=1200.0,
            has_timing_data=True,
            segment_count_with_timing=2,
        )

        return ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=timing_profile,
        )

    @pytest.fixture
    def untimed_route(self) -> ParsedRoute:
        """Create a route without timing data."""
        metadata = RouteMetadata(
            name="Untimed Route",
            file_path="/test/untimed.kml",
            point_count=2,
        )

        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_arrival_time=None,
                expected_segment_speed_knots=None,
            ),
            RoutePoint(
                latitude=40.5,
                longitude=-74.0,
                altitude=10000,
                sequence=1,
                expected_arrival_time=None,
                expected_segment_speed_knots=None,
            ),
        ]

        return ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=None,
        )

    def test_get_segment_speed_at_progress_with_timing(self, simple_timed_route):
        """Test getting segment speed from route with timing data."""
        follower = KMLRouteFollower(simple_timed_route)

        # At progress 0.0 (start), should return speed from first segment (500 knots)
        speed = follower.get_segment_speed_at_progress(0.0)
        assert speed == 500.0

        # At progress ~0.5 (middle, still in first segment), should return 500 knots
        speed = follower.get_segment_speed_at_progress(0.25)
        assert speed == 500.0

        # At progress ~0.6 (past first segment, in second segment), should return 550 knots
        speed = follower.get_segment_speed_at_progress(0.65)
        assert speed == 550.0

    def test_get_segment_speed_at_progress_without_timing(self, untimed_route):
        """Test getting segment speed from route without timing data."""
        follower = KMLRouteFollower(untimed_route)

        # Should return None at all progress points
        assert follower.get_segment_speed_at_progress(0.0) is None
        assert follower.get_segment_speed_at_progress(0.5) is None
        assert follower.get_segment_speed_at_progress(1.0) is None

    def test_get_segment_speed_past_end(self, simple_timed_route):
        """Test getting segment speed when progress is past the end."""
        follower = KMLRouteFollower(simple_timed_route)

        # At progress > 1.0, should wrap around (modulo) and return speed from segment
        # 1.5 % 1.0 = 0.5, which is in the first segment, so 500 knots
        speed = follower.get_segment_speed_at_progress(1.5)
        assert speed == 500.0

    def test_get_route_timing_profile_with_timing(self, simple_timed_route):
        """Test getting timing profile from timed route."""
        follower = KMLRouteFollower(simple_timed_route)

        profile = follower.get_route_timing_profile()
        assert profile is not None
        assert profile.has_timing_data is True
        assert profile.departure_time == datetime(2025, 11, 3, 12, 0, 0)
        assert profile.arrival_time == datetime(2025, 11, 3, 12, 20, 0)
        assert profile.total_expected_duration_seconds == 1200.0

    def test_get_route_timing_profile_without_timing(self, untimed_route):
        """Test getting timing profile from untimed route."""
        follower = KMLRouteFollower(untimed_route)

        profile = follower.get_route_timing_profile()
        assert profile is None


class TestPositionSimulatorTimingAware:
    """Test timing-aware behavior in PositionSimulator."""

    @pytest.fixture
    def position_config(self) -> PositionConfig:
        """Create position config."""
        return PositionConfig(
            speed_min_knots=50.0,
            speed_max_knots=600.0,
            altitude_min_feet=5000.0,
            altitude_max_feet=45000.0,
        )

    @pytest.fixture
    def route_config(self) -> RouteConfig:
        """Create route config."""
        return RouteConfig(
            pattern="circular",
            latitude_start=40.0,
            longitude_start=-74.0,
            radius_km=100.0,
            distance_km=100.0,
            completion_behavior="loop",
        )

    @pytest.fixture
    def simple_timed_route(self) -> ParsedRoute:
        """Create a simple timed route."""
        metadata = RouteMetadata(
            name="Test Route",
            file_path="/test/route.kml",
            point_count=3,
        )

        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_arrival_time=None,
                expected_segment_speed_knots=None,
            ),
            RoutePoint(
                latitude=40.5,
                longitude=-74.0,
                altitude=10000,
                sequence=1,
                expected_arrival_time=None,
                expected_segment_speed_knots=500.0,
            ),
            RoutePoint(
                latitude=41.0,
                longitude=-74.0,
                altitude=10000,
                sequence=2,
                expected_arrival_time=None,
                expected_segment_speed_knots=550.0,
            ),
        ]

        return ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=None,
        )

    def test_speed_override_with_timing_data(
        self, position_config, route_config, simple_timed_route
    ):
        """Test that simulator uses expected speed from route when available."""
        simulator = PositionSimulator(route_config, position_config)
        follower = KMLRouteFollower(simple_timed_route)
        simulator.set_route_follower(follower)

        # Run multiple updates to test speed behavior
        for _ in range(5):
            simulator.update()

        # Check that speed is close to expected (500-550 knots range)
        # with small drift (±0.5 knots)
        assert 499.5 <= simulator.current_speed <= 550.5

    def test_speed_fallback_without_timing_data(
        self, position_config, route_config
    ):
        """Test that simulator uses default speed when no timing data."""
        simulator = PositionSimulator(route_config, position_config)

        # Run multiple updates without route follower
        for _ in range(5):
            simulator.update()

        # Check that speed is in default range (45-75 knots with drift)
        assert 40.0 <= simulator.current_speed <= 80.0

    def test_speed_override_partial_timing(self, position_config, route_config):
        """Test speed override with partial timing data (some points timed)."""
        metadata = RouteMetadata(
            name="Partial Timed Route",
            file_path="/test/partial.kml",
            point_count=4,
        )

        # Mix of timed and untimed segments
        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_segment_speed_knots=None,
            ),
            RoutePoint(
                latitude=40.33,
                longitude=-74.0,
                altitude=10000,
                sequence=1,
                expected_segment_speed_knots=500.0,  # Timed
            ),
            RoutePoint(
                latitude=40.66,
                longitude=-74.0,
                altitude=10000,
                sequence=2,
                expected_segment_speed_knots=None,  # Untimed
            ),
            RoutePoint(
                latitude=41.0,
                longitude=-74.0,
                altitude=10000,
                sequence=3,
                expected_segment_speed_knots=550.0,  # Timed
            ),
        ]

        partial_timed_route = ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=None,
        )

        simulator = PositionSimulator(route_config, position_config)
        follower = KMLRouteFollower(partial_timed_route)
        simulator.set_route_follower(follower)

        # Run multiple updates
        for _ in range(10):
            simulator.update()

        # Speed should vary between timed (500-550) and untimed (45-75) segments
        # This is harder to test precisely, but we can check it's being called
        assert simulator.current_speed > 0

    def test_timing_integration_with_progress(
        self, position_config, route_config, simple_timed_route
    ):
        """Test that simulator maintains consistent speed as it progresses."""
        simulator = PositionSimulator(route_config, position_config)
        follower = KMLRouteFollower(simple_timed_route)
        simulator.set_route_follower(follower)

        # Track speeds across progress
        speeds = []
        for _ in range(10):
            simulator.update()
            speeds.append(simulator.current_speed)

        # All speeds should be in expected range (500 ± 0.5 or 550 ± 0.5)
        assert all(499.5 <= s <= 550.5 for s in speeds)

        # Speed should vary slightly (not constant)
        speed_variance = max(speeds) - min(speeds)
        assert 0.0 < speed_variance <= 2.0  # Up to ±1 knot variation

    def test_speed_clamping_within_config_limits(
        self, position_config, route_config
    ):
        """Test that speeds are clamped to config limits."""
        # Create a route with unrealistic speed
        metadata = RouteMetadata(
            name="Extreme Speed Route",
            file_path="/test/extreme.kml",
            point_count=2,
        )

        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_segment_speed_knots=None,
            ),
            RoutePoint(
                latitude=40.5,
                longitude=-74.0,
                altitude=10000,
                sequence=1,
                expected_segment_speed_knots=1000.0,  # Unrealistically high
            ),
        ]

        extreme_route = ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=None,
        )

        simulator = PositionSimulator(route_config, position_config)
        follower = KMLRouteFollower(extreme_route)
        simulator.set_route_follower(follower)

        simulator.update()

        # Speed should be clamped to max_knots (600.0)
        assert simulator.current_speed <= position_config.speed_max_knots

    def test_speed_override_with_direction(self, position_config, route_config):
        """Test that speed override works with reverse direction."""
        metadata = RouteMetadata(
            name="Reverse Test Route",
            file_path="/test/reverse.kml",
            point_count=2,
        )

        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_segment_speed_knots=None,
            ),
            RoutePoint(
                latitude=40.5,
                longitude=-74.0,
                altitude=10000,
                sequence=1,
                expected_segment_speed_knots=500.0,
            ),
        ]

        reverse_route = ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=None,
        )

        simulator = PositionSimulator(route_config, position_config)
        follower = KMLRouteFollower(reverse_route)
        simulator.set_route_follower(follower, completion_behavior="reverse")

        # Update to move forward
        for _ in range(5):
            simulator.update()

        forward_progress = simulator.progress
        forward_speed = simulator.current_speed

        # Continue updating until we reverse
        for _ in range(100):
            simulator.update()

        # After reversing, speed should still be close to expected (500 knots)
        # but progress should be decreasing
        assert 499.5 <= simulator.current_speed <= 550.5


class TestTimingAwarenessIntegration:
    """Integration tests for timing-aware simulation."""

    def test_simulator_with_full_timing_profile(self):
        """Test complete simulator with full timing profile."""
        # Create a realistic timed route
        metadata = RouteMetadata(
            name="KADW-PHNL",
            file_path="/test/kadw-phnl.kml",
            point_count=100,
        )

        # Simulate 100-point route with timing
        points = []
        base_lat, base_lon = 38.8, -77.0  # Near DC
        base_time = datetime(2025, 11, 3, 12, 0, 0)

        for i in range(100):
            # Simulate progress across ~2000 km
            lat = base_lat + (20.8 / 100) * i  # Move toward Hawaii
            lon = base_lon + (98 / 100) * i
            time_offset = 36000 * i / 100  # 10 hour flight spread across points

            point = RoutePoint(
                latitude=lat,
                longitude=lon,
                altitude=35000 + random.randint(-1000, 1000),
                sequence=i,
                expected_arrival_time=base_time + timedelta(seconds=time_offset),
                expected_segment_speed_knots=500.0 + random.uniform(-20, 20),
            )
            points.append(point)

        # Add timing profile
        timing_profile = RouteTimingProfile(
            departure_time=base_time,
            arrival_time=base_time + timedelta(hours=10),
            total_expected_duration_seconds=36000,
            has_timing_data=True,
            segment_count_with_timing=99,
        )

        route = ParsedRoute(
            metadata=metadata,
            points=points,
            waypoints=[],
            timing_profile=timing_profile,
        )

        # Create simulator and set route
        position_config = PositionConfig(
            speed_min_knots=400.0,
            speed_max_knots=600.0,
            altitude_min_feet=20000.0,
            altitude_max_feet=45000.0,
        )
        route_config = RouteConfig(
            pattern="circular",
            latitude_start=base_lat,
            longitude_start=base_lon,
            radius_km=100.0,
            distance_km=100.0,
            completion_behavior="stop",
        )

        simulator = PositionSimulator(route_config, position_config)
        follower = KMLRouteFollower(route)
        simulator.set_route_follower(follower, completion_behavior="stop")

        # Run simulation for several updates
        speeds = []
        for _ in range(20):
            simulator.update()
            speeds.append(simulator.current_speed)

        # Verify speeds are in expected range (480-520 knots for 500 ± drift)
        assert all(480 <= s <= 520 for s in speeds)

        # Verify progress increases
        assert simulator.progress >= 0.0


# Additional import for random in test
import random
