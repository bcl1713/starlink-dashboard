"""Route ETA calculator for estimating arrival times to waypoints and locations along a route."""

import math
import logging
from typing import Optional

from app.models.route import ParsedRoute
from app.services.eta_cache import ETACache, ETAHistoryTracker

logger = logging.getLogger(__name__)

# Global cache instance (singleton pattern)
_eta_cache = ETACache(ttl_seconds=5.0)
_eta_history = ETAHistoryTracker(max_history=100)


def project_point_to_line_segment(
    point_lat: float,
    point_lon: float,
    seg_start_lat: float,
    seg_start_lon: float,
    seg_end_lat: float,
    seg_end_lon: float,
) -> tuple[float, float, float]:
    """
    Project a point onto a line segment using parametric projection.

    Finds the closest point on the line segment to the given point.

    Args:
        point_lat/lon: Point to project
        seg_start_lat/lon: Start of line segment
        seg_end_lat/lon: End of line segment

    Returns:
        Tuple of (projected_lat, projected_lon, distance_to_segment_meters)
    """
    # Convert to radians for distance calculations
    p_lat, p_lon = math.radians(point_lat), math.radians(point_lon)
    a_lat, a_lon = math.radians(seg_start_lat), math.radians(seg_start_lon)
    b_lat, b_lon = math.radians(seg_end_lat), math.radians(seg_end_lon)

    # Haversine distance helper
    def haversine(lat1, lon1, lat2, lon2):
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return 6371000.0 * c  # Earth radius in meters

    # Calculate distances
    dist_a_b = haversine(a_lat, a_lon, b_lat, b_lon)
    dist_a_p = haversine(a_lat, a_lon, p_lat, p_lon)
    dist_b_p = haversine(b_lat, b_lon, p_lat, p_lon)

    # Handle zero-length segment
    if dist_a_b < 1:
        return seg_start_lat, seg_start_lon, dist_a_p

    # Parametric projection using spherical geometry approximation
    # For small segments, use planar approximation
    cos_angle = (
        (dist_a_b**2 + dist_a_p**2 - dist_b_p**2) / (2 * dist_a_b * dist_a_p)
        if dist_a_p > 0
        else 1
    )
    cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]

    t = dist_a_p * math.cos(math.acos(cos_angle)) / dist_a_b if dist_a_p > 0 else 0
    t = max(0, min(1, t))  # Clamp to [0, 1]

    # Linear interpolation for projected point
    proj_lat = seg_start_lat + t * (seg_end_lat - seg_start_lat)
    proj_lon = seg_start_lon + t * (seg_end_lon - seg_start_lon)

    # Distance from point to projected point
    dist_to_proj = haversine(
        p_lat, p_lon, math.radians(proj_lat), math.radians(proj_lon)
    )

    return proj_lat, proj_lon, dist_to_proj


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

    def project_poi_to_route(
        self,
        poi_lat: float,
        poi_lon: float,
    ) -> dict:
        """
        Project a POI onto the route path.

        Finds the closest point on the route's LineString to the POI and calculates
        the progress percentage where that point occurs.

        Args:
            poi_lat: POI latitude
            poi_lon: POI longitude

        Returns:
            Dictionary with:
            - projected_lat: Latitude of projection point
            - projected_lon: Longitude of projection point
            - projected_waypoint_index: Index of closest route point
            - projected_route_progress: Progress percentage (0-100) where POI projects
            - distance_to_route_meters: Distance from POI to its projection
        """
        if not self.route.points:
            return {
                "projected_lat": poi_lat,
                "projected_lon": poi_lon,
                "projected_waypoint_index": 0,
                "projected_route_progress": 0.0,
                "distance_to_route_meters": float("inf"),
            }

        best_proj_lat = self.route.points[0].latitude
        best_proj_lon = self.route.points[0].longitude
        best_waypoint_index = 0
        best_distance = float("inf")
        best_distance_along_route = 0.0

        # Find closest point on route path by checking all segments
        distance_along_route = 0.0

        for i in range(len(self.route.points) - 1):
            p1 = self.route.points[i]
            p2 = self.route.points[i + 1]

            # Project POI onto this segment
            proj_lat, proj_lon, dist_to_segment = project_point_to_line_segment(
                poi_lat,
                poi_lon,
                p1.latitude,
                p1.longitude,
                p2.latitude,
                p2.longitude,
            )

            # Check if this is the closest projection so far
            if dist_to_segment < best_distance:
                best_distance = dist_to_segment
                best_proj_lat = proj_lat
                best_proj_lon = proj_lon
                best_waypoint_index = i
                best_distance_along_route = (
                    distance_along_route
                    + self._haversine_distance(
                        p1.latitude,
                        p1.longitude,
                        proj_lat,
                        proj_lon,
                    )
                )

            # Add segment distance for next iteration
            distance_along_route += self._haversine_distance(
                p1.latitude,
                p1.longitude,
                p2.latitude,
                p2.longitude,
            )

        # Calculate progress percentage
        total_distance = self.route.get_total_distance()
        projected_route_progress = (
            (best_distance_along_route / total_distance * 100)
            if total_distance > 0
            else 0.0
        )

        return {
            "projected_lat": best_proj_lat,
            "projected_lon": best_proj_lon,
            "projected_waypoint_index": best_waypoint_index,
            "projected_route_progress": projected_route_progress,
            "distance_to_route_meters": best_distance,
        }

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
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
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

    def _calculate_remaining_duration_from_segments(
        self,
        start_index: int,
    ) -> Optional[float]:
        """
        Calculate expected duration for remaining route using segment-specific data.

        This method calculates the actual expected time to complete the remaining
        route by examining each segment's timing data and expected speeds.

        Args:
            start_index: Index of current position on route

        Returns:
            Duration in seconds, or None if cannot be calculated
        """
        if not self.route.timing_profile or start_index >= len(self.route.points) - 1:
            return None

        total_remaining_duration = 0.0

        # If we have a timing profile with departure and arrival times,
        # use the expected arrival time from the profile
        if (
            self.route.timing_profile.arrival_time
            and self.route.timing_profile.departure_time
        ):
            # Get the expected arrival time for the route
            arrival_time = self.route.timing_profile.arrival_time

            # Calculate time from current point to final destination
            if self.route.points[start_index].expected_arrival_time:
                time_delta = (
                    arrival_time - self.route.points[start_index].expected_arrival_time
                ).total_seconds()
                if time_delta > 0:
                    return time_delta

        # Fall back to calculating from segment speeds if available
        for i in range(start_index, len(self.route.points) - 1):
            point = self.route.points[i]
            next_point = self.route.points[i + 1]

            # Get segment distance
            segment_distance = self._haversine_distance(
                point.latitude,
                point.longitude,
                next_point.latitude,
                next_point.longitude,
            )

            # Get segment speed
            segment_speed = self._get_speed_for_segment(i)

            # Calculate time for this segment
            if segment_speed > 0:
                segment_duration = (segment_distance / 1852.0 / segment_speed) * 3600.0
                total_remaining_duration += segment_duration

        return total_remaining_duration if total_remaining_duration > 0 else None

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
            "estimated_time_remaining_seconds": (
                eta_seconds if eta_seconds >= 0 else None
            ),
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
            "estimated_time_remaining_seconds": (
                eta_seconds if eta_seconds >= 0 else None
            ),
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
            self.route.waypoints[nearest_waypoint_idx] if self.route.waypoints else None
        )

        # Calculate progress
        total_distance = self.route.get_total_distance()
        distance_completed = self._calculate_distance_along_route(0, nearest_point_idx)
        distance_remaining = total_distance - distance_completed

        progress_percent = (
            (distance_completed / total_distance * 100) if total_distance > 0 else 0.0
        )

        # Get timing information
        expected_total_duration = None
        expected_duration_remaining = None
        if self.route.timing_profile:
            expected_total_duration = self.route.timing_profile.get_total_duration()

        # Calculate remaining duration using segment-aware method if available
        # This ensures multi-leg routes with varying speeds calculate correct ETAs
        if not expected_duration_remaining and self.route.timing_profile:
            expected_duration_remaining = (
                self._calculate_remaining_duration_from_segments(nearest_point_idx)
            )

        # Calculate average speed if we have total duration
        average_speed = self.DEFAULT_SPEED_KNOTS
        if expected_total_duration and expected_total_duration > 0:
            average_speed = (total_distance / expected_total_duration) * (3600 / 1852)

            # If we couldn't calculate segment-aware duration, fall back to average speed
            if (
                not expected_duration_remaining
                and average_speed > 0
                and distance_remaining > 0
            ):
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
