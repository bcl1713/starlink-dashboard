"""KML file parser for converting KML routes to ParsedRoute objects."""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint, RouteWaypoint

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}

# Regex pattern for extracting timestamps from waypoint descriptions
TIMESTAMP_PATTERN = re.compile(
    r"Time Over Waypoint:\s*(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})Z"
)


def extract_timestamp_from_description(
    description: Optional[str],
) -> Optional[datetime]:
    """
    Extract timestamp from waypoint description.

    Looks for pattern: "Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ"

    Args:
        description: Waypoint description text

    Returns:
        datetime object if timestamp found and valid, None otherwise

    Example:
        >>> desc = "Airport\\n Time Over Waypoint: 2025-10-27 16:51:13Z"
        >>> ts = extract_timestamp_from_description(desc)
        >>> ts.isoformat()
        '2025-10-27T16:51:13'
    """
    if not description:
        return None

    match = TIMESTAMP_PATTERN.search(description)
    if not match:
        return None

    try:
        timestamp_str = match.group(1)
        # Parse format: "2025-10-27 16:51:13"
        return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError) as e:
        logger.debug(f"Failed to parse timestamp from description: {e}")
        return None


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
    logger.debug("Parsed %d placemarks from %s", len(placemarks), file_path.name)

    waypoints, route_segments = _partition_placemarks(placemarks)
    logger.debug(
        "Classified %d waypoint placemarks and %d route segments",
        len(waypoints),
        len(route_segments),
    )

    departure_wp, arrival_wp = _identify_primary_waypoints(route_name, waypoints)

    primary_coords = _build_primary_route(
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

    # Map waypoint timestamps to route points based on proximity
    _assign_waypoint_timestamps_to_points(points, route_waypoints)

    # Calculate expected segment speeds from timestamps
    _calculate_segment_speeds(points)

    # Build route-level timing profile
    timing_profile = _build_route_timing_profile(route_name, points, route_waypoints)

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
        coordinates.append(
            CoordinateTriple(longitude=lon, latitude=lat, altitude=altitude)
        )

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
    """
    Identify departure and arrival waypoints from route name.

    Parses route name in format "DEPARTURE-ARRIVAL" (e.g., "RKSO-KADW").
    Falls back to first/last waypoint with #destWaypointIcon style if parsing fails.

    Returns:
        Tuple of (departure_wp, arrival_wp)
    """
    departure_code: Optional[str] = None
    arrival_code: Optional[str] = None

    # Extract airport codes from route name (e.g., "RKSO-KADW" → RKSO, KADW)
    if route_name:
        route_name_upper = route_name.upper()
        match = re.search(r"\b([A-Z0-9]{3,5})[-→]+([A-Z0-9]{3,5})\b", route_name_upper)
        if match:
            departure_code, arrival_code = match.group(1), match.group(2)
            logger.info("Parsed route name: %s → %s", departure_code, arrival_code)

    # Try to match waypoints by code
    departure_wp = _match_waypoint_by_code(waypoints, departure_code, prefer_last=False)
    arrival_wp = _match_waypoint_by_code(waypoints, arrival_code, prefer_last=True)

    # Fallback: find first/last waypoint with #destWaypointIcon style
    if departure_wp is None:
        departure_wp = next(
            (
                wp
                for wp in waypoints
                if wp.coordinate is not None
                and wp.style_url
                and "dest" in wp.style_url.lower()
            ),
            None,
        )

    if arrival_wp is None:
        arrival_wp = next(
            (
                wp
                for wp in reversed(waypoints)
                if wp.coordinate is not None
                and wp.style_url
                and "dest" in wp.style_url.lower()
            ),
            None,
        )

    # Final fallback: use first/last waypoint with any coordinate
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


def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate approximate distance between two points using haversine formula.

    Args:
        lat1, lon1: First point coordinates in degrees
        lat2, lon2: Second point coordinates in degrees

    Returns:
        Distance in meters (approximate, using Earth radius = 6371 km)
    """
    from math import radians, cos, sin, asin, sqrt

    # Convert degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371000  # Earth radius in meters

    return c * r


def _assign_waypoint_timestamps_to_points(
    points: list[RoutePoint],
    waypoints: list[RouteWaypoint],
) -> None:
    """
    Assign waypoint timestamps to the nearest route points.

    For each waypoint with a timestamp, find the closest route point and assign the timestamp.
    This creates a mapping of specific times to specific locations along the route.

    Args:
        points: List of RoutePoint objects to be updated in-place
        waypoints: List of RouteWaypoint objects with extracted timestamps
    """
    # Build a list of waypoints with timestamps
    timed_waypoints = [wp for wp in waypoints if wp.expected_arrival_time is not None]

    if not timed_waypoints:
        logger.debug(
            "No waypoints with timestamps found; skipping timestamp assignment"
        )
        return

    logger.debug(
        f"Assigning timestamps from {len(timed_waypoints)} waypoints to route points"
    )

    # For each timed waypoint, find the nearest route point
    for waypoint in timed_waypoints:
        if points:
            # Find closest point by calculating haversine distance
            min_distance = float("inf")
            closest_point = None

            for point in points:
                distance = _haversine_distance(
                    waypoint.latitude,
                    waypoint.longitude,
                    point.latitude,
                    point.longitude,
                )
                if distance < min_distance:
                    min_distance = distance
                    closest_point = point

            # Assign timestamp if we found a point (within reasonable tolerance, ~1000m)
            if closest_point is not None and min_distance < 1000:
                closest_point.expected_arrival_time = waypoint.expected_arrival_time
                logger.debug(
                    f"Assigned timestamp {waypoint.expected_arrival_time} to point "
                    f"({closest_point.latitude}, {closest_point.longitude}) "
                    f"(distance: {min_distance:.0f}m from waypoint {waypoint.name})"
                )


def _calculate_segment_speeds(points: list[RoutePoint]) -> None:
    """
    Calculate expected speeds for segments between consecutive points with timing.

    For each pair of consecutive points where both have timestamps, calculates the
    speed using the haversine distance and time delta. Stores speed in the second
    point of each pair.

    Formula: speed_knots = distance_meters / time_seconds * (3600 / 1852)
    (converts m/s to knots: 1 knot = 1852 m / 3600 s)

    Args:
        points: List of RoutePoint objects to update in-place
    """
    if len(points) < 2:
        logger.debug("Insufficient points for speed calculation (need at least 2)")
        return

    speeds_calculated = 0

    for i in range(1, len(points)):
        prev_point = points[i - 1]
        curr_point = points[i]

        # Both points must have timestamps to calculate speed
        if (
            prev_point.expected_arrival_time is None
            or curr_point.expected_arrival_time is None
        ):
            continue

        # Calculate time delta in seconds
        time_delta = curr_point.expected_arrival_time - prev_point.expected_arrival_time
        time_seconds = time_delta.total_seconds()

        # Skip if time delta is zero or negative (invalid)
        if time_seconds <= 0:
            logger.debug(
                f"Skipping segment {i-1}->{i}: invalid time delta ({time_seconds}s)"
            )
            continue

        # Calculate distance in meters
        distance_meters = _haversine_distance(
            prev_point.latitude,
            prev_point.longitude,
            curr_point.latitude,
            curr_point.longitude,
        )

        # Calculate speed: convert m/s to knots (1 knot = 1852 m / 3600 s)
        speed_ms = distance_meters / time_seconds
        speed_knots = speed_ms * (3600 / 1852)

        # Store speed in the current (end) point
        curr_point.expected_segment_speed_knots = speed_knots
        speeds_calculated += 1

        logger.debug(
            f"Segment {i-1}->{i}: {distance_meters:.0f}m in {time_seconds:.0f}s = {speed_knots:.1f} knots"
        )

    logger.debug(f"Calculated speeds for {speeds_calculated} segments")


def _build_route_timing_profile(
    route_name: str,
    points: list[RoutePoint],
    waypoints: list[RouteWaypoint],
) -> Optional["RouteTimingProfile"]:
    """
    Build RouteTimingProfile with departure/arrival times and total duration.

    Extracts departure code from route name (e.g., "KADW" from "KADW-PHNL") and
    finds corresponding departure and arrival timestamps from waypoints and points.

    Args:
        route_name: Route name (e.g., "Flight Plan KADW-PHNL")
        points: List of RoutePoint objects with assigned timestamps
        waypoints: List of RouteWaypoint objects with extracted timestamps

    Returns:
        RouteTimingProfile with timing data, or None if insufficient timing information
    """
    # Import here to avoid circular dependency
    from app.models.route import RouteTimingProfile

    # Extract airport codes from route name (format: "...XXXX-YYYY" or "XXXX-YYYY")
    # Look for pattern like "KADW-PHNL" in the route name
    import re

    airport_pattern = re.search(r"([A-Z]{3,4})-([A-Z]{3,4})", route_name)

    if not airport_pattern:
        logger.debug(f"Could not extract airport codes from route name: {route_name}")
        return None

    departure_code = airport_pattern.group(1)
    arrival_code = airport_pattern.group(2)

    # Find departure waypoint matching the departure code
    departure_waypoint = None
    for wp in waypoints:
        if wp.name and wp.name.upper() == departure_code:
            departure_waypoint = wp
            break

    # Find first point with timestamp (departure time)
    departure_time = None
    if departure_waypoint and departure_waypoint.expected_arrival_time:
        departure_time = departure_waypoint.expected_arrival_time
    else:
        # Fallback: find first point with any timestamp
        for point in points:
            if point.expected_arrival_time:
                departure_time = point.expected_arrival_time
                break

    # Find arrival waypoint and time
    arrival_waypoint = None
    for wp in waypoints:
        if wp.name and wp.name.upper() == arrival_code:
            arrival_waypoint = wp
            break

    # Find last point with timestamp (arrival time)
    arrival_time = None
    if arrival_waypoint and arrival_waypoint.expected_arrival_time:
        arrival_time = arrival_waypoint.expected_arrival_time
    else:
        # Fallback: find last point with any timestamp
        for point in reversed(points):
            if point.expected_arrival_time:
                arrival_time = point.expected_arrival_time
                break

    # Count how many points have timing information
    points_with_timing = sum(1 for p in points if p.expected_arrival_time is not None)

    # If we have at least some timing information, create the profile
    if departure_time is not None or arrival_time is not None or points_with_timing > 0:
        # Calculate total duration if we have both times
        total_duration_seconds = None
        if departure_time and arrival_time:
            duration = arrival_time - departure_time
            total_duration_seconds = duration.total_seconds()

        timing_profile = RouteTimingProfile(
            departure_time=departure_time,
            arrival_time=arrival_time,
            total_expected_duration_seconds=total_duration_seconds,
            has_timing_data=points_with_timing > 0,
            segment_count_with_timing=sum(
                1 for p in points if p.expected_segment_speed_knots is not None
            ),
        )

        logger.info(
            f"Created timing profile for {route_name}: "
            f"departure={departure_time}, arrival={arrival_time}, "
            f"duration={total_duration_seconds}s, points_with_timing={points_with_timing}"
        )

        return timing_profile

    logger.debug(f"Insufficient timing data for route {route_name}")
    return None


def _build_route_waypoints(
    waypoints: list[WaypointData],
    departure_wp: Optional[WaypointData],
    arrival_wp: Optional[WaypointData],
) -> list[RouteWaypoint]:
    """Convert waypoint data into RouteWaypoint models with basic role tagging and timing extraction."""
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

        # Extract timestamp from waypoint description
        expected_arrival_time = extract_timestamp_from_description(waypoint.description)

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
                expected_arrival_time=expected_arrival_time,
            )
        )

    return route_waypoints


def _filter_segments_by_style(
    segments: list[RouteSegmentData],
) -> list[RouteSegmentData]:
    """
    Filter route segments to only include the main route (exclude alternates).

    Flight planning software (like ForeFlight/RocketRoute) exports routes with:
    - Main route segments: color ffddad05 (orange/gold)
    - Alternate segments: color ffb3b3b3 (gray)

    This function filters to keep only the main route segments.

    Args:
        segments: All route segments extracted from KML file

    Returns:
        Filtered list containing only main route segments, or all segments if no color match
    """
    # Main route color from ForeFlight/RocketRoute export format
    main_route_color = "ffddad05"

    # Debug: log all colors found
    color_counts = {}
    for seg in segments:
        if seg.style and seg.style.color:
            color = seg.style.color.lower()
            color_counts[color] = color_counts.get(color, 0) + 1
        else:
            color_counts["(no color)"] = color_counts.get("(no color)", 0) + 1

    if color_counts:
        logger.debug("Segment colors: %s", color_counts)

    main_segments = [
        seg
        for seg in segments
        if seg.style
        and seg.style.color
        and seg.style.color.lower() == main_route_color.lower()
    ]

    if main_segments:
        logger.info(
            "Filtered segments by style: %d main route (ffddad05) from %d total",
            len(main_segments),
            len(segments),
        )
        return main_segments

    # Fallback: if no colored segments found, return all segments
    logger.warning(
        "No main route segments (ffddad05) found in %d segments; returning all",
        len(segments),
    )
    return segments


def _build_primary_route(
    route_segments: list[RouteSegmentData],
    start_coord: Optional[CoordinateTriple],
    end_coord: Optional[CoordinateTriple],
) -> list[CoordinateTriple]:
    """Construct the primary coordinate chain from the available segments."""
    # Filter segments to only include the main route (by color/style)
    filtered_segments = _filter_segments_by_style(route_segments)

    segments_remaining = [seg for seg in filtered_segments if seg.coordinates]
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
            # Color-filtered segments don't connect properly. Return empty to
            # trigger legacy fallback, which will use all segments regardless of color
            logger.debug(
                "Color-filtered segments did not chain properly; "
                "%d segments remaining, current=%s",
                len(segments_remaining),
                (
                    f"({current.latitude:.6f},{current.longitude:.6f})"
                    if current
                    else "None"
                ),
            )
            return []

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
    tolerance: float = 1e-4,
) -> bool:
    """Check if two coordinates refer to the same location within tolerance.

    Tolerance of 1e-4 degrees (~10 meters at equator) allows for coordinate
    variations in KML segment boundaries while still being geographically precise.

    Handles International Dateline crossing: when comparing longitudes that wrap
    around ±180°, calculates shortest distance across the dateline.
    """
    if coord_a is None or coord_b is None:
        return False

    # Check latitude
    lat_diff = abs(coord_a.latitude - coord_b.latitude)
    if lat_diff > tolerance:
        return False

    # Check longitude with dateline wraparound handling
    lon_diff = abs(coord_a.longitude - coord_b.longitude)
    # If difference is > 180°, it's shorter to cross the dateline
    if lon_diff > 180:
        lon_diff = 360 - lon_diff

    return lon_diff <= tolerance


def _deduplicate_coordinates(
    coordinates: list[CoordinateTriple],
) -> list[CoordinateTriple]:
    """Remove consecutive duplicate coordinates."""
    deduped: list[CoordinateTriple] = []

    for coord in coordinates:
        if not deduped or not _coordinates_match(deduped[-1], coord):
            deduped.append(coord)

    return deduped


def _flatten_route_segments(
    route_segments: list[RouteSegmentData],
) -> list[CoordinateTriple]:
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
