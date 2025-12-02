"""Tests for coordinator speed handling with route timing data."""

import pytest
from datetime import datetime

from app.models.route import (
    RoutePoint,
    RouteMetadata,
    ParsedRoute,
    RouteTimingProfile,
)
from app.models.config import SimulationConfig, PositionConfig, RouteConfig
from app.simulation.coordinator import SimulationCoordinator
from app.simulation.kml_follower import KMLRouteFollower


class TestCoordinatorRouteTiming:
    """Test that coordinator respects route timing data speeds."""

    @pytest.fixture
    def timed_route_coordinator(self) -> tuple[SimulationCoordinator, KMLRouteFollower]:
        """Create a coordinator with a timed route."""
        # Create configuration
        config = SimulationConfig(
            mode="simulation",
            route=RouteConfig(pattern="straight", distance_km=500),
            position=PositionConfig(
                speed_min_knots=0.0,
                speed_max_knots=1000.0,  # Allow 1600 knots
            ),
        )

        # Create coordinator
        coordinator = SimulationCoordinator(config)

        # Create a timed route with expected speeds around 450 knots
        metadata = RouteMetadata(
            name="Korea to Andrews Leg",
            file_path="/test/route.kml",
            point_count=5,
        )

        points = [
            RoutePoint(
                latitude=37.0,
                longitude=127.0,
                altitude=10000,
                sequence=0,
                expected_arrival_time=datetime(2025, 11, 3, 12, 0, 0),
                expected_segment_speed_knots=None,
            ),
            RoutePoint(
                latitude=37.5,
                longitude=126.0,
                altitude=10000,
                sequence=1,
                expected_arrival_time=datetime(2025, 11, 3, 12, 15, 0),
                expected_segment_speed_knots=450.0,  # Actual expected speed
            ),
            RoutePoint(
                latitude=38.0,
                longitude=125.0,
                altitude=10000,
                sequence=2,
                expected_arrival_time=datetime(2025, 11, 3, 12, 30, 0),
                expected_segment_speed_knots=460.0,
            ),
            RoutePoint(
                latitude=38.5,
                longitude=124.0,
                altitude=10000,
                sequence=3,
                expected_arrival_time=datetime(2025, 11, 3, 12, 45, 0),
                expected_segment_speed_knots=440.0,
            ),
            RoutePoint(
                latitude=39.0,
                longitude=123.0,
                altitude=10000,
                sequence=4,
                expected_arrival_time=datetime(2025, 11, 3, 13, 0, 0),
                expected_segment_speed_knots=450.0,
            ),
        ]

        timing_profile = RouteTimingProfile(
            departure_time=datetime(2025, 11, 3, 12, 0, 0),
            arrival_time=datetime(2025, 11, 3, 13, 0, 0),
            total_expected_duration_seconds=3600,
            has_timing_data=True,
            segment_count_with_timing=4,
        )

        route = ParsedRoute(
            metadata=metadata,
            points=points,
            timing_profile=timing_profile,
        )

        follower = KMLRouteFollower(route)
        return coordinator, follower

    def test_coordinator_uses_route_timing_speed_not_gps_calculated(
        self, timed_route_coordinator
    ):
        """Test that coordinator uses route timing speed, not GPS-calculated speed."""
        coordinator, follower = timed_route_coordinator

        # Set the route follower
        coordinator.position_sim.set_route_follower(
            follower, completion_behavior="loop"
        )

        # Generate telemetry several times to accumulate speed history in SpeedTracker
        for _ in range(10):
            telemetry = coordinator.update()

        # The position simulator should be using expected speeds around 440-460 knots
        # NOT the arbitrary 1600 knots from config
        speed = telemetry.position.speed

        # Speed should be close to expected timing speeds (±0.5 knot drift)
        # Allow range of 430-470 to account for drift and variation
        assert 430 <= speed <= 470, (
            f"Speed should be from route timing (~450 knots), "
            f"got {speed} (should NOT be 1600 knots from config)"
        )

    def test_route_without_timing_uses_gps_speed(self):
        """Test that routes without timing data still use GPS-based speed calculation."""
        # Create configuration with a default speed range
        config = SimulationConfig(
            mode="simulation",
            route=RouteConfig(pattern="straight", distance_km=500),
            position=PositionConfig(
                speed_min_knots=0.0,
                speed_max_knots=100.0,
            ),
        )

        coordinator = SimulationCoordinator(config)

        # Create a route WITHOUT timing data
        metadata = RouteMetadata(
            name="Untimed Route",
            file_path="/test/route.kml",
            point_count=3,
        )

        points = [
            RoutePoint(
                latitude=40.0,
                longitude=-74.0,
                altitude=10000,
                sequence=0,
                expected_arrival_time=None,  # No timing
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
            RoutePoint(
                latitude=41.0,
                longitude=-74.0,
                altitude=10000,
                sequence=2,
                expected_arrival_time=None,
                expected_segment_speed_knots=None,
            ),
        ]

        route = ParsedRoute(
            metadata=metadata,
            points=points,
            timing_profile=None,
        )

        follower = KMLRouteFollower(route)
        coordinator.position_sim.set_route_follower(
            follower, completion_behavior="loop"
        )

        # Generate telemetry
        for _ in range(5):
            telemetry = coordinator.update()

        # Without timing data, SpeedTracker should kick in and limit speed to config max
        speed = telemetry.position.speed

        # Should be within the configured range (0-100 knots)
        assert speed <= 100, (
            f"Speed without timing should respect config max (100 knots), "
            f"got {speed}"
        )

    def test_speed_transition_from_timing_to_no_timing(self, timed_route_coordinator):
        """Test speed behavior transitions correctly when timing data is available/unavailable."""
        coordinator, follower = timed_route_coordinator

        # Initially with timing data
        coordinator.position_sim.set_route_follower(
            follower, completion_behavior="loop"
        )

        speeds_with_timing = []
        for _ in range(10):
            telemetry = coordinator.update()
            speeds_with_timing.append(telemetry.position.speed)

        avg_with_timing = sum(speeds_with_timing) / len(speeds_with_timing)

        # Now disable route following
        coordinator.position_sim.set_route_follower(None)

        speeds_without_timing = []
        for _ in range(10):
            telemetry = coordinator.update()
            speeds_without_timing.append(telemetry.position.speed)

        avg_without_timing = sum(speeds_without_timing) / len(speeds_without_timing)

        # With timing data, speed should be around 450 knots
        assert (
            430 <= avg_with_timing <= 470
        ), f"With timing: expected ~450 knots, got {avg_with_timing}"

        # Without timing data, speed can be anything in the default range
        # (This is because SpeedTracker accumulates position changes)
        # Just verify it's not using the 1600 knot config value
        assert (
            avg_without_timing < 200
        ), "Without timing: should use default simulator, not arbitrary 1600 knots"

    def test_route_timing_speeds_override_config_limits(self, timed_route_coordinator):
        """Test that route timing speeds take precedence over config speed limits."""
        coordinator, follower = timed_route_coordinator

        # Set config speed limits LOWER than expected route speeds
        # Route speeds are ~450 knots, config max is 400
        coordinator.config.position.speed_max_knots = 400.0

        coordinator.position_sim.set_route_follower(
            follower, completion_behavior="loop"
        )

        for _ in range(10):
            telemetry = coordinator.update()

        # Route timing data (~450 knots) should NOT be clamped by config max (400)
        # The route's expected speeds take precedence
        speed = telemetry.position.speed
        assert (
            speed > 400
        ), f"Route timing speed (~450 knots) should override config limit (400), got {speed}"
