"""Position simulator for realistic movement along a route."""

import random
from typing import Tuple

from app.models.config import PositionConfig, RouteConfig
from app.models.telemetry import PositionData
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
        self.current_speed = 0.0  # knots
        self.current_heading = 0.0  # degrees
        self.current_altitude = (
            position_config.altitude_min_meters +
            position_config.altitude_max_meters
        ) / 2.0

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

        # Update heading with slight variation
        self._update_heading()

        # Update altitude with slight variation
        self._update_altitude()

        # Get position from route
        lat, lon, route_heading = self.route.get_segment(self.progress)

        return PositionData(
            latitude=lat,
            longitude=lon,
            altitude=self.current_altitude,
            speed=self.current_speed,
            heading=self.current_heading
        )

    def _update_progress(self) -> None:
        """Update progress along the route based on current speed."""
        # Update speed with some randomness
        self._update_speed()

        # Convert speed (knots) to distance per second
        # 1 knot = 1.852 km/h = 1.852 / 3600 km/s = 0.000514 km/s
        km_per_second = self.current_speed * 1.852 / 3600.0

        # Estimate route circumference/length for progress calculation
        # For circular route: 2 * pi * radius
        # For straight route: total distance
        if hasattr(self.route, 'radius_km'):
            # Circular route
            route_length_km = 2 * 3.14159 * self.route.radius_km
        else:
            # Straight route
            route_length_km = self.route.distance_km

        # Update progress (1 second per update)
        self.progress += km_per_second / route_length_km

    def _update_speed(self) -> None:
        """Update speed with realistic acceleration/deceleration."""
        config = self.position_config

        # Random walk for speed (tends to stay similar but drifts)
        speed_change = random.uniform(-1.0, 1.0)  # knots per update
        self.current_speed += speed_change

        # Clamp to valid range
        self.current_speed = max(
            config.speed_min_knots,
            min(config.speed_max_knots, self.current_speed)
        )

    def _update_heading(self) -> None:
        """Update heading with variation."""
        config = self.position_config

        # Smooth heading changes
        heading_change = random.uniform(
            -config.heading_variation_rate,
            config.heading_variation_rate
        )
        self.current_heading = (self.current_heading + heading_change) % 360.0

    def _update_altitude(self) -> None:
        """Update altitude with slight variation."""
        config = self.position_config

        # Small random variation in altitude
        altitude_change = random.uniform(-100.0, 100.0)
        self.current_altitude += altitude_change

        # Clamp to valid range
        self.current_altitude = max(
            config.altitude_min_meters,
            min(config.altitude_max_meters, self.current_altitude)
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
        self.current_heading = 0.0
        self.current_altitude = (
            self.position_config.altitude_min_meters +
            self.position_config.altitude_max_meters
        ) / 2.0
