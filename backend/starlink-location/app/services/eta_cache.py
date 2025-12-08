"""ETA calculation caching service for improved performance."""

import time
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone

from app.core.logging import get_logger

logger = get_logger(__name__)


class ETACache:
    """
    Cache for ETA calculations to avoid redundant distance/speed computations.

    Stores cached ETA results with TTL (time-to-live) to ensure freshness.
    Significantly speeds up dashboard and metric updates.
    """

    def __init__(self, ttl_seconds: float = 5.0):
        """
        Initialize the ETA cache.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
        """
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[any, float]] = {}

    def _make_key(
        self,
        route_id: str,
        target_lat: float,
        target_lon: float,
        current_lat: float,
        current_lon: float,
        current_speed: float,
    ) -> str:
        """
        Create a cache key from ETA calculation parameters.

        Precision: rounds to 2 decimal places for coordinates to allow
        slight position changes without cache misses.
        """
        # Round to 2 decimal places for cache key (~1.1 km precision)
        return (
            f"{route_id}:"
            f"{round(target_lat, 2)},"
            f"{round(target_lon, 2)}:"
            f"{round(current_lat, 2)},"
            f"{round(current_lon, 2)}:"
            f"{round(current_speed, 1)}"
        )

    def get(
        self,
        route_id: str,
        target_lat: float,
        target_lon: float,
        current_lat: float,
        current_lon: float,
        current_speed: float,
    ) -> Optional[dict]:
        """
        Get cached ETA result if available and fresh.

        Returns:
            Cached ETA dict or None if not found/expired
        """
        key = self._make_key(
            route_id, target_lat, target_lon, current_lat, current_lon, current_speed
        )

        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        elapsed = time.time() - timestamp

        if elapsed > self.ttl_seconds:
            del self._cache[key]
            return None

        return value

    def set(
        self,
        route_id: str,
        target_lat: float,
        target_lon: float,
        current_lat: float,
        current_lon: float,
        current_speed: float,
        value: dict,
    ) -> None:
        """
        Store ETA result in cache.

        Args:
            value: Dictionary with ETA calculation results
        """
        key = self._make_key(
            route_id, target_lat, target_lon, current_lat, current_lon, current_speed
        )
        self._cache[key] = (value, time.time())

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of expired entries removed
        """
        now = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if (now - timestamp) > self.ttl_seconds
        ]

        for key in expired_keys:
            del self._cache[key]

        return len(expired_keys)

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache size and TTL info
        """
        return {
            "cached_entries": len(self._cache),
            "ttl_seconds": self.ttl_seconds,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class ETAHistoryTracker:
    """
    Track historical ETA accuracy for real-time monitoring and adjustment.

    Stores ETA predictions and actual arrival times to detect
    systematic errors and improve future estimates.
    """

    def __init__(self, max_history: int = 100):
        """
        Initialize the ETA history tracker.

        Args:
            max_history: Maximum number of history entries to keep
        """
        self.max_history = max_history
        self._history: list[dict] = []

    def record_prediction(
        self,
        waypoint_id: str,
        predicted_eta_seconds: float,
        current_position: Tuple[float, float],
        current_speed: float,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Record an ETA prediction for later accuracy analysis.

        Args:
            waypoint_id: Identifier for the target waypoint
            predicted_eta_seconds: Predicted ETA in seconds
            current_position: Current position as (lat, lon) tuple
            current_speed: Current speed in knots
            timestamp: Timestamp of prediction (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        record = {
            "waypoint_id": waypoint_id,
            "predicted_eta_seconds": predicted_eta_seconds,
            "current_position": current_position,
            "current_speed": current_speed,
            "prediction_time": timestamp,
            "actual_arrival_time": None,
            "accuracy_error_seconds": None,
        }

        self._history.append(record)

        # Trim history if needed
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history :]

    def record_arrival(
        self,
        waypoint_id: str,
        actual_arrival_time: Optional[datetime] = None,
    ) -> None:
        """
        Record actual arrival at a waypoint and calculate accuracy.

        Args:
            waypoint_id: Identifier for the waypoint
            actual_arrival_time: Actual arrival time (defaults to now)
        """
        if actual_arrival_time is None:
            actual_arrival_time = datetime.now(timezone.utc)

        # Find matching prediction (most recent for this waypoint)
        for record in reversed(self._history):
            if (
                record["waypoint_id"] == waypoint_id
                and record["actual_arrival_time"] is None
            ):
                record["actual_arrival_time"] = actual_arrival_time
                # Calculate error
                predicted_time = record["prediction_time"]
                (actual_arrival_time - predicted_time).total_seconds()
                expected_arrival = (
                    predicted_time.timestamp() + record["predicted_eta_seconds"]
                )
                record["accuracy_error_seconds"] = (
                    actual_arrival_time.timestamp() - expected_arrival
                )
                break

    def get_accuracy_stats(self) -> dict:
        """
        Get ETA accuracy statistics from historical data.

        Returns:
            Dictionary with accuracy metrics
        """
        completed = [r for r in self._history if r["actual_arrival_time"] is not None]

        if not completed:
            return {
                "total_predictions": len(self._history),
                "completed_arrivals": 0,
                "average_error_seconds": 0,
                "max_error_seconds": 0,
                "min_error_seconds": 0,
            }

        errors = [r["accuracy_error_seconds"] for r in completed]
        return {
            "total_predictions": len(self._history),
            "completed_arrivals": len(completed),
            "average_error_seconds": sum(errors) / len(errors),
            "max_error_seconds": max(errors),
            "min_error_seconds": min(errors),
            "accuracy_percentage": (
                (len(completed) / len(self._history) * 100) if self._history else 0
            ),
        }

    def clear(self) -> None:
        """Clear all history."""
        self._history.clear()
