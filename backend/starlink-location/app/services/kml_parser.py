"""KML file parser for converting KML routes to ParsedRoute objects.

This module provides backward compatibility by re-exporting functionality
from the app.services.kml submodule.
"""

# Re-export everything from the kml module for backward compatibility
from app.services.kml import (
    parse_kml_file,
    validate_kml_file,
    KMLParseError,
    extract_timestamp_from_description,
    TIMESTAMP_PATTERN,
    CoordinateTriple,
    PlacemarkGeometry,
    LineStyleInfo,
    WaypointData,
    RouteSegmentData,
    haversine_distance,
)

__all__ = [
    "parse_kml_file",
    "validate_kml_file",
    "KMLParseError",
    "extract_timestamp_from_description",
    "TIMESTAMP_PATTERN",
    "CoordinateTriple",
    "PlacemarkGeometry",
    "LineStyleInfo",
    "WaypointData",
    "RouteSegmentData",
    "haversine_distance",
]
