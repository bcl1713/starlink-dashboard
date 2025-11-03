"""Route ETA calculator for estimating arrival times to waypoints and locations along a route."""

import math
import logging
from typing import Optional
from datetime import datetime

from app.models.route import ParsedRoute, RoutePoint, RouteWaypoint
from app.services.eta_cache import ETACache, ETAHistoryTracker

logger = logging.getLogger(__name__)

# Global cache instance (singleton pattern)
_eta_cache = ETACache(ttl_seconds=5.0)
_eta_history = ETAHistoryTracker(max_history=100)


class RouteETACalculator:
    """
    Calculate ETAs for routes with embedded timing data.

    Provides ETA calculations to waypoints, arbitrary locations, and route progress metrics.
    Supports both routes with timing data and estimates for routes without timing.
    Includes caching for improved performance and history tracking for accuracy analysis.
    """

    EARTH_RADIUS_M = 6371000.0  # Earth's radius in meters
    DEFAULT_SPEED_KNOTS = 500.0  # Default cruise speed for aircraft

    def __init__(self, parsed_route: ParsedRoute):
        """
        Initialize the route ETA calculator.

        Args:
            parsed_route: ParsedRoute object containing points, waypoints, and optional timing data
        """
        self.route = parsed_route
        self._validate_route()

    def _validate_route(self) -> None:
        """Validate that route has required data."""
        if not self.route.points:
            raise ValueError("Route must have at least one point")

    def _haversine_distance(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """
        Calculate great-circle distance using Haversine formula.

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

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad)
            * math.cos(lat2_rad)
            * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return self.EARTH_RADIUS_M * c

    def find_nearest_point(
        self,
        current_lat: float,
        current_lon: float,
    ) -> tuple[int, float]:
        """
        Find the nearest route point to the current position.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude

        Returns:
            Tuple of (point_index, distance_to_point_meters)
        """
        min_distance = float("inf")
        nearest_index = 0

        for idx, point in enumerate(self.route.points):
            distance = self._haversine_distance(
                current_lat,
                current_lon,
                point.latitude,
                point.longitude,
            )

            if distance < min_distance:
                min_distance = distance
                nearest_index = idx

        return nearest_index, min_distance

    def _get_speed_for_segment(self, point_index: int) -> float:
        """
        Get the expected speed for a route segment.

        Prioritizes speed data from timing profile, falls back to default.

        Args:
            point_index: Index of the route point

        Returns:
            Speed in knots
        """
        if point_index >= len(self.route.points):
            return self.DEFAULT_SPEED_KNOTS

        point = self.route.points[point_index]

        # Use segment speed if available from timing data
        if point.expected_segment_speed_knots:
            return point.expected_segment_speed_knots

        # Fall back to average speed from route timing profile
        if (
            self.route.timing_profile
            and self.route.timing_profile.total_expected_duration_seconds
        ):
            # Calculate average speed from total distance and duration
            total_distance_m = self.route.get_total_distance()
            total_duration_s = self.route.timing_profile.total_expected_duration_seconds

            if total_duration_s > 0:
                # speed (knots) = distance (meters) / time (seconds) * conversion factor
                # conversion: meters/second to knots = * 3600 / 1852
                return (total_distance_m / total_duration_s) * (3600 / 1852)

        return self.DEFAULT_SPEED_KNOTS

    def _calculate_distance_along_route(
        self,
        start_index: int,
        end_index: int,
    ) -> float:
        """
        Calculate distance along the route between two points.

        Args:
            start_index: Starting point index (inclusive)
            end_index: Ending point index (inclusive)

        Returns:
            Distance in meters
        """
        if start_index > end_index or start_index >= len(self.route.points):
            return 0.0

        distance = 0.0
        for i in range(start_index, min(end_index, len(self.route.points) - 1)):
            p1 = self.route.points[i]
            p2 = self.route.points[i + 1]

            segment_distance = self._haversine_distance(
                p1.latitude,
                p1.longitude,
                p2.latitude,
                p2.longitude,
            )
            distance += segment_distance

        return distance

    def calculate_eta_to_waypoint(
        self,
        waypoint_index: int,
        current_lat: float,
        current_lon: float,
    ) -> dict:
        """
        Calculate ETA to a specific waypoint.

        Args:
            waypoint_index: Index of the waypoint in route.waypoints
            current_lat: Current latitude
            current_lon: Current longitude

        Returns:
            Dictionary with ETA information:
            - waypoint_index: Index of target waypoint
            - waypoint_name: Name of waypoint
            - waypoint_lat/lon: Waypoint coordinates
            - expected_arrival_time: Expected arrival time if timing data available
            - distance_remaining_meters: Distance to waypoint
            - distance_remaining_km: Distance in kilometers
            - estimated_time_remaining_seconds: ETA in seconds
            - estimated_speed_knots: Estimated speed used for calculation
        """
        if waypoint_index >= len(self.route.waypoints):
            raise ValueError(f"Waypoint index {waypoint_index} out of range")

        waypoint = self.route.waypoints[waypoint_index]

        # Find nearest route point to current position
        nearest_index, _ = self.find_nearest_point(current_lat, current_lon)

        # Find which route point corresponds to this waypoint
        # (waypoints are typically embedded in the route description)
        # For now, estimate based on route length
        waypoint_route_index = int(
            (waypoint_index / len(self.route.waypoints)) * len(self.route.points)
        )
        waypoint_route_index = min(waypoint_route_index, len(self.route.points) - 1)

        # Calculate distance remaining along route
        distance_to_waypoint = self._haversine_distance(
            current_lat,
            current_lon,
            waypoint.latitude,
            waypoint.longitude,
        )

        # Get average speed
        speed_knots = self._get_speed_for_segment(nearest_index)

        # Calculate ETA
        if speed_knots > 0:
            eta_seconds = (distance_to_waypoint / 1852.0 / speed_knots) * 3600.0
        else:
            eta_seconds = -1.0

        return {
            "waypoint_index": waypoint_index,
            "waypoint_name": waypoint.name or f"Waypoint {waypoint_index}",
            "waypoint_lat": waypoint.latitude,
            "waypoint_lon": waypoint.longitude,
            "expected_arrival_time": (
                waypoint.expected_arrival_time.isoformat()
                if waypoint.expected_arrival_time
                else None
            ),
            "distance_remaining_meters": distance_to_waypoint,
            "distance_remaining_km": distance_to_waypoint / 1000.0,
            "estimated_time_remaining_seconds": eta_seconds if eta_seconds >= 0 else None,
            "estimated_speed_knots": speed_knots,
        }

    def calculate_eta_to_location(
        self,
        target_lat: float,
        target_lon: float,
        current_lat: float,
        current_lon: float,
    ) -> dict:
        """
        Calculate ETA to an arbitrary location on or near the route.

        Args:
            target_lat: Target latitude
            target_lon: Target longitude
            current_lat: Current latitude
            current_lon: Current longitude

        Returns:
            Dictionary with ETA information (same structure as calculate_eta_to_waypoint)
        """
        nearest_index, _ = self.find_nearest_point(current_lat, current_lon)

        # Calculate direct distance to target
        distance_to_target = self._haversine_distance(
            current_lat,
            current_lon,
            target_lat,
            target_lon,
        )

        # Get speed
        speed_knots = self._get_speed_for_segment(nearest_index)

        # Calculate ETA
        if speed_knots > 0:
            eta_seconds = (distance_to_target / 1852.0 / speed_knots) * 3600.0
        else:
            eta_seconds = -1.0

        return {
            "target_lat": target_lat,
            "target_lon": target_lon,
            "distance_to_target_meters": distance_to_target,
            "distance_to_target_km": distance_to_target / 1000.0,
            "estimated_time_remaining_seconds": eta_seconds if eta_seconds >= 0 else None,
            "estimated_speed_knots": speed_knots,
        }

    def get_route_progress(
        self,
        current_lat: float,
        current_lon: float,
    ) -> dict:
        """
        Calculate overall route progress metrics.

        Args:
            current_lat: Current latitude
            current_lon: Current longitude

        Returns:
            Dictionary with progress information:
            - current_waypoint_index: Index of closest waypoint
            - current_waypoint_name: Name of closest waypoint
            - progress_percent: Percentage of route completed (0-100)
            - total_route_distance_meters: Total route distance
            - distance_completed_meters: Distance traveled so far
            - distance_remaining_meters: Distance left to travel
            - expected_total_duration_seconds: Total expected time if timing available
            - expected_duration_remaining_seconds: Remaining time
            - average_speed_knots: Average speed along route
        """
        nearest_point_idx, _ = self.find_nearest_point(current_lat, current_lon)

        # Find nearest waypoint
        nearest_waypoint_idx = 0
        if self.route.waypoints:
            min_waypoint_distance = float("inf")
            for idx, waypoint in enumerate(self.route.waypoints):
                distance = self._haversine_distance(
                    current_lat,
                    current_lon,
                    waypoint.latitude,
                    waypoint.longitude,
                )
                if distance < min_waypoint_distance:
                    min_waypoint_distance = distance
                    nearest_waypoint_idx = idx

        nearest_waypoint = (
            self.route.waypoints[nearest_waypoint_idx]
            if self.route.waypoints
            else None
        )

        # Calculate progress
        total_distance = self.route.get_total_distance()
        distance_completed = self._calculate_distance_along_route(0, nearest_point_idx)
        distance_remaining = total_distance - distance_completed

        progress_percent = (
            (distance_completed / total_distance * 100)
            if total_distance > 0
            else 0.0
        )

        # Get timing information
        expected_total_duration = None
        expected_duration_remaining = None
        if self.route.timing_profile:
            expected_total_duration = (
                self.route.timing_profile.get_total_duration()
            )

        # Calculate average speed if we have total duration
        average_speed = self.DEFAULT_SPEED_KNOTS
        if expected_total_duration and expected_total_duration > 0:
            average_speed = (total_distance / expected_total_duration) * (3600 / 1852)

            # Calculate remaining time based on distance and average speed
            if average_speed > 0 and distance_remaining > 0:
                expected_duration_remaining = (
                    distance_remaining / 1852.0 / average_speed
                ) * 3600.0

        return {
            "current_waypoint_index": nearest_waypoint_idx,
            "current_waypoint_name": (
                nearest_waypoint.name if nearest_waypoint else "Unknown"
            ),
            "progress_percent": progress_percent,
            "total_route_distance_meters": total_distance,
            "distance_completed_meters": distance_completed,
            "distance_remaining_meters": distance_remaining,
            "expected_total_duration_seconds": expected_total_duration,
            "expected_duration_remaining_seconds": expected_duration_remaining,
            "average_speed_knots": average_speed,
        }


def get_eta_cache_stats() -> dict:
    """
    Get statistics about the global ETA cache.

    Returns:
        Dictionary with cache metrics
    """
    return _eta_cache.stats()


def get_eta_accuracy_stats() -> dict:
    """
    Get ETA accuracy statistics from historical tracking.

    Returns:
        Dictionary with accuracy metrics
    """
    return _eta_history.get_accuracy_stats()


def clear_eta_cache() -> None:
    """Clear all cached ETA calculations."""
    _eta_cache.clear()


def cleanup_eta_cache() -> int:
    """
    Clean up expired entries in the ETA cache.

    Returns:
        Number of expired entries removed
    """
    return _eta_cache.cleanup_expired()
