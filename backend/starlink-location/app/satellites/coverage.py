"""Coverage sampling for Ka satellite transport.

Samples aircraft route to detect entry/exit events into satellite coverage
areas using point-in-polygon testing against GeoJSON footprints.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CoverageEvent:
    """Represents a satellite coverage entry or exit event."""

    timestamp: datetime
    event_type: str  # "entry" or "exit"
    satellite_id: str
    latitude: float
    longitude: float
    metadata: Optional[dict] = None


def point_in_polygon(
    point: Tuple[float, float], polygon: List[Tuple[float, float]]
) -> bool:
    """Test if a point is inside a polygon using ray casting algorithm.

    Args:
        point: (longitude, latitude) tuple
        polygon: List of (longitude, latitude) tuples forming polygon exterior ring

    Returns:
        True if point is inside polygon
    """
    lon, lat = point
    n = len(polygon)
    inside = False

    p1_lon, p1_lat = polygon[0]
    for i in range(1, n + 1):
        p2_lon, p2_lat = polygon[i % n]

        if lat > min(p1_lat, p2_lat):
            if lat <= max(p1_lat, p2_lat):
                if lon <= max(p1_lon, p2_lon):
                    if p1_lat != p2_lat:
                        x_intersect = (lat - p1_lat) * (p2_lon - p1_lon) / (
                            p2_lat - p1_lat
                        ) + p1_lon

                    if p1_lon == p2_lon or lon <= x_intersect:
                        inside = not inside

        p1_lon, p1_lat = p2_lon, p2_lat

    return inside


class CoverageSampler:
    """Samples route for satellite coverage entry/exit events."""

    def __init__(self, coverage_geojson_path: Optional[Path] = None):
        """Initialize sampler with optional coverage data.

        Args:
            coverage_geojson_path: Path to HCX or custom coverage GeoJSON
        """
        self.coverage_data = None
        self.satellite_polygons = {}  # satellite_id -> list of polygon rings

        if coverage_geojson_path and coverage_geojson_path.exists():
            self._load_coverage_geojson(coverage_geojson_path)

    def _load_coverage_geojson(self, geojson_path: Path) -> None:
        """Load and parse coverage GeoJSON file.

        Handles both single-polygon and multi-polygon features (e.g., PORB split
        across International Date Line as two separate polygon rings).

        Args:
            geojson_path: Path to GeoJSON file
        """
        try:
            with open(geojson_path, "r") as f:
                self.coverage_data = json.load(f)

            # Index polygons by satellite_id from feature properties
            # Store as list of rings to handle MultiPolygon or split regions
            satellite_rings = {}  # satellite_id -> list of polygon rings

            for feature in self.coverage_data.get("features", []):
                if feature.get("type") != "Feature":
                    continue

                props = feature.get("properties", {})
                satellite_id = props.get("satellite_id")
                geometry = feature.get("geometry", {})
                geom_type = geometry.get("type")

                if not satellite_id:
                    continue

                # Handle Polygon (single ring)
                if geom_type == "Polygon":
                    coords = geometry.get("coordinates", [])
                    if coords:
                        ring = [(lon, lat) for lon, lat in coords[0]]
                        if satellite_id not in satellite_rings:
                            satellite_rings[satellite_id] = []
                        satellite_rings[satellite_id].append(ring)

                # Handle MultiPolygon (e.g., PORB split by IDL)
                elif geom_type == "MultiPolygon":
                    coords_list = geometry.get("coordinates", [])
                    if satellite_id not in satellite_rings:
                        satellite_rings[satellite_id] = []

                    for polygon_coords in coords_list:
                        if polygon_coords:
                            ring = [(lon, lat) for lon, lat in polygon_coords[0]]
                            satellite_rings[satellite_id].append(ring)

            # Convert to coverage format (store all rings for each satellite)
            self.satellite_polygons = satellite_rings

            logger.info(
                f"Loaded coverage for {len(self.satellite_polygons)} satellites "
                f"({sum(len(rings) for rings in self.satellite_polygons.values())} total rings)"
            )

        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load coverage GeoJSON: {e}")
            self.coverage_data = None
            self.satellite_polygons = {}

    def check_coverage_at_point(
        self, latitude: float, longitude: float
    ) -> List[str]:
        """Check which satellites cover a given point.

        Handles multi-ring polygons (e.g., coverage split by International Date Line).

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees

        Returns:
            List of satellite IDs that cover this point
        """
        point = (longitude, latitude)
        covered_by = []

        for satellite_id, polygon_rings in self.satellite_polygons.items():
            # polygon_rings is a list of rings for this satellite
            # Check if point is in any of the rings
            if isinstance(polygon_rings, list):
                for ring in polygon_rings:
                    if point_in_polygon(point, ring):
                        covered_by.append(satellite_id)
                        break  # Found coverage for this satellite
            else:
                # Backward compatibility: single ring
                if point_in_polygon(point, polygon_rings):
                    covered_by.append(satellite_id)

        return covered_by

    def sample_route_coverage(
        self,
        waypoints: List[Tuple[float, float, datetime]],
        sample_interval_seconds: int = 60,
    ) -> List[CoverageEvent]:
        """Sample route for coverage entry/exit events.

        Walks through waypoints at specified interval and detects coverage changes.

        Args:
            waypoints: List of (lat, lon, timestamp) tuples
            sample_interval_seconds: Sampling interval in seconds (default: 60)

        Returns:
            List of CoverageEvent objects (entry/exit transitions)
        """
        if not waypoints or not self.satellite_polygons:
            return []

        events = []
        previous_coverage = set()

        for lat, lon, timestamp in waypoints:
            current_coverage = set(self.check_coverage_at_point(lat, lon))

            # Detect entries (new satellites in coverage)
            entries = current_coverage - previous_coverage
            for sat_id in entries:
                events.append(
                    CoverageEvent(
                        timestamp=timestamp,
                        event_type="entry",
                        satellite_id=sat_id,
                        latitude=lat,
                        longitude=lon,
                    )
                )

            # Detect exits (satellites no longer in coverage)
            exits = previous_coverage - current_coverage
            for sat_id in exits:
                events.append(
                    CoverageEvent(
                        timestamp=timestamp,
                        event_type="exit",
                        satellite_id=sat_id,
                        latitude=lat,
                        longitude=lon,
                    )
                )

            previous_coverage = current_coverage

        return events

    def estimate_coverage_fallback(
        self, satellite_lon: float, aircraft_lat: float, aircraft_lon: float
    ) -> float:
        """Estimate coverage using math-based elevation threshold (fallback).

        When GeoJSON polygons are unavailable, use simple elevation-based estimation.

        Args:
            satellite_lon: Satellite longitude (assumes equator)
            aircraft_lat: Aircraft latitude
            aircraft_lon: Aircraft longitude

        Returns:
            Estimated elevation angle in degrees (positive = visible, negative = blocked)

        Note:
            This is a simplified approximation and should only be used when
            actual coverage polygons are unavailable.
        """
        from app.satellites.geometry import look_angles

        azimuth, elevation = look_angles(aircraft_lat, aircraft_lon, 0, satellite_lon)
        return elevation

    def save_coverage_events(self, events: List[CoverageEvent], output_path: Path) -> None:
        """Save coverage events to JSON for caching/analysis.

        Args:
            events: List of CoverageEvent objects
            output_path: Path to save JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        event_dicts = [
            {
                "timestamp": event.timestamp.isoformat(),
                "event_type": event.event_type,
                "satellite_id": event.satellite_id,
                "latitude": event.latitude,
                "longitude": event.longitude,
                "metadata": event.metadata,
            }
            for event in events
        ]

        try:
            with open(output_path, "w") as f:
                json.dump(event_dicts, f, indent=2)
            logger.info(f"Saved {len(events)} coverage events to {output_path}")
        except IOError as e:
            logger.error(f"Failed to save coverage events: {e}")

    def load_coverage_events(self, input_path: Path) -> List[CoverageEvent]:
        """Load coverage events from JSON cache.

        Args:
            input_path: Path to JSON file

        Returns:
            List of CoverageEvent objects
        """
        if not input_path.exists():
            return []

        try:
            with open(input_path, "r") as f:
                event_dicts = json.load(f)

            events = [
                CoverageEvent(
                    timestamp=datetime.fromisoformat(e["timestamp"]),
                    event_type=e["event_type"],
                    satellite_id=e["satellite_id"],
                    latitude=e["latitude"],
                    longitude=e["longitude"],
                    metadata=e.get("metadata"),
                )
                for e in event_dicts
            ]
            logger.info(f"Loaded {len(events)} coverage events from {input_path}")
            return events
        except (IOError, json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to load coverage events: {e}")
            return []
