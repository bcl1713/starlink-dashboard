"""KML file parser for converting KML routes to ParsedRoute objects.

This module provides backward compatibility by re-exporting functionality
from the app.services.kml submodule.
"""

# Re-export everything from the kml module for backward compatibility
from app.services.kml import (
    TIMESTAMP_PATTERN,
    CoordinateTriple,
    KMLParseError,
    LineStyleInfo,
    PlacemarkGeometry,
    RouteSegmentData,
    WaypointData,
    extract_timestamp_from_description,
    haversine_distance,
    parse_kml_file,
    validate_kml_file,
)

__all__ = [
    "TIMESTAMP_PATTERN",
    "CoordinateTriple",
    "KMLParseError",
    "LineStyleInfo",
    "PlacemarkGeometry",
    "RouteSegmentData",
    "WaypointData",
    "extract_timestamp_from_description",
    "haversine_distance",
    "parse_kml_file",
    "validate_kml_file",
]
