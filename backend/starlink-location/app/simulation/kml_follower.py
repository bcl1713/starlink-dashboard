"""KML route follower for simulation that follows KML routes."""

import logging
import math
import random
from typing import Optional

from app.models.route import ParsedRoute

logger = logging.getLogger(__name__)


class KMLRouteFollower:
    """
    Follows a KML route during simulation with realistic deviations.

    Features:
    - Load KML routes and follow waypoints
    - Realistic position deviations (±0.0001-0.001 degrees)
    - Calculate heading based on trajectory
    - Loop back to start when route completes
    - Progress tracking (0.0-1.0)
    """

    def __init__(self, route: ParsedRoute, deviation_degrees: float = 0.0005):
        """
        Initialize KML route follower.

        Args:
            route: ParsedRoute object to follow
            deviation_degrees: Random deviation range (±this value)
        """
        self.route = route
        self.deviation_degrees = deviation_degrees
        self.progress = 0.0  # 0.0 to 1.0
        self._current_waypoint_index = 0
        self._distance_to_next_waypoint = 0.0
        self._total_route_distance = route.get_total_distance()

        if self._total_route_distance == 0:
            logger.warning("Route has zero distance")

        logger.info(
            f"Initialized KMLRouteFollower for route: {route.metadata.name}, "
            f"points: {len(route.points)}, distance: {self._total_route_distance/1000:.1f}km"
        )

    def get_position(self, progress: float) -> dict:
        """
        Get current position along route with realistic deviations.

        Args:
            progress: Route progress (0.0 to 1.0)

        Returns:
            Dictionary with latitude, longitude, altitude, heading, and sequence
        """
        # Normalize progress to 0-1 and wrap around for looping
        progress = progress % 1.0

        # Calculate total distance traveled
        distance_traveled = progress * self._total_route_distance

        # Find current position on route
        cumulative_distance = 0.0

        for i in range(len(self.route.points) - 1):
            p1 = self.route.points[i]
            p2 = self.route.points[i + 1]

            segment_distance = self._calculate_distance(
                p1.latitude, p1.longitude, p2.latitude, p2.longitude
            )

            if cumulative_distance + segment_distance >= distance_traveled:
                # We're on this segment
                distance_into_segment = distance_traveled - cumulative_distance

                if segment_distance > 0:
                    segment_progress = distance_into_segment / segment_distance
                else:
                    segment_progress = 0.0

                # Interpolate position
                lat = p1.latitude + (p2.latitude - p1.latitude) * segment_progress
                lon = p1.longitude + (p2.longitude - p1.longitude) * segment_progress

                # Interpolate altitude if available
                alt = None
                if p1.altitude is not None and p2.altitude is not None:
                    alt = p1.altitude + (p2.altitude - p1.altitude) * segment_progress
                elif p1.altitude is not None:
                    alt = p1.altitude
                elif p2.altitude is not None:
                    alt = p2.altitude

                # Calculate heading based on direction to next point
                heading = self._calculate_heading(p1.latitude, p1.longitude, p2.latitude, p2.longitude)

                # Add realistic deviation
                lat_dev = random.uniform(-self.deviation_degrees, self.deviation_degrees)
                lon_dev = random.uniform(-self.deviation_degrees, self.deviation_degrees)

                return {
                    "latitude": lat + lat_dev,
                    "longitude": lon + lon_dev,
                    "altitude": alt,
                    "heading": heading,
                    "sequence": i,
                    "progress": progress,
                }

            cumulative_distance += segment_distance

        # If we get here, we're past the end - return last point
        last_point = self.route.points[-1]
        return {
            "latitude": last_point.latitude,
            "longitude": last_point.longitude,
            "altitude": last_point.altitude,
            "heading": 0.0,
            "sequence": len(self.route.points) - 1,
            "progress": progress,
        }

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points using Haversine formula."""
        earth_radius_m = 6371000.0
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return earth_radius_m * c

    def _calculate_heading(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate heading (bearing) from point 1 to point 2."""
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        dlon = lon2_rad - lon1_rad

        y = math.sin(dlon) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)

        heading_rad = math.atan2(y, x)
        heading_deg = math.degrees(heading_rad)

        # Normalize to 0-360
        return (heading_deg + 360) % 360

    def get_total_distance(self) -> float:
        """Get total route distance in meters."""
        return self._total_route_distance

    def get_point_count(self) -> int:
        """Get number of waypoints in route."""
        return len(self.route.points)

    def get_route_name(self) -> str:
        """Get route name."""
        return self.route.metadata.name

    def reset(self) -> None:
        """Reset follower to start of route."""
        self.progress = 0.0
        self._current_waypoint_index = 0
        logger.info("KML route follower reset to start")
