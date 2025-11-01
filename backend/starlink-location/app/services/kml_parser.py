"""KML file parser for converting KML routes to ParsedRoute objects."""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteWaypoint

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


@dataclass
class CoordinateTriple:
    """Represents a single coordinate triple in KML."""

    longitude: float
    latitude: float
    altitude: Optional[float] = None


@dataclass
class PlacemarkGeometry:
    """Geometry data extracted from a Placemark."""

    kind: str
    coordinates: list[CoordinateTriple]
    altitude_mode: Optional[str] = None


@dataclass
class LineStyleInfo:
    """Line style attributes declared on a Placemark."""

    color: Optional[str] = None
    width: Optional[float] = None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class PlacemarkData:
    """Lightweight representation of a Placemark for downstream processing."""

    name: Optional[str]
    description: Optional[str]
    style_url: Optional[str]
    geometry: Optional[PlacemarkGeometry]
    line_style: Optional[LineStyleInfo]
    order: int


@dataclass
class WaypointData:
    """Represents a waypoint placemark extracted from the KML document."""

    name: Optional[str]
    description: Optional[str]
    style_url: Optional[str]
    coordinate: Optional[CoordinateTriple]
    altitude_mode: Optional[str]
    order: int


@dataclass
class RouteSegmentData:
    """Represents a line segment placemark for the planned route."""

    name: Optional[str]
    description: Optional[str]
    style: Optional[LineStyleInfo]
    coordinates: list[CoordinateTriple]
    altitude_mode: Optional[str]
    order: int


class KMLParseError(Exception):
    """Raised when KML parsing fails."""

    pass


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
    doc_name = _get_element_text(root, "kml:name")

    # Also try to get from Document element if it exists
    if not doc_name:
        doc_elem = root.find("kml:Document", KML_NS)
        if doc_elem is not None:
            doc_name = _get_element_text(doc_elem, "kml:name")

    doc_description = _get_element_text(root, "kml:description")
    if not doc_description:
        doc_elem = root.find("kml:Document", KML_NS)
        if doc_elem is not None:
            doc_description = _get_element_text(doc_elem, "kml:description")

    route_name = doc_name or "Unknown Route"
    route_description = doc_description

    placemarks = _extract_placemarks(root)
    logger.debug(
        "Parsed %d placemarks from %s", len(placemarks), file_path.name
    )

    waypoints, route_segments = _partition_placemarks(placemarks)
    logger.debug(
        "Classified %d waypoint placemarks and %d route segments",
        len(waypoints),
        len(route_segments),
    )

    departure_wp, arrival_wp = _identify_primary_waypoints(route_name, waypoints)

    primary_coords = _build_primary_route(
        route_segments=route_segments,
        start_coord=departure_wp.coordinate if departure_wp and departure_wp.coordinate else None,
        end_coord=arrival_wp.coordinate if arrival_wp and arrival_wp.coordinate else None,
    )

    if not primary_coords:
        logger.warning(
            "Falling back to legacy route flattening for %s; "
            "could not determine primary path from %d segments",
            file_path.name,
            len(route_segments),
        )
        primary_coords = _flatten_route_segments(route_segments)
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

    route_waypoints = _build_route_waypoints(
        waypoints=waypoints,
        departure_wp=departure_wp,
        arrival_wp=arrival_wp,
    )

    # Create metadata
    metadata = RouteMetadata(
        name=route_name,
        description=route_description,
        file_path=str(file_path.absolute()),
        point_count=len(points),
    )

    # Create ParsedRoute
    parsed_route = ParsedRoute(metadata=metadata, points=points, waypoints=route_waypoints)

    logger.info(
        f"Successfully parsed KML file: {file_path} with {len(points)} points, "
        f"route name: {route_name}"
    )

    return parsed_route


def _get_element_text(element: ET.Element, tag: str) -> Optional[str]:
    """
    Get text content from an XML element.

    Args:
        element: XML element to search
        tag: Tag name (with namespace if needed, e.g., "kml:name")

    Returns:
        Text content or None if not found
    """
    elem = element.find(tag, KML_NS)
    if elem is None or elem.text is None:
        return None
    return elem.text.strip() or None


def _extract_placemarks(root: ET.Element) -> list[PlacemarkData]:
    """Extract placemarks in document order into structured data."""
    placemarks: list[PlacemarkData] = []

    for index, placemark_elem in enumerate(root.findall(".//kml:Placemark", KML_NS)):
        name = _get_element_text(placemark_elem, "kml:name")
        description = _get_element_text(placemark_elem, "kml:description")
        style_url = _get_element_text(placemark_elem, "kml:styleUrl")
        geometry = _parse_geometry(placemark_elem)
        line_style = _parse_line_style(placemark_elem)

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


def _parse_geometry(placemark_elem: ET.Element) -> Optional[PlacemarkGeometry]:
    """Parse geometry for a Placemark."""
    point_elem = placemark_elem.find("kml:Point", KML_NS)
    if point_elem is not None:
        coords_elem = point_elem.find("kml:coordinates", KML_NS)
        if coords_elem is None or not coords_elem.text:
            return None
        coordinates = _parse_coordinates(coords_elem.text)
        altitude_mode = _get_element_text(point_elem, "kml:altitudeMode")
        return PlacemarkGeometry(
            kind="Point",
            coordinates=coordinates,
            altitude_mode=altitude_mode,
        )

    linestring_elem = placemark_elem.find("kml:LineString", KML_NS)
    if linestring_elem is not None:
        coords_elem = linestring_elem.find("kml:coordinates", KML_NS)
        if coords_elem is None or not coords_elem.text:
            return None
        coordinates = _parse_coordinates(coords_elem.text)
        altitude_mode = _get_element_text(linestring_elem, "kml:altitudeMode")
        return PlacemarkGeometry(
            kind="LineString",
            coordinates=coordinates,
            altitude_mode=altitude_mode,
        )

    # Additional geometries can be added here as needed
    return None


def _parse_line_style(placemark_elem: ET.Element) -> Optional[LineStyleInfo]:
    """Parse inline LineStyle data if present on the Placemark."""
    linestring_style = placemark_elem.find("kml:Style/kml:LineStyle", KML_NS)
    if linestring_style is None:
        return None

    color = _get_element_text(linestring_style, "kml:color")

    width_text = _get_element_text(linestring_style, "kml:width")
    width = None
    if width_text:
        try:
            width = float(width_text)
        except ValueError:
            logger.debug("Ignoring non-numeric LineStyle width: %s", width_text)

    extra: dict[str, str] = {}
    for child in list(linestring_style):
        tag = child.tag
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        if tag not in {"color", "width"} and child.text:
            extra[tag] = child.text.strip()

    return LineStyleInfo(color=color, width=width, extra=extra)


def _parse_coordinates(coords_text: str) -> list[CoordinateTriple]:
    """Parse a whitespace-separated coordinate string into triples."""
    coordinates: list[CoordinateTriple] = []
    text = coords_text.strip()
    for coord_str in text.split():
        parts = coord_str.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
            altitude = float(parts[2]) if len(parts) > 2 and parts[2] else None
        except ValueError:
            logger.warning("Failed to parse coordinate: %s", coord_str)
            continue
        coordinates.append(CoordinateTriple(longitude=lon, latitude=lat, altitude=altitude))

    return coordinates


def _partition_placemarks(
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


def _identify_primary_waypoints(
    route_name: Optional[str], waypoints: list[WaypointData]
) -> tuple[Optional[WaypointData], Optional[WaypointData]]:
    """Identify likely departure and arrival waypoints based on metadata."""
    departure_code: Optional[str] = None
    arrival_code: Optional[str] = None

    if route_name:
        route_name_upper = route_name.upper()
        match = re.search(r"\b([A-Z0-9]{3,5})[-→]+([A-Z0-9]{3,5})\b", route_name_upper)
        if match:
            departure_code, arrival_code = match.group(1), match.group(2)

    departure_wp = _match_waypoint_by_code(waypoints, departure_code, prefer_last=False)
    arrival_wp = _match_waypoint_by_code(waypoints, arrival_code, prefer_last=True)

    if departure_wp is None:
        departure_wp = next((wp for wp in waypoints if wp.coordinate is not None), None)

    if arrival_wp is None:
        arrival_wp = next(
            (wp for wp in reversed(waypoints) if wp.coordinate is not None),
            None,
        )

    return departure_wp, arrival_wp


def _match_waypoint_by_code(
    waypoints: list[WaypointData],
    code: Optional[str],
    *,
    prefer_last: bool,
) -> Optional[WaypointData]:
    """Find a waypoint whose name matches the supplied code."""
    if not code:
        return None

    code_upper = code.upper()
    iterator = reversed(waypoints) if prefer_last else iter(waypoints)

    for waypoint in iterator:
        if waypoint.name and waypoint.coordinate:
            if waypoint.name.upper() == code_upper:
                return waypoint

    return None


def _build_route_waypoints(
    waypoints: list[WaypointData],
    departure_wp: Optional[WaypointData],
    arrival_wp: Optional[WaypointData],
) -> list[RouteWaypoint]:
    """Convert waypoint data into RouteWaypoint models with basic role tagging."""
    route_waypoints: list[RouteWaypoint] = []

    for waypoint in waypoints:
        coord = waypoint.coordinate
        if coord is None:
            continue

        role: Optional[str] = None
        if departure_wp and waypoint.order == departure_wp.order:
            role = "departure"
        elif arrival_wp and waypoint.order == arrival_wp.order:
            role = "arrival"
        elif waypoint.style_url:
            style_lower = waypoint.style_url.lower()
            if "alt" in style_lower:
                role = "alternate"
            elif "dest" in style_lower:
                role = "waypoint"

        route_waypoints.append(
            RouteWaypoint(
                name=waypoint.name,
                description=waypoint.description,
                style_url=waypoint.style_url,
                latitude=coord.latitude,
                longitude=coord.longitude,
                altitude=coord.altitude,
                order=waypoint.order,
                role=role,
            )
        )

    return route_waypoints


def _build_primary_route(
    route_segments: list[RouteSegmentData],
    start_coord: Optional[CoordinateTriple],
    end_coord: Optional[CoordinateTriple],
) -> list[CoordinateTriple]:
    """Construct the primary coordinate chain from the available segments."""
    segments_remaining = [seg for seg in route_segments if seg.coordinates]
    if not segments_remaining:
        return []

    path: list[CoordinateTriple] = []
    current = None

    if start_coord:
        path.append(start_coord)
        current = start_coord
    else:
        first_segment = segments_remaining.pop(0)
        path.extend(first_segment.coordinates)
        current = first_segment.coordinates[-1]

    safety_counter = 0
    max_iterations = len(segments_remaining) + 1

    while segments_remaining and safety_counter <= max_iterations:
        idx, reverse_needed = _find_next_segment_index(segments_remaining, current)
        if idx is None:
            break

        segment = segments_remaining.pop(idx)
        coords_sequence = segment.coordinates
        if reverse_needed:
            coords_sequence = list(reversed(coords_sequence))

        if not path:
            path.extend(coords_sequence)
        else:
            path.extend(coords_sequence[1:])

        current = coords_sequence[-1]
        safety_counter += 1

        if end_coord and _coordinates_match(current, end_coord):
            break

    deduped_path = _deduplicate_coordinates(path)

    if len(deduped_path) < 2:
        return []

    if end_coord and not _coordinates_match(deduped_path[-1], end_coord):
        return []

    return deduped_path


def _find_next_segment_index(
    segments: list[RouteSegmentData],
    current: Optional[CoordinateTriple],
) -> tuple[Optional[int], bool]:
    """Locate the next segment that connects to the current coordinate."""
    if current is None:
        return None, False

    for idx, segment in enumerate(segments):
        if not segment.coordinates:
            continue

        first = segment.coordinates[0]
        last = segment.coordinates[-1]

        if _coordinates_match(first, current):
            return idx, False

        if _coordinates_match(last, current):
            return idx, True

    return None, False


def _coordinates_match(
    coord_a: Optional[CoordinateTriple],
    coord_b: Optional[CoordinateTriple],
    tolerance: float = 1e-6,
) -> bool:
    """Check if two coordinates refer to the same location within tolerance."""
    if coord_a is None or coord_b is None:
        return False

    return (
        abs(coord_a.latitude - coord_b.latitude) <= tolerance
        and abs(coord_a.longitude - coord_b.longitude) <= tolerance
    )


def _deduplicate_coordinates(
    coordinates: list[CoordinateTriple],
) -> list[CoordinateTriple]:
    """Remove consecutive duplicate coordinates."""
    deduped: list[CoordinateTriple] = []

    for coord in coordinates:
        if not deduped or not _coordinates_match(deduped[-1], coord):
            deduped.append(coord)

    return deduped


def _flatten_route_segments(route_segments: list[RouteSegmentData]) -> list[CoordinateTriple]:
    """Fallback: concatenate all segment coordinates in document order."""
    combined: list[CoordinateTriple] = []

    for segment in sorted(route_segments, key=lambda seg: seg.order):
        if not combined:
            combined.extend(segment.coordinates)
        else:
            combined.extend(segment.coordinates)

    return _deduplicate_coordinates(combined)


def validate_kml_file(file_path: str | Path) -> tuple[bool, Optional[str]]:
    """
    Validate a KML file without fully parsing it.

    Args:
        file_path: Path to KML file

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parse_kml_file(file_path)
        return True, None
    except KMLParseError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"
