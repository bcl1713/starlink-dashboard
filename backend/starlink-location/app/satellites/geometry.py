"""Azimuth and elevation calculations for satellite geometry.

Provides functions to convert between geodetic (lat/lon/alt) and ECEF
(Earth-Centered, Earth-Fixed) coordinates, and to calculate azimuth and
elevation angles from an aircraft to a satellite.

Reference ellipsoid: WGS84
"""

import math
from typing import Tuple

# WGS84 ellipsoid parameters
WGS84_SEMI_MAJOR_AXIS = 6378137.0  # meters (a)
WGS84_ECCENTRICITY_SQUARED = 6.69437999014132e-3  # (e^2)
WGS84_SEMI_MINOR_AXIS = 6356752.314245  # meters (b)

# Geostationary orbit altitude (approximate mean)
GEOSTATIONARY_ALTITUDE = 35786000.0  # meters


def ecef_from_geodetic(
    latitude: float, longitude: float, altitude: float = 0.0
) -> Tuple[float, float, float]:
    """Convert geodetic coordinates to ECEF (Earth-Centered, Earth-Fixed).

    Args:
        latitude: Latitude in decimal degrees (-90 to 90)
        longitude: Longitude in decimal degrees (-180 to 180)
        altitude: Altitude in meters above sea level (default: 0)

    Returns:
        Tuple of (x, y, z) ECEF coordinates in meters

    Reference:
        https://en.wikipedia.org/wiki/Earth-centered,_Earth-fixed_coordinate_system
    """
    # Convert to radians
    lat_rad = math.radians(latitude)
    lon_rad = math.radians(longitude)

    # Calculate N (prime vertical radius of curvature)
    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    n = WGS84_SEMI_MAJOR_AXIS / math.sqrt(1 - WGS84_ECCENTRICITY_SQUARED * sin_lat**2)

    # Calculate ECEF coordinates
    x = (n + altitude) * cos_lat * math.cos(lon_rad)
    y = (n + altitude) * cos_lat * math.sin(lon_rad)
    z = (n * (1 - WGS84_ECCENTRICITY_SQUARED) + altitude) * sin_lat

    return x, y, z


def geodetic_from_ecef(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Convert ECEF coordinates to geodetic coordinates.

    Uses iterative method for improved accuracy.

    Args:
        x, y, z: ECEF coordinates in meters

    Returns:
        Tuple of (latitude, longitude, altitude)
        - latitude in decimal degrees (-90 to 90)
        - longitude in decimal degrees (-180 to 180)
        - altitude in meters above sea level
    """
    # Calculate longitude
    longitude = math.degrees(math.atan2(y, x))

    # Distance from z-axis
    p = math.sqrt(x**2 + y**2)

    # Iterative method for latitude and altitude
    # Start with geocentric latitude as initial guess
    latitude = math.atan2(z, p * (1 - WGS84_ECCENTRICITY_SQUARED))

    # Iterate to converge on latitude
    for _ in range(10):
        sin_lat = math.sin(latitude)
        n = WGS84_SEMI_MAJOR_AXIS / math.sqrt(
            1 - WGS84_ECCENTRICITY_SQUARED * sin_lat**2
        )
        latitude = math.atan2(z + WGS84_ECCENTRICITY_SQUARED * n * sin_lat, p)

    # Calculate altitude
    sin_lat = math.sin(latitude)
    cos_lat = math.cos(latitude)
    n = WGS84_SEMI_MAJOR_AXIS / math.sqrt(1 - WGS84_ECCENTRICITY_SQUARED * sin_lat**2)
    altitude = (
        p / cos_lat - n
        if abs(cos_lat) > 1e-10
        else z / sin_lat - n * (1 - WGS84_ECCENTRICITY_SQUARED)
    )

    latitude = math.degrees(latitude)

    return latitude, longitude, altitude


def azimuth_elevation_from_ecef(
    observer_ecef: Tuple[float, float, float],
    target_ecef: Tuple[float, float, float],
    observer_lat_deg: float,
    observer_lon_deg: float,
) -> Tuple[float, float]:
    """Calculate azimuth and elevation from observer to target in ECEF.

    Args:
        observer_ecef: Observer position as (x, y, z) in meters
        target_ecef: Target position as (x, y, z) in meters
        observer_lat_deg: Observer latitude in decimal degrees (for local horizon)
        observer_lon_deg: Observer longitude in decimal degrees (for local horizon)

    Returns:
        Tuple of (azimuth, elevation) in decimal degrees
        - azimuth: 0° = North, 90° = East, 180° = South, 270° = West
        - elevation: 0° = horizon, 90° = zenith, negative = below horizon

    Reference:
        https://en.wikipedia.org/wiki/Horizontal_coordinate_system
    """
    # Vector from observer to target in ECEF
    dx = target_ecef[0] - observer_ecef[0]
    dy = target_ecef[1] - observer_ecef[1]
    dz = target_ecef[2] - observer_ecef[2]

    # Convert observer position to geodetic for local coordinate system
    # Create local horizon frame (SEZ: South-East-Z)
    lat_rad = math.radians(observer_lat_deg)
    lon_rad = math.radians(observer_lon_deg)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    sin_lon = math.sin(lon_rad)
    cos_lon = math.cos(lon_rad)

    # Rotation matrix from ECEF to SEZ (South-East-Zenith)
    # This transforms the ECEF vector to local horizon coordinates
    south = sin_lat * cos_lon * dx + sin_lat * sin_lon * dy - cos_lat * dz
    east = -sin_lon * dx + cos_lon * dy
    zenith = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

    # Calculate elevation (angle above horizon)
    distance = math.sqrt(south**2 + east**2 + zenith**2)
    if distance == 0:
        elevation = 90.0
    else:
        elevation = math.degrees(math.asin(zenith / distance))

    # Calculate azimuth (angle from north, measured clockwise)
    # In SEZ frame: South=+s, East=+e, Zenith=+z
    # Azimuth measured from North (which is -South direction)
    azimuth = math.degrees(math.atan2(east, -south))
    if azimuth < 0:
        azimuth += 360.0

    return azimuth, elevation


def look_angles(
    aircraft_lat_deg: float,
    aircraft_lon_deg: float,
    aircraft_alt_m: float,
    satellite_lon_deg: float,
    satellite_alt_m: float = GEOSTATIONARY_ALTITUDE,
) -> Tuple[float, float]:
    """Calculate look angles (azimuth, elevation) from aircraft to satellite.

    Simplified wrapper for geostationary satellites (fixed latitude at equator).

    Args:
        aircraft_lat_deg: Aircraft latitude in decimal degrees
        aircraft_lon_deg: Aircraft longitude in decimal degrees
        aircraft_alt_m: Aircraft altitude in meters above sea level
        satellite_lon_deg: Satellite longitude in decimal degrees (sat latitude ~0 at equator)
        satellite_alt_m: Satellite altitude in meters (default: geostationary)

    Returns:
        Tuple of (azimuth, elevation) in decimal degrees
        - azimuth: 0° = North, 90° = East, 180° = South, 270° = West
        - elevation: 0° = horizon, positive = above horizon, negative = below

    Note:
        For geostationary satellites, latitude is assumed to be ~0° (equator).
        For LEO satellites, use azimuth_elevation_from_ecef() directly.
    """
    # Convert observer and target to ECEF
    observer_ecef = ecef_from_geodetic(
        aircraft_lat_deg, aircraft_lon_deg, aircraft_alt_m
    )

    # Satellite at equator (lat=0) with given longitude
    target_ecef = ecef_from_geodetic(0.0, satellite_lon_deg, satellite_alt_m)

    return azimuth_elevation_from_ecef(
        observer_ecef, target_ecef, aircraft_lat_deg, aircraft_lon_deg
    )


def is_in_azimuth_range(azimuth: float, min_azimuth: float, max_azimuth: float) -> bool:
    """Check if azimuth is within a specified range (handles wraparound).

    Useful for checking forbidden cones that may wrap around North (0°).

    Args:
        azimuth: Current azimuth in degrees (0-360)
        min_azimuth: Minimum azimuth in degrees
        max_azimuth: Maximum azimuth in degrees

    Returns:
        True if azimuth is within the range (accounting for 0°/360° wraparound)

    Examples:
        - is_in_azimuth_range(10, 315, 45) -> True (wraps around North)
        - is_in_azimuth_range(180, 135, 225) -> True
        - is_in_azimuth_range(270, 135, 225) -> False
    """
    azimuth = azimuth % 360.0
    min_azimuth = min_azimuth % 360.0
    max_azimuth = max_azimuth % 360.0

    if min_azimuth <= max_azimuth:
        # Normal range (no wraparound)
        return min_azimuth <= azimuth <= max_azimuth
    else:
        # Wraparound range (e.g., 315-45 crosses 0°)
        return azimuth >= min_azimuth or azimuth <= max_azimuth
