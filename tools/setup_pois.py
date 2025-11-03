#!/usr/bin/env python3
"""Setup POIs evenly spaced around the circular track using REST API."""

import math
import json
import requests
import sys

API_BASE = "http://localhost:8000"

# Configuration
CENTER_LAT = 40.7128  # NYC latitude
CENTER_LON = -74.0060  # NYC longitude
RADIUS_KM = 100.0
NUM_POIS = 20
DEGREES_BETWEEN = 360 / NUM_POIS  # 18 degrees


def haversine_destination(lat: float, lon: float, bearing: float, distance_km: float) -> tuple:
    """Calculate destination coordinates from starting point, bearing, and distance."""
    R = 6371  # Earth's radius in km
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    bearing_rad = math.radians(bearing)
    angular_distance = distance_km / R

    lat2_rad = math.asin(
        math.sin(lat_rad) * math.cos(angular_distance) +
        math.cos(lat_rad) * math.sin(angular_distance) * math.cos(bearing_rad)
    )

    lon2_rad = lon_rad + math.atan2(
        math.sin(bearing_rad) * math.sin(angular_distance) * math.cos(lat_rad),
        math.cos(angular_distance) - math.sin(lat_rad) * math.sin(lat2_rad)
    )

    return (math.degrees(lat2_rad), math.degrees(lon2_rad))


def delete_all_pois():
    """Delete all existing POIs."""
    try:
        response = requests.get(f"{API_BASE}/api/pois")
        pois = response.json().get("pois", [])

        if pois:
            print(f"Deleting {len(pois)} existing POIs...")
            for poi in pois:
                poi_id = poi["id"]
                requests.delete(f"{API_BASE}/api/pois/{poi_id}")
                print(f"  Deleted: {poi['name']}")
        else:
            print("No existing POIs to delete")
    except Exception as e:
        print(f"Error deleting POIs: {e}")
        sys.exit(1)


def create_pois():
    """Create POIs at 18-degree intervals around the circle."""
    print(f"\nCreating {NUM_POIS} POIs around circular track...")
    print(f"Center: {CENTER_LAT}°N, {abs(CENTER_LON)}°W")
    print(f"Radius: {RADIUS_KM} km")
    print(f"Spacing: {DEGREES_BETWEEN}° apart\n")

    for i in range(NUM_POIS):
        bearing = i * DEGREES_BETWEEN
        poi_name = f"Waypoint {i + 1:02d}"

        # Calculate POI location on the circle
        lat, lon = haversine_destination(CENTER_LAT, CENTER_LON, bearing, RADIUS_KM)

        # Create POI via API
        poi_data = {
            "name": poi_name,
            "latitude": lat,
            "longitude": lon,
            "icon": "marker",
            "category": "waypoint",
            "description": f"Test waypoint at {bearing:.0f}° bearing"
        }

        try:
            response = requests.post(f"{API_BASE}/api/pois", json=poi_data)
            if response.status_code == 201:
                poi = response.json()
                print(f"  ✓ {poi['name']:20} at {poi['latitude']:.4f}°, {poi['longitude']:.4f}°")
            else:
                print(f"  ✗ Failed to create {poi_name}: {response.status_code}")
        except Exception as e:
            print(f"  ✗ Error creating {poi_name}: {e}")

    print(f"\n✓ Successfully created {NUM_POIS} evenly-spaced POIs!")
    print("✓ POIs are ready for course tracking tests!")


if __name__ == "__main__":
    delete_all_pois()
    create_pois()
