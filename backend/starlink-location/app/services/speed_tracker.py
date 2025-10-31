"""Speed tracker for calculating speed from GPS position updates."""

import logging
import math
import time
from collections import deque
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SpeedTracker:
    """
    Track position updates and calculate speed from GPS movement.

    This is used in LIVE mode to calculate speed from real GPS data,
    since the Starlink API does not provide speed directly.

    Uses a time-based rolling window to smooth speed calculations over
    a configurable duration (default: 120 seconds = 2 minutes).
    """

    def __init__(self, smoothing_duration_seconds: float = 120.0, min_distance_meters: float = 10.0):
        """
        Initialize speed tracker.

        Args:
            smoothing_duration_seconds: Duration of smoothing window in seconds (default: 120s)
            min_distance_meters: Minimum distance to consider for speed calculation
                                (prevents jitter when stationary)
        """
        self.smoothing_duration_seconds = smoothing_duration_seconds
        self.min_distance_meters = min_distance_meters

        # Store position updates: (latitude, longitude, timestamp)
        self._position_history: deque[Tuple[float, float, float]] = deque()
        self._last_speed: float = 0.0

    def update(
        self,
        latitude: float,
        longitude: float,
        timestamp: Optional[float] = None
    ) -> float:
        """
        Update with new position and calculate speed.

        Args:
            latitude: Current latitude in decimal degrees
            longitude: Current longitude in decimal degrees
            timestamp: Timestamp of position (defaults to time.time())

        Returns:
            Speed in knots, smoothed over the configured window duration.
            Returns 0.0 if insufficient data or stationary.
        """
        if timestamp is None:
            timestamp = time.time()

        # Add current position to history
        self._position_history.append((latitude, longitude, timestamp))

        # Remove positions older than smoothing window
        cutoff_time = timestamp - self.smoothing_duration_seconds
        while self._position_history and self._position_history[0][2] < cutoff_time:
            self._position_history.popleft()

        # Calculate speed from oldest to newest position in window
        if len(self._position_history) < 2:
            # Not enough data for speed calculation
            return self._last_speed

        oldest_lat, oldest_lon, oldest_time = self._position_history[0]
        newest_lat, newest_lon, newest_time = self._position_history[-1]

        # Calculate distance and time delta
        distance_meters = self._calculate_distance(oldest_lat, oldest_lon, newest_lat, newest_lon)
        time_delta_seconds = newest_time - oldest_time

        # Avoid division by zero and very small time deltas
        if time_delta_seconds < 0.1:
            return self._last_speed

        # Calculate speed: distance / time -> knots
        # 1 knot = 1 nautical mile / hour = 1852 meters / 3600 seconds
        speed_knots = (distance_meters / time_delta_seconds) / 1852.0 * 3600.0

        # Require minimum distance to avoid noise
        if distance_meters >= self.min_distance_meters:
            self._last_speed = speed_knots
            logger.debug(
                f"Speed calculated: {speed_knots:.2f}kn "
                f"({distance_meters:.1f}m in {time_delta_seconds:.1f}s, "
                f"window: {len(self._position_history)} samples)"
            )
        else:
            # Not enough movement - return last speed
            logger.debug(
                f"Distance {distance_meters:.1f}m < threshold {self.min_distance_meters}m, "
                f"returning last speed {self._last_speed:.2f}kn"
            )

        return self._last_speed

    def _calculate_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float
    ) -> float:
        """
        Calculate great-circle distance between two points in meters using Haversine formula.

        Args:
            lat1: First latitude in decimal degrees
            lon1: First longitude in decimal degrees
            lat2: Second latitude in decimal degrees
            lon2: Second longitude in decimal degrees

        Returns:
            Distance in meters
        """
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
        self._position_history.clear()
        self._last_speed = 0.0
        logger.info("Speed tracker reset")

    def get_last_speed(self) -> float:
        """Get the last calculated speed in knots."""
        return self._last_speed

    def get_stats(self) -> dict:
        """
        Get tracker statistics.

        Returns:
            Dictionary with current stats
        """
        window_coverage_seconds = 0.0
        if len(self._position_history) > 1:
            oldest_time = self._position_history[0][2]
            newest_time = self._position_history[-1][2]
            window_coverage_seconds = newest_time - oldest_time

        return {
            "speed_knots": self._last_speed,
            "position_samples": len(self._position_history),
            "smoothing_window_seconds": self.smoothing_duration_seconds,
            "current_window_coverage_seconds": window_coverage_seconds,
        }
