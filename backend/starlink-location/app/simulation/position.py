"""Position simulator for realistic movement along a route."""

# FR-004: File exceeds 300 lines (365 lines) because position simulation
# coordinates route following, telemetry generation, noise/jitter injection, and
# speed calculation. Splitting would fragment the simulation pipeline.
# Deferred to v0.4.0.

import logging
import math
import random
import time
from datetime import datetime
from typing import Optional

from app.models.config import PositionConfig, RouteConfig
from app.models.telemetry import PositionData
from app.services.heading_tracker import HeadingTracker
from app.simulation.route import create_route

logger = logging.getLogger(__name__)


class PositionSimulator:
    """Simulator for position data along a predefined route."""

    # Class constant for reverse mode boundary adjustment
    # Used to prevent immediate re-triggering of boundary conditions (progress >= 1.0 or <= 0.0)
    # when reversing direction at route endpoints
    _PROGRESS_EPSILON = 0.01

    def __init__(self, route_config: RouteConfig, position_config: PositionConfig):
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
            distance_km=route_config.distance_km,
        )

        # Initialize state
        self.progress = 0.0  # 0.0 to 1.0 along route
        self.current_speed = 0.0  # knots
        self.current_altitude = (
            position_config.altitude_min_feet + position_config.altitude_max_feet
        ) / 2.0

        # Time tracking for accurate delta calculation
        # Initialize to 1 second in the past so first update has a reasonable time delta
        self.last_update_time = time.time() - 1.0

        # Initialize heading tracker (simulates live mode behavior)
        self.heading_tracker = HeadingTracker(
            min_distance_meters=5.0,  # Lower threshold for simulation
            max_age_seconds=30.0,
        )

        # Route following support (Phase 5 feature)
        self.route_follower = None
        self.route_completion_behavior = "loop"  # loop, stop, or reverse
        self._previous_route_name = None  # Track route changes
        self._route_direction = 1  # 1 = forward, -1 = backward (for reverse mode)
        self._movement_stopped = (
            False  # Flag to explicitly stop movement at route end (for 'stop' mode)
        )

    def update(self) -> PositionData:
        """
        Update position simulator and return current position.

        Returns:
            PositionData with current coordinates and movement info
        """
        # Check if we should follow a KML route
        if self.route_follower:
            return self._update_with_route_following()
        else:
            return self._update_with_default_route()

    def _update_with_route_following(self) -> PositionData:
        """
        Update position by following a KML route.

        Returns:
            PositionData following the KML route
        """
        # Update progress (speed-based movement, respecting direction)
        self._update_progress_with_direction()

        # Get position from KML route follower
        position_dict = self.route_follower.get_position(self.progress)

        # Extract position data
        lat = position_dict["latitude"]
        lon = position_dict["longitude"]
        alt = (
            position_dict["altitude"] or self.current_altitude
        )  # Fallback if no altitude
        heading = position_dict["heading"]

        # Adjust heading if moving backward
        if self._route_direction == -1:
            heading = (heading + 180) % 360

        # Handle route completion behavior
        if self.progress >= 1.0:
            # Route end reached
            if self.route_completion_behavior == "loop":
                logger.info(
                    f"Route loop completed, restarting: {self.route_follower.get_route_name()}"
                )
                self.progress = 0.0
                self._route_direction = 1
                self._movement_stopped = False
            elif self.route_completion_behavior == "stop":
                logger.info(
                    f"Route completed, stopping: {self.route_follower.get_route_name()}"
                )
                self.progress = 1.0  # Clamp to end
                self._movement_stopped = True
            elif self.route_completion_behavior == "reverse":
                logger.info(
                    f"Route end reached, reversing direction: {self.route_follower.get_route_name()}"
                )
                self._route_direction = -1
                self._movement_stopped = False
                # Adjust progress slightly to avoid immediately hitting 0.0
                self.progress = 1.0 - self._PROGRESS_EPSILON
        elif self.progress <= 0.0 and self.route_completion_behavior == "reverse":
            # Route start reached (only relevant for reverse mode)
            logger.info(
                f"Route start reached, reversing direction: {self.route_follower.get_route_name()}"
            )
            self._route_direction = 1
            self._movement_stopped = False
            # Adjust progress slightly to avoid immediately hitting 1.0
            self.progress = 0.0 + self._PROGRESS_EPSILON

        return PositionData(
            latitude=lat,
            longitude=lon,
            altitude=alt,
            speed=self.current_speed,
            heading=heading,  # Use calculated heading from route (adjusted for direction)
        )

    def _update_with_default_route(self) -> PositionData:
        """
        Update position using default simulated route (original behavior).

        Returns:
            PositionData with default simulated movement
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
            latitude=lat, longitude=lon, timestamp=datetime.now()
        )

        return PositionData(
            latitude=lat,
            longitude=lon,
            altitude=self.current_altitude,
            speed=self.current_speed,
            heading=calculated_heading,  # ✅ Using movement-based heading calculation!
        )

    def _update_progress(self) -> None:
        """Update progress along the route based on current speed.

        Delegates to the generic progress update method with default parameters.
        """
        self._update_progress_generic(direction=1, use_route_length=False)

    def _update_progress_with_direction(self) -> None:
        """Update progress along the route based on current speed and direction.

        For route following with reverse completion behavior support.
        Delegates to the generic progress update method with route-aware parameters.
        """
        # If movement is stopped (e.g., in 'stop' completion behavior), do nothing
        if self._movement_stopped:
            return

        self._update_progress_generic(
            direction=self._route_direction, use_route_length=True
        )

    def _update_progress_generic(
        self, direction: int = 1, use_route_length: bool = False
    ) -> None:
        """Generic method to update progress with configurable behavior.

        Eliminates code duplication between default and route-following updates.

        Args:
            direction: Direction multiplier (1 for forward, -1 for backward)
            use_route_length: If True, use KML route length; if False, use default route calculation
        """
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

        # Determine route length based on context
        if use_route_length and self.route_follower:
            # Using KML route: get total distance
            route_length_km = (
                self.route_follower.get_total_distance() / 1000.0
            )  # Convert meters to km
        else:
            # Using default route: estimate circumference/length for progress calculation
            # For circular route: 2 * pi * radius
            # For straight route: total distance
            if hasattr(self.route, "radius_km"):
                # Circular route
                route_length_km = 2 * math.pi * self.route.radius_km
            else:
                # Straight route
                route_length_km = self.route.distance_km

        # Update progress based on actual distance traveled and direction
        self.progress += direction * km_traveled / route_length_km

    def _update_speed(self) -> None:
        """
        Update speed with realistic acceleration/deceleration.

        Phase 5 Enhancement: Respects expected segment speeds from timing data.
        If the route has timing information, uses the expected speed instead of
        generating a random cruising speed.
        """
        config = self.position_config

        # Phase 5: Check if we're following a route with timing data
        if self.route_follower:
            expected_speed = self.route_follower.get_segment_speed_at_progress(
                self.progress
            )
            if expected_speed is not None:
                # Route has timing data - use expected speed from route
                # Add small drift (±0.5 knots) to simulate realistic variations
                # while still staying close to expected speed
                speed_change = random.uniform(-0.5, 0.5)
                self.current_speed = expected_speed + speed_change

                # Do NOT clamp to config speed range when using route timing data
                # The route's expected speeds take precedence over generic config defaults
                # Config speed range is only for non-timed routes
                return

        # For Starlink terminal movement simulation:
        # Use a stable cruising speed with very small variations
        # This simulates realistic aircraft movement where speed is relatively constant

        # If first update or speed is zero, pick a cruising speed
        if self.current_speed < 1.0:
            # Choose a realistic cruising speed (e.g., 45-75 knots for typical aircraft)
            self.current_speed = random.uniform(45.0, 75.0)
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
            config.speed_min_knots, min(config.speed_max_knots, self.current_speed)
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
            min(config.altitude_max_feet, self.current_altitude),
        )

    def set_progress(self, progress: float) -> None:
        """
        Set progress along the route (0.0 to 1.0).

        Args:
            progress: Progress value (will be wrapped to 0-1 range)
        """
        self.progress = progress % 1.0

    def set_route_follower(
        self, follower: Optional["KMLRouteFollower"], completion_behavior: str = "loop"
    ) -> None:
        """
        Set a KML route follower for this simulator.

        Args:
            follower: KMLRouteFollower instance or None to disable
            completion_behavior: How to handle route completion ("loop", "stop", or "reverse")
        """
        if follower is None:
            logger.info("Route following disabled")
            self.route_follower = None
            self._movement_stopped = False
        else:
            logger.info(
                f"Route following enabled for: {follower.get_route_name()}, "
                f"completion_behavior: {completion_behavior}"
            )
            self.route_follower = follower
            self.route_completion_behavior = completion_behavior
            self.progress = 0.0  # Reset progress when new route set
            self._route_direction = 1  # Reset direction to forward
            self._movement_stopped = False  # Reset movement state for new route
            self._previous_route_name = follower.get_route_name()

    def reset(self) -> None:
        """Reset simulator to initial state."""
        self.progress = 0.0
        self.current_speed = 0.0
        self.current_altitude = (
            self.position_config.altitude_min_feet
            + self.position_config.altitude_max_feet
        ) / 2.0
        self.last_update_time = time.time()
        self.heading_tracker.reset()
        self._route_direction = 1  # Reset direction to forward
        if self.route_follower:
            self.route_follower.reset()
