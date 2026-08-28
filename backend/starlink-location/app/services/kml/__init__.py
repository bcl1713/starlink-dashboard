"""KML parsing module for route and waypoint extraction.

This module provides comprehensive KML parsing capabilities including:
- Geometry parsing (coordinates, line styles, placemarks)
- Route construction and segment chaining
- Waypoint identification and classification
- Timing data extraction and speed calculation
- Route validation
"""

from app.services.kml.geometry import (
    KML_NS,
    CoordinateTriple,
    LineStyleInfo,
    PlacemarkGeometry,
    coordinates_match,
    deduplicate_coordinates,
    get_element_text,
    haversine_distance,
    parse_coordinates,
    parse_geometry,
    parse_line_style,
)
from app.services.kml.parser import (
    extract_placemarks,
    parse_kml_file,
    partition_placemarks,
)
from app.services.kml.route_builder import (
    RouteSegmentData,
    build_primary_route,
    filter_segments_by_style,
    find_next_segment_index,
    flatten_route_segments,
)
from app.services.kml.timing import (
    TIMESTAMP_PATTERN,
    assign_waypoint_timestamps_to_points,
    build_route_timing_profile,
    calculate_segment_speeds,
    extract_timestamp_from_description,
)
from app.services.kml.validator import KMLParseError, validate_kml_file
from app.services.kml.waypoints import (
    WaypointData,
    build_route_waypoints,
    identify_primary_waypoints,
    match_waypoint_by_code,
)

__all__ = [
    "KML_NS",
    "TIMESTAMP_PATTERN",
    # Geometry
    "CoordinateTriple",
    # Validator
    "KMLParseError",
    "LineStyleInfo",
    "PlacemarkGeometry",
    # Route Builder
    "RouteSegmentData",
    # Waypoints
    "WaypointData",
    "assign_waypoint_timestamps_to_points",
    "build_primary_route",
    "build_route_timing_profile",
    "build_route_waypoints",
    "calculate_segment_speeds",
    "coordinates_match",
    "deduplicate_coordinates",
    "extract_placemarks",
    # Timing
    "extract_timestamp_from_description",
    "filter_segments_by_style",
    "find_next_segment_index",
    "flatten_route_segments",
    "get_element_text",
    "haversine_distance",
    "identify_primary_waypoints",
    "match_waypoint_by_code",
    "parse_coordinates",
    "parse_geometry",
    # Parser
    "parse_kml_file",
    "parse_line_style",
    "partition_placemarks",
    "validate_kml_file",
]
