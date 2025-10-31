"""Position simulator for realistic movement along a route."""

import random
import time
from datetime import datetime
from typing import Tuple

from app.models.config import PositionConfig, RouteConfig
from app.models.telemetry import PositionData
from app.services.heading_tracker import HeadingTracker
from app.simulation.route import create_route


class PositionSimulator:
    """Simulator for position data along a predefined route."""

    def __init__(
        self,
        route_config: RouteConfig,
        position_config: PositionConfig
    ):
        """
        Initialize position simulator.

        Args:
            route_config: Route configuration
            position_config: Position simulation parameters
        """
        self.route_config = route_config
        self.position_config = position_config

        # Create route
        self.route = create_route(
            pattern=route_config.pattern,
            latitude_start=route_config.latitude_start,
            longitude_start=route_config.longitude_start,
            radius_km=route_config.radius_km,
            distance_km=route_config.distance_km
        )

        # Initialize state
        self.progress = 0.0  # 0.0 to 1.0 along route
        self.current_speed = 300.0  # knots
        self.current_altitude = (
            position_config.altitude_min_feet +
            position_config.altitude_max_feet
        ) / 2.0

        # Time tracking for accurate delta calculation
        self.last_update_time = time.time()

        # Initialize heading tracker (simulates live mode behavior)
        self.heading_tracker = HeadingTracker(
            min_distance_meters=5.0,   # Lower threshold for simulation
            max_age_seconds=30.0
        )

    def update(self) -> PositionData:
        """
        Update position simulator and return current position.

        Returns:
            PositionData with current coordinates and movement info
        """
        # Update progress (speed-based movement)
        # Convert knots to km/h: 1 knot = 1.852 km/h
        # Then to km per update: distance = speed * time_interval
        # Assuming 1 second update interval
        self._update_progress()

        # Update altitude with slight variation
        self._update_altitude()

        # Get position from route
        lat, lon, route_heading = self.route.get_segment(self.progress)

        # Calculate heading from movement using HeadingTracker
        # This simulates how heading will be calculated in live mode!
        calculated_heading = self.heading_tracker.update(
            latitude=lat,
            longitude=lon,
            timestamp=datetime.now()
        )

        return PositionData(
            latitude=lat,
            longitude=lon,
            altitude=self.current_altitude,
            speed=self.current_speed,
            heading=calculated_heading  # ✅ Using movement-based heading calculation!
        )

    def _update_progress(self) -> None:
        """Update progress along the route based on current speed."""
        # Calculate actual time delta since last update
        current_time = time.time()
        time_delta_seconds = current_time - self.last_update_time
        self.last_update_time = current_time

        # Update speed with some randomness
        self._update_speed()

        # Convert speed (knots) to distance per second
        # 1 knot = 1.852 km/h = 1.852 / 3600 km/s = 0.000514 km/s
        km_per_second = self.current_speed * 1.852 / 3600.0

        # Calculate actual distance traveled based on time delta
        km_traveled = km_per_second * time_delta_seconds

        # Estimate route circumference/length for progress calculation
        # For circular route: 2 * pi * radius
        # For straight route: total distance
        if hasattr(self.route, 'radius_km'):
            # Circular route
            route_length_km = 2 * 3.14159 * self.route.radius_km
        else:
            # Straight route
            route_length_km = self.route.distance_km

        # Update progress based on actual distance traveled
        self.progress += km_traveled / route_length_km

    def _update_speed(self) -> None:
        """Update speed with realistic acceleration/deceleration."""
        config = self.position_config

        # For Starlink terminal movement simulation:
        # Use a stable cruising speed with very small variations
        # This simulates realistic aircraft movement where speed is relatively constant

        # If first update or speed is zero, pick a cruising speed
        if self.current_speed < 1.0:
            # Choose a realistic cruising speed (e.g., 45-75 knots for typical aircraft)
            self.current_speed = random.uniform(300.0, 350.0)
        else:
            # Very small drift (±0.2 knots per update)
            # This is 100x smoother than the original ±1.0 knot changes
            speed_change = random.uniform(-0.2, 0.2)
            self.current_speed += speed_change

            # Occasionally simulate minor speed adjustments (1% chance per update)
            if random.random() < 0.01:
                # Small adjustment: ±2 knots
                speed_change = random.uniform(-2.0, 2.0)
                self.current_speed += speed_change

        # Clamp to valid range
        self.current_speed = max(
            config.speed_min_knots,
            min(config.speed_max_knots, self.current_speed)
        )

    def _update_altitude(self) -> None:
        """Update altitude with slight variation."""
        config = self.position_config

        # Small random variation in altitude (in feet)
        altitude_change = random.uniform(-328.0, 328.0)
        self.current_altitude += altitude_change

        # Clamp to valid range
        self.current_altitude = max(
            config.altitude_min_feet,
            min(config.altitude_max_feet, self.current_altitude)
        )

    def set_progress(self, progress: float) -> None:
        """
        Set progress along the route (0.0 to 1.0).

        Args:
            progress: Progress value (will be wrapped to 0-1 range)
        """
        self.progress = progress % 1.0

    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.progress = 0.0
        self.current_speed = 0.0
        self.current_altitude = (
            self.position_config.altitude_min_feet +
            self.position_config.altitude_max_feet
        ) / 2.0
        self.last_update_time = time.time()
        self.heading_tracker.reset()
