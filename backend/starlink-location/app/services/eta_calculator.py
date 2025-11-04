"""ETA and distance calculation service with speed smoothing."""

import logging
import math
import time
from collections import deque
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from app.models.poi import POI

if TYPE_CHECKING:
    from app.models.route import ParsedRoute

logger = logging.getLogger(__name__)


class ETACalculator:
    """
    Calculate ETA and distance to POIs with speed smoothing.

    Features:
    - Exponential moving average for speed smoothing
    - Haversine formula for great-circle distance
    - Support for custom speed update intervals
    - Tracking of passed POIs
    """

    def __init__(self, smoothing_duration_seconds: float = 120.0, default_speed_knots: float = 150.0):
        """
        Initialize ETA calculator.

        Args:
            smoothing_duration_seconds: Duration of time-based smoothing window in seconds (default: 120s = 2 min)
            default_speed_knots: Default speed to use when no speed data available
        """
        self.smoothing_duration_seconds = smoothing_duration_seconds
        self.default_speed_knots = default_speed_knots
        self.earth_radius_m = 6371000.0  # Earth's radius in meters

        # Speed smoothing using time-based rolling window
        # Store tuples of (speed, timestamp) to enable time-based windowing
        self._speed_history: deque[tuple[float, float]] = deque()  # (speed_knots, timestamp)
        self._smoothed_speed: float = default_speed_knots
        self._last_update_time: Optional[datetime] = None

        # POI tracking
        self._passed_pois: set[str] = set()  # Track POI IDs that have been passed
        self._poi_distance_threshold_m = 100.0  # 100m threshold for "passed"

    def update_speed(self, current_speed_knots: float) -> None:
        """
        Update current speed and recalculate smoothed speed.

        Uses time-based rolling window average for speed smoothing.
        Only considers samples within the smoothing window duration.

        Args:
            current_speed_knots: Current speed in knots
        """
        current_time = time.time()
        self._speed_history.append((current_speed_knots, current_time))

        # Remove samples older than smoothing window
        cutoff_time = current_time - self.smoothing_duration_seconds
        while self._speed_history and self._speed_history[0][1] < cutoff_time:
            self._speed_history.popleft()

        # Calculate average of samples within window
        if len(self._speed_history) > 0:
            self._smoothed_speed = sum(speed for speed, _ in self._speed_history) / len(self._speed_history)
        else:
            self._smoothed_speed = self.default_speed_knots

        self._last_update_time = datetime.utcnow()

        logger.debug(
            f"Speed updated: raw={current_speed_knots:.1f}kn, smoothed={self._smoothed_speed:.1f}kn, samples={len(self._speed_history)}"
        )

    def get_smoothed_speed(self) -> float:
        """
        Get current smoothed speed.

        Returns:
            Smoothed speed in knots
        """
        return self._smoothed_speed

    def calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate great-circle distance between two points using Haversine formula.

        Args:
            lat1: Starting latitude in degrees
            lon1: Starting longitude in degrees
            lat2: Ending latitude in degrees
            lon2: Ending longitude in degrees

        Returns:
            Distance in meters
        """
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return self.earth_radius_m * c

    def calculate_eta(self, distance_meters: float, speed_knots: Optional[float] = None) -> float:
        """
        Calculate estimated time to arrival (ETA) for a given distance and speed.

        Args:
            distance_meters: Distance in meters
            speed_knots: Speed in knots (uses smoothed speed if not provided)

        Returns:
            ETA in seconds (negative for passed POIs, -1 for zero/no speed)
        """
        speed = speed_knots if speed_knots is not None else self._smoothed_speed

        # Handle zero or very small speed (below 0.5 knots is effectively stationary)
        # This prevents division by near-zero values and extreme ETA estimates
        # At less than 0.5 knots, meaningful ETA predictions are unreliable
        if speed < 0.5:
            return -1.0

        # Convert distance to nautical miles
        nautical_miles = distance_meters / 1852.0  # 1 nautical mile = 1852 meters

        # Calculate time in hours
        time_hours = nautical_miles / speed

        # Convert to seconds
        eta_seconds = time_hours * 3600.0

        return eta_seconds

    def calculate_poi_metrics(
        self,
        current_lat: float,
        current_lon: float,
        pois: list[POI],
        speed_knots: Optional[float] = None,
        active_route: Optional["ParsedRoute"] = None,
    ) -> dict[str, dict]:
        """
        Calculate distance and ETA metrics for all POIs.

        When an active route with timing data is provided, POIs that are waypoints
        on that route will use route-aware ETA calculations (segment-based speeds).
        POIs not on the active route fall back to distance/speed calculation.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            pois: List of POI objects
            speed_knots: Current speed in knots (uses smoothed speed if not provided)
            active_route: Optional ParsedRoute with timing data for route-aware calculations

        Returns:
            Dictionary mapping POI ID to dict with 'eta', 'distance', and 'passed' keys
        """
        metrics = {}

        for poi in pois:
            distance = self.calculate_distance(current_lat, current_lon, poi.latitude, poi.longitude)

            # Try route-aware ETA calculation if active route available
            eta = None
            if active_route and poi.route_id and poi.route_id == active_route.metadata.file_path:
                eta = self._calculate_route_aware_eta(
                    current_lat, current_lon, poi, active_route
                )

            # Fall back to distance/speed calculation if route-aware failed
            if eta is None:
                eta = self.calculate_eta(distance, speed_knots)

            # Determine if POI has been passed
            passed = distance < self._poi_distance_threshold_m

            # Track passed POIs
            if passed and poi.id not in self._passed_pois:
                self._passed_pois.add(poi.id)
                logger.info(f"POI passed: {poi.name} (ID: {poi.id})")

            metrics[poi.id] = {
                "poi_name": poi.name,
                "poi_category": poi.category or "",  # Use empty string for null categories
                "distance_meters": distance,
                "eta_seconds": eta,
                "passed": passed,
            }

        return metrics

    def _calculate_route_aware_eta(
        self,
        current_lat: float,
        current_lon: float,
        poi: POI,
        active_route: "ParsedRoute",
    ) -> Optional[float]:
        """
        Calculate ETA using route timing data if POI is a waypoint on the active route.

        This method implements the route-aware ETA logic: if the POI name matches a waypoint
        on the active route with timing data, we use the route's expected arrival time for
        that waypoint minus the expected arrival time at the nearest current point.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            poi: POI object whose name should match a waypoint name
            active_route: ParsedRoute with timing data

        Returns:
            ETA in seconds if route-aware calculation succeeds, None to fall back to distance/speed
        """
        # Early return if no timing data on route
        if not active_route.timing_profile or not active_route.timing_profile.has_timing_data:
            return None

        # Try to find matching waypoint on route by name
        matching_waypoint = None
        for waypoint in active_route.waypoints:
            if waypoint.name.upper() == poi.name.upper():
                matching_waypoint = waypoint
                break

        if not matching_waypoint or not matching_waypoint.expected_arrival_time:
            return None

        try:
            # Find nearest route point to current position that has timing data
            nearest_point_with_timing = None
            nearest_distance = float('inf')

            for point in active_route.points:
                if point.expected_arrival_time:
                    dist = self.calculate_distance(current_lat, current_lon, point.latitude, point.longitude)
                    if dist < nearest_distance:
                        nearest_distance = dist
                        nearest_point_with_timing = point

            if not nearest_point_with_timing:
                return None

            # Calculate ETA as the difference between destination arrival time and current point arrival time
            time_to_destination = (matching_waypoint.expected_arrival_time - nearest_point_with_timing.expected_arrival_time).total_seconds()

            # If time_to_destination is negative, we've already passed this waypoint
            if time_to_destination <= 0:
                return None

            return time_to_destination

        except Exception as e:
            logger.debug(f"Route-aware ETA calculation failed for {poi.name}: {e}")
            return None

    def reset(self) -> None:
        """Reset calculator state."""
        self._speed_history.clear()
        self._smoothed_speed = self.default_speed_knots
        self._passed_pois.clear()
        self._last_update_time = None
        logger.info(f"ETA calculator reset (smoothing window: {self.smoothing_duration_seconds}s)")

    def get_passed_pois(self) -> set[str]:
        """
        Get set of POI IDs that have been passed.

        Returns:
            Set of passed POI IDs
        """
        return self._passed_pois.copy()

    def clear_passed_pois(self) -> None:
        """Clear the set of passed POIs (useful when route resets)."""
        self._passed_pois.clear()
        logger.info("Cleared passed POIs tracking")

    def get_stats(self) -> dict:
        """
        Get calculator statistics.

        Returns:
            Dictionary with current stats
        """
        # Calculate window coverage (time from oldest to newest sample)
        window_coverage_seconds = 0.0
        if len(self._speed_history) > 1:
            oldest_time = self._speed_history[0][1]
            newest_time = self._speed_history[-1][1]
            window_coverage_seconds = newest_time - oldest_time

        return {
            "smoothed_speed_knots": self._smoothed_speed,
            "speed_samples": len(self._speed_history),
            "smoothing_window_seconds": self.smoothing_duration_seconds,
            "current_window_coverage_seconds": window_coverage_seconds,
            "passed_pois_count": len(self._passed_pois),
            "last_update": self._last_update_time.isoformat() if self._last_update_time else None,
        }
