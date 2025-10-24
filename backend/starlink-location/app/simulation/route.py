"""Synthetic route generator for position simulation."""

import math
from typing import List, Tuple

import numpy as np


def degrees_to_radians(degrees: float) -> float:
    """Convert degrees to radians."""
    return degrees * (math.pi / 180.0)


def radians_to_degrees(radians: float) -> float:
    """Convert radians to degrees."""
    return radians * (180.0 / math.pi)


def calculate_bearing(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float
) -> float:
    """
    Calculate bearing (heading) from point 1 to point 2.

    This is the initial bearing (forward azimuth) that would take you from
    point 1 to point 2 along a great-circle arc.

    Args:
        lat1: Starting latitude in decimal degrees
        lon1: Starting longitude in decimal degrees
        lat2: Ending latitude in decimal degrees
        lon2: Ending longitude in decimal degrees

    Returns:
        Bearing in degrees (0-360, where 0=North, 90=East, 180=South, 270=West)

    Formula:
        θ = atan2(sin(Δλ) * cos(φ2), cos(φ1) * sin(φ2) - sin(φ1) * cos(φ2) * cos(Δλ))

    Example:
        >>> calculate_bearing(41.5, -74.0, 41.6, -73.9)  # Moving northeast
        44.8  # degrees
    """
    # Convert to radians
    lat1_rad = degrees_to_radians(lat1)
    lon1_rad = degrees_to_radians(lon1)
    lat2_rad = degrees_to_radians(lat2)
    lon2_rad = degrees_to_radians(lon2)

    # Calculate bearing
    dlon = lon2_rad - lon1_rad

    y = math.sin(dlon) * math.cos(lat2_rad)
    x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
         math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon))

    bearing_rad = math.atan2(y, x)
    bearing_deg = radians_to_degrees(bearing_rad)

    # Normalize to 0-360 range
    return (bearing_deg + 360.0) % 360.0


def calculate_destination(
    start_lat: float,
    start_lon: float,
    bearing: float,
    distance_km: float
) -> Tuple[float, float]:
    """
    Calculate destination point given start, bearing, and distance.

    Uses Haversine formula for great-circle distance on Earth.

    Args:
        start_lat: Starting latitude (degrees)
        start_lon: Starting longitude (degrees)
        bearing: Bearing in degrees (0-360, 0=North)
        distance_km: Distance in kilometers

    Returns:
        Tuple of (latitude, longitude)
    """
    earth_radius_km = 6371.0

    lat1_rad = degrees_to_radians(start_lat)
    lon1_rad = degrees_to_radians(start_lon)
    bearing_rad = degrees_to_radians(bearing)

    lat2_rad = math.asin(
        math.sin(lat1_rad) * math.cos(distance_km / earth_radius_km) +
        math.cos(lat1_rad) * math.sin(distance_km / earth_radius_km) * math.cos(bearing_rad)
    )

    lon2_rad = lon1_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(distance_km / earth_radius_km) * math.cos(lat1_rad),
        math.cos(distance_km / earth_radius_km) - math.sin(lat1_rad) * math.sin(lat2_rad)
    )

    return (radians_to_degrees(lat2_rad), radians_to_degrees(lon2_rad))


class CircularRoute:
    """Generator for circular route patterns."""

    def __init__(
        self,
        center_lat: float,
        center_lon: float,
        radius_km: float,
        num_points: int = 360
    ):
        """
        Initialize circular route.

        Args:
            center_lat: Center latitude (degrees)
            center_lon: Center longitude (degrees)
            radius_km: Radius of circle (kilometers)
            num_points: Number of points around the circle (default 360)
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.radius_km = radius_km
        self.num_points = num_points
        self._generate_points()

    def _generate_points(self) -> None:
        """Generate points around circular route."""
        self.points = []

        for i in range(self.num_points):
            # Bearing from center to point (radial direction)
            bearing_from_center = (360.0 * i) / self.num_points

            # Calculate point position
            lat, lon = calculate_destination(
                self.center_lat,
                self.center_lon,
                bearing_from_center,
                self.radius_km
            )

            # Heading is tangent to circle (perpendicular to radius)
            # For clockwise motion: heading = radial_bearing + 90°
            heading = (bearing_from_center + 90.0) % 360.0

            self.points.append((lat, lon, heading))

    def get_point(self, progress: float) -> Tuple[float, float, float]:
        """
        Get point on route based on progress.

        Args:
            progress: Progress along route (0.0 to 1.0)

        Returns:
            Tuple of (latitude, longitude, heading)
        """
        # Wrap progress to 0-1 range
        progress = progress % 1.0

        # Get index
        index = int(progress * len(self.points)) % len(self.points)
        return self.points[index]

    def get_segment(self, progress: float) -> Tuple[float, float, float]:
        """
        Get interpolated point on route with smooth heading.

        Args:
            progress: Progress along route (0.0 to 1.0)

        Returns:
            Tuple of (latitude, longitude, heading)
        """
        # Wrap progress to 0-1 range
        progress = progress % 1.0

        # Get current and next index
        index = (progress * len(self.points)) % len(self.points)
        current_idx = int(index)
        next_idx = (current_idx + 1) % len(self.points)

        # Get interpolation factor
        factor = index - current_idx

        # Get current and next points
        lat1, lon1, head1 = self.points[current_idx]
        lat2, lon2, head2 = self.points[next_idx]

        # Linear interpolation (good enough for adjacent points on circle)
        lat = lat1 + (lat2 - lat1) * factor
        lon = lon1 + (lon2 - lon1) * factor

        # Handle heading wrap-around at 0/360
        if head2 < head1:
            head2 += 360.0
        heading = head1 + (head2 - head1) * factor
        heading = heading % 360.0

        return (lat, lon, heading)


class StraightRoute:
    """Generator for straight line route patterns."""

    def __init__(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float
    ):
        """
        Initialize straight line route.

        Args:
            start_lat: Starting latitude (degrees)
            start_lon: Starting longitude (degrees)
            end_lat: Ending latitude (degrees)
            end_lon: Ending longitude (degrees)
        """
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.end_lat = end_lat
        self.end_lon = end_lon

        # Calculate distance and bearing
        self._calculate_distance_and_bearing()

    def _calculate_distance_and_bearing(self) -> None:
        """Calculate total distance and bearing for the route."""
        lat1_rad = degrees_to_radians(self.start_lat)
        lon1_rad = degrees_to_radians(self.start_lon)
        lat2_rad = degrees_to_radians(self.end_lat)
        lon2_rad = degrees_to_radians(self.end_lon)

        earth_radius_km = 6371.0

        # Haversine distance
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        self.distance_km = earth_radius_km * c

        # Calculate bearing
        y = math.sin(dlon) * math.cos(lat2_rad)
        x = math.cos(lat1_rad) * math.sin(lat2_rad) - math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(dlon)
        self.bearing = radians_to_degrees(math.atan2(y, x))
        self.bearing = (self.bearing + 360) % 360

    def get_segment(self, progress: float) -> Tuple[float, float, float]:
        """
        Get interpolated point on straight route.

        Args:
            progress: Progress along route (0.0 to 1.0)

        Returns:
            Tuple of (latitude, longitude, heading)
        """
        # Wrap progress to 0-1 range
        progress = progress % 1.0

        # Calculate distance along route
        distance_along = progress * self.distance_km

        # Calculate position
        lat, lon = calculate_destination(
            self.start_lat,
            self.start_lon,
            self.bearing,
            distance_along
        )

        return (lat, lon, self.bearing)


def create_route(
    pattern: str,
    latitude_start: float,
    longitude_start: float,
    radius_km: float = 100.0,
    distance_km: float = 500.0
) -> CircularRoute | StraightRoute:
    """
    Create a route generator.

    Args:
        pattern: "circular" or "straight"
        latitude_start: Starting latitude
        longitude_start: Starting longitude
        radius_km: Radius for circular route
        distance_km: Distance for straight route

    Returns:
        CircularRoute or StraightRoute instance

    Raises:
        ValueError: If pattern is not recognized
    """
    if pattern == "circular":
        return CircularRoute(latitude_start, longitude_start, radius_km)
    elif pattern == "straight":
        # Calculate end point for straight route
        end_lat, end_lon = calculate_destination(
            latitude_start,
            longitude_start,
            45.0,  # Northeast direction
            distance_km
        )
        return StraightRoute(latitude_start, longitude_start, end_lat, end_lon)
    else:
        raise ValueError(f"Unknown route pattern: {pattern}")
