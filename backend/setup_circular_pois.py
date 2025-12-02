#!/usr/bin/env python3
"""
Setup POIs evenly spaced around the circular track for course tracking testing.
Creates 20 POIs at 18-degree intervals around a circle centered at NYC.
"""

import math
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "starlink-location"))

from app.models.poi import POICreate
from app.services.poi_manager import POIManager


def haversine_destination(
    lat: float, lon: float, bearing: float, distance_km: float
) -> tuple[float, float]:
    """
    Calculate destination coordinates from a starting point, bearing, and distance.

    Uses Haversine formula.

    Args:
        lat: Starting latitude in degrees
        lon: Starting longitude in degrees
        bearing: Direction in degrees (0=North, 90=East, 180=South, 270=West)
        distance_km: Distance to travel in kilometers

    Returns:
        Tuple of (destination_latitude, destination_longitude)
    """
    R = 6371  # Earth's radius in kilometers

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)

    # Angular distance in radians
    angular_distance = distance_km / R

    # Destination latitude
    lat2_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance)
        + math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )

    # Destination longitude
    lon2_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(lat2_rad),
    )

    return (math.degrees(lat2_rad), math.degrees(lon2_rad))


def setup_circular_pois():
    """Clear all POIs and create new ones around the circular track."""

    # Configuration
    CENTER_LAT = 40.7128  # NYC latitude
    CENTER_LON = -74.0060  # NYC longitude
    RADIUS_KM = 100.0
    NUM_POIS = 20
    DEGREES_BETWEEN = 360 / NUM_POIS  # 18 degrees

    print(f"Setting up {NUM_POIS} POIs around circular track")
    print(f"Center: {CENTER_LAT}°N, {abs(CENTER_LON)}°W")
    print(f"Radius: {RADIUS_KM} km")
    print(f"Spacing: {DEGREES_BETWEEN}° apart")
    print()

    # Initialize POI manager
    poi_manager = POIManager()

    # Get current POIs
    existing_pois = poi_manager.list_pois()
    print(f"Found {len(existing_pois)} existing POIs")

    # Delete all existing POIs
    if existing_pois:
        print("Deleting existing POIs...")
        for poi in existing_pois:
            poi_manager.delete_poi(poi.id)
            print(f"  Deleted: {poi.name}")
        print()

    # Create new POIs at 18-degree intervals
    print("Creating new POIs...")
    for i in range(NUM_POIS):
        bearing = i * DEGREES_BETWEEN
        poi_name = f"Waypoint {i + 1:02d}"

        # Calculate POI location on the circle
        lat, lon = haversine_destination(CENTER_LAT, CENTER_LON, bearing, RADIUS_KM)

        # Create POI
        poi_create = POICreate(
            name=poi_name,
            latitude=lat,
            longitude=lon,
            icon="marker",
            category="waypoint",
            description=f"Test waypoint at {bearing:.0f}° bearing",
        )

        poi = poi_manager.create_poi(poi_create)
        print(f"  Created: {poi.name} at {poi.latitude:.4f}°, {poi.longitude:.4f}°")

    print()
    print(f"✓ Successfully created {NUM_POIS} evenly-spaced POIs")
    print("✓ POIs saved to /data/pois.json")
    print()
    print("POIs are now ready for course tracking tests!")


if __name__ == "__main__":
    try:
        setup_circular_pois()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
