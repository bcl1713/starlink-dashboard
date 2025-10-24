"""Heading tracker for calculating heading from GPS position updates."""

from typing import Optional, Tuple
from datetime import datetime, timedelta

from app.simulation.route import calculate_bearing


class HeadingTracker:
    """
    Track position updates and calculate heading from movement.

    This is used in LIVE mode to calculate heading from real GPS data,
    since the Starlink API may not provide heading directly.
    """

    def __init__(self, min_distance_meters: float = 10.0, max_age_seconds: float = 30.0):
        """
        Initialize heading tracker.

        Args:
            min_distance_meters: Minimum distance between points to calculate heading
                                (prevents jitter when stationary)
            max_age_seconds: Maximum age of previous position before discarding
        """
        self.min_distance_meters = min_distance_meters
        self.max_age_seconds = max_age_seconds

        self._previous_position: Optional[Tuple[float, float, datetime]] = None
        self._last_heading: float = 0.0

    def update(
        self,
        latitude: float,
        longitude: float,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Update with new position and calculate heading.

        Args:
            latitude: Current latitude in decimal degrees
            longitude: Current longitude in decimal degrees
            timestamp: Timestamp of position (defaults to now)

        Returns:
            Heading in degrees (0-360, 0=North, 90=East, 180=South, 270=West)
            If stationary or insufficient data, returns last known heading.
        """
        if timestamp is None:
            timestamp = datetime.now()

        # First position - no heading yet
        if self._previous_position is None:
            self._previous_position = (latitude, longitude, timestamp)
            return self._last_heading

        prev_lat, prev_lon, prev_time = self._previous_position

        # Check if previous position is too old
        if (timestamp - prev_time).total_seconds() > self.max_age_seconds:
            # Reset tracking with current position
            self._previous_position = (latitude, longitude, timestamp)
            return self._last_heading

        # Calculate distance moved (rough approximation in meters)
        distance = self._calculate_distance(prev_lat, prev_lon, latitude, longitude)

        # If moved enough, calculate new heading
        if distance >= self.min_distance_meters:
            heading = calculate_bearing(prev_lat, prev_lon, latitude, longitude)
            self._last_heading = heading
            self._previous_position = (latitude, longitude, timestamp)
            return heading

        # Not enough movement - return last heading
        return self._last_heading

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate approximate distance between two points in meters.

        Uses the haversine formula for great-circle distance.

        Args:
            lat1: First latitude
            lon1: First longitude
            lat2: Second latitude
            lon2: Second longitude

        Returns:
            Distance in meters
        """
        import math

        # Earth radius in meters
        R = 6371000.0

        # Convert to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (math.sin(dlat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def reset(self) -> None:
        """Reset tracker state."""
        self._previous_position = None
        self._last_heading = 0.0

    def get_last_heading(self) -> float:
        """Get the last calculated heading."""
        return self._last_heading
