"""ETA and distance calculation service with speed smoothing."""

import logging
import math
from collections import deque
from datetime import datetime
from typing import Optional

from app.models.poi import POI

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

    def __init__(self, window_size: int = 5, default_speed_knots: float = 150.0):
        """
        Initialize ETA calculator.

        Args:
            window_size: Number of samples for moving average (PRD requires 5x update interval)
            default_speed_knots: Default speed to use when no speed data available
        """
        self.window_size = window_size
        self.default_speed_knots = default_speed_knots
        self.earth_radius_m = 6371000.0  # Earth's radius in meters

        # Speed smoothing using rolling window
        self._speed_history: deque[float] = deque(maxlen=window_size)
        self._smoothed_speed: float = default_speed_knots
        self._last_update_time: Optional[datetime] = None

        # POI tracking
        self._passed_pois: set[str] = set()  # Track POI IDs that have been passed
        self._poi_distance_threshold_m = 100.0  # 100m threshold for "passed"

    def update_speed(self, current_speed_knots: float) -> None:
        """
        Update current speed and recalculate smoothed speed.

        Uses rolling window average for speed smoothing.

        Args:
            current_speed_knots: Current speed in knots
        """
        self._speed_history.append(current_speed_knots)

        # Calculate rolling average
        if len(self._speed_history) > 0:
            self._smoothed_speed = sum(self._speed_history) / len(self._speed_history)
        else:
            self._smoothed_speed = self.default_speed_knots

        self._last_update_time = datetime.utcnow()

        logger.debug(
            f"Speed updated: raw={current_speed_knots:.1f}kn, smoothed={self._smoothed_speed:.1f}kn"
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

        # Handle zero or no speed
        if speed <= 0:
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
    ) -> dict[str, dict]:
        """
        Calculate distance and ETA metrics for all POIs.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude
            pois: List of POI objects
            speed_knots: Current speed in knots (uses smoothed speed if not provided)

        Returns:
            Dictionary mapping POI ID to dict with 'eta', 'distance', and 'passed' keys
        """
        metrics = {}

        for poi in pois:
            distance = self.calculate_distance(current_lat, current_lon, poi.latitude, poi.longitude)
            eta = self.calculate_eta(distance, speed_knots)

            # Determine if POI has been passed
            passed = distance < self._poi_distance_threshold_m

            # Track passed POIs
            if passed and poi.id not in self._passed_pois:
                self._passed_pois.add(poi.id)
                logger.info(f"POI passed: {poi.name} (ID: {poi.id})")

            metrics[poi.id] = {
                "poi_name": poi.name,
                "distance_meters": distance,
                "eta_seconds": eta,
                "passed": passed,
            }

        return metrics

    def reset(self) -> None:
        """Reset calculator state."""
        self._speed_history.clear()
        self._smoothed_speed = self.default_speed_knots
        self._passed_pois.clear()
        self._last_update_time = None
        logger.info("ETA calculator reset")

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
        return {
            "smoothed_speed_knots": self._smoothed_speed,
            "speed_samples": len(self._speed_history),
            "passed_pois_count": len(self._passed_pois),
            "last_update": self._last_update_time.isoformat() if self._last_update_time else None,
        }
