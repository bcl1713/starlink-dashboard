"""KML parsing module for route and waypoint extraction.

This module provides comprehensive KML parsing capabilities including:
- Geometry parsing (coordinates, line styles, placemarks)
- Route construction and segment chaining
- Waypoint identification and classification
- Timing data extraction and speed calculation
- Route validation
"""

from app.services.kml.parser import (
    parse_kml_file,
    extract_placemarks,
    partition_placemarks,
)
from app.services.kml.geometry import (
    CoordinateTriple,
    PlacemarkGeometry,
    LineStyleInfo,
    parse_geometry,
    parse_line_style,
    parse_coordinates,
    get_element_text,
    coordinates_match,
    deduplicate_coordinates,
    haversine_distance,
    KML_NS,
)
from app.services.kml.waypoints import (
    WaypointData,
    identify_primary_waypoints,
    match_waypoint_by_code,
    build_route_waypoints,
)
from app.services.kml.route_builder import (
    RouteSegmentData,
    build_primary_route,
    filter_segments_by_style,
    find_next_segment_index,
    flatten_route_segments,
)
from app.services.kml.timing import (
    extract_timestamp_from_description,
    assign_waypoint_timestamps_to_points,
    calculate_segment_speeds,
    build_route_timing_profile,
    TIMESTAMP_PATTERN,
)
from app.services.kml.validator import KMLParseError, validate_kml_file

__all__ = [
    # Parser
    "parse_kml_file",
    "extract_placemarks",
    "partition_placemarks",
    # Geometry
    "CoordinateTriple",
    "PlacemarkGeometry",
    "LineStyleInfo",
    "parse_geometry",
    "parse_line_style",
    "parse_coordinates",
    "get_element_text",
    "coordinates_match",
    "deduplicate_coordinates",
    "haversine_distance",
    "KML_NS",
    # Waypoints
    "WaypointData",
    "identify_primary_waypoints",
    "match_waypoint_by_code",
    "build_route_waypoints",
    # Route Builder
    "RouteSegmentData",
    "build_primary_route",
    "filter_segments_by_style",
    "find_next_segment_index",
    "flatten_route_segments",
    # Timing
    "extract_timestamp_from_description",
    "assign_waypoint_timestamps_to_points",
    "calculate_segment_speeds",
    "build_route_timing_profile",
    "TIMESTAMP_PATTERN",
    # Validator
    "KMLParseError",
    "validate_kml_file",
]
