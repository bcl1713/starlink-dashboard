"""KML file parser for converting KML routes to ParsedRoute objects."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.services.kml.geometry import PlacemarkGeometry, LineStyleInfo

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.kml.geometry import (
    get_element_text,
    parse_geometry,
    parse_line_style,
    KML_NS,
)
from app.services.kml.waypoints import (
    WaypointData,
    identify_primary_waypoints,
    build_route_waypoints,
)
from app.services.kml.route_builder import (
    RouteSegmentData,
    build_primary_route,
    flatten_route_segments,
)
from app.services.kml.timing import (
    assign_waypoint_timestamps_to_points,
    calculate_segment_speeds,
    build_route_timing_profile,
)
from app.services.kml.validator import KMLParseError

logger = logging.getLogger(__name__)


@dataclass
class PlacemarkData:
    """Lightweight representation of a Placemark for downstream processing."""

    name: Optional[str]
    description: Optional[str]
    style_url: Optional[str]
    geometry: Optional[PlacemarkGeometry]
    line_style: Optional[LineStyleInfo]
    order: int


def parse_kml_file(file_path: str | Path) -> Optional[ParsedRoute]:
    """
    Parse a KML file and convert to ParsedRoute object.

    Args:
        file_path: Path to KML file

    Returns:
        ParsedRoute object or None if parsing fails

    Raises:
        KMLParseError: If the KML file is invalid or cannot be parsed
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise KMLParseError(f"KML file not found: {file_path}")

    if not file_path.suffix.lower() == ".kml":
        raise KMLParseError(f"File is not a KML file: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except IOError as e:
        raise KMLParseError(f"Failed to read KML file: {e}")

    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise KMLParseError(f"Failed to parse KML: {e}")

    # Extract name and description from document (could be in Document or Folder)
    doc_name = get_element_text(root, "kml:name")

    # Also try to get from Document element if it exists
    if not doc_name:
        doc_elem = root.find("kml:Document", KML_NS)
        if doc_elem is not None:
            doc_name = get_element_text(doc_elem, "kml:name")

    doc_description = get_element_text(root, "kml:description")
    if not doc_description:
        doc_elem = root.find("kml:Document", KML_NS)
        if doc_elem is not None:
            doc_description = get_element_text(doc_elem, "kml:description")

    route_name = doc_name or "Unknown Route"
    route_description = doc_description

    placemarks = extract_placemarks(root)
    logger.debug("Parsed %d placemarks from %s", len(placemarks), file_path.name)

    waypoints, route_segments = partition_placemarks(placemarks)
    logger.debug(
        "Classified %d waypoint placemarks and %d route segments",
        len(waypoints),
        len(route_segments),
    )

    departure_wp, arrival_wp = identify_primary_waypoints(route_name, waypoints)

    primary_coords = build_primary_route(
        route_segments=route_segments,
        start_coord=(
            departure_wp.coordinate
            if departure_wp and departure_wp.coordinate
            else None
        ),
        end_coord=(
            arrival_wp.coordinate if arrival_wp and arrival_wp.coordinate else None
        ),
    )

    if not primary_coords:
        logger.warning(
            "Falling back to legacy route flattening for %s; "
            "could not determine primary path from %d segments",
            file_path.name,
            len(route_segments),
        )
        primary_coords = flatten_route_segments(route_segments)
    else:
        logger.info(
            "Identified primary route with %d coordinates (start=%s, end=%s)",
            len(primary_coords),
            departure_wp.name if departure_wp else "unknown",
            arrival_wp.name if arrival_wp else "unknown",
        )

    # Convert coordinates to RoutePoint list
    points: list[RoutePoint] = []
    point_sequence = 0

    if not primary_coords:
        raise KMLParseError("No coordinate data found in KML file")

    for coord in primary_coords:
        points.append(
            RoutePoint(
                latitude=coord.latitude,
                longitude=coord.longitude,
                altitude=coord.altitude,
                sequence=point_sequence,
            )
        )
        point_sequence += 1

    route_waypoints = build_route_waypoints(
        waypoints=waypoints,
        departure_wp=departure_wp,
        arrival_wp=arrival_wp,
    )

    # Map waypoint timestamps to route points based on proximity
    assign_waypoint_timestamps_to_points(points, route_waypoints)

    # Calculate expected segment speeds from timestamps
    calculate_segment_speeds(points)

    # Build route-level timing profile
    timing_profile = build_route_timing_profile(route_name, points, route_waypoints)

    # Create metadata
    metadata = RouteMetadata(
        name=route_name,
        description=route_description,
        file_path=str(file_path.absolute()),
        point_count=len(points),
    )

    # Create ParsedRoute with timing profile
    parsed_route = ParsedRoute(
        metadata=metadata,
        points=points,
        waypoints=route_waypoints,
        timing_profile=timing_profile,
    )

    logger.info(
        f"Successfully parsed KML file: {file_path} with {len(points)} points, "
        f"route name: {route_name}"
    )

    return parsed_route


def extract_placemarks(root: ET.Element) -> list[PlacemarkData]:
    """Extract placemarks in document order into structured data."""
    placemarks: list[PlacemarkData] = []

    for index, placemark_elem in enumerate(root.findall(".//kml:Placemark", KML_NS)):
        name = get_element_text(placemark_elem, "kml:name")
        description = get_element_text(placemark_elem, "kml:description")
        style_url = get_element_text(placemark_elem, "kml:styleUrl")
        geometry = parse_geometry(placemark_elem)
        line_style = parse_line_style(placemark_elem)

        placemarks.append(
            PlacemarkData(
                name=name,
                description=description,
                style_url=style_url,
                geometry=geometry,
                line_style=line_style,
                order=index,
            )
        )

    return placemarks


def partition_placemarks(
    placemarks: list[PlacemarkData],
) -> tuple[list[WaypointData], list[RouteSegmentData]]:
    """Split placemarks into waypoint and route segment collections."""
    waypoints: list[WaypointData] = []
    segments: list[RouteSegmentData] = []

    for placemark in placemarks:
        geometry = placemark.geometry
        if geometry is None:
            continue

        if geometry.kind == "Point":
            coordinate = geometry.coordinates[0] if geometry.coordinates else None
            waypoints.append(
                WaypointData(
                    name=placemark.name,
                    description=placemark.description,
                    style_url=placemark.style_url,
                    coordinate=coordinate,
                    altitude_mode=geometry.altitude_mode,
                    order=placemark.order,
                )
            )
        elif geometry.kind == "LineString":
            segments.append(
                RouteSegmentData(
                    name=placemark.name,
                    description=placemark.description,
                    style=placemark.line_style,
                    coordinates=geometry.coordinates,
                    altitude_mode=geometry.altitude_mode,
                    order=placemark.order,
                )
            )

    # Preserve document order by sorting on order index (defensive)
    waypoints.sort(key=lambda w: w.order)
    segments.sort(key=lambda s: s.order)

    return waypoints, segments
