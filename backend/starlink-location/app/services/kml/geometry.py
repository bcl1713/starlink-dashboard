"""KML geometry parsing and coordinate handling."""

import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

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


def parse_geometry(placemark_elem: ET.Element) -> Optional[PlacemarkGeometry]:
    """Parse geometry for a Placemark.

    Args:
        placemark_elem: XML element representing a KML Placemark

    Returns:
        PlacemarkGeometry object if geometry found, None otherwise
    """
    point_elem = placemark_elem.find("kml:Point", KML_NS)
    if point_elem is not None:
        coords_elem = point_elem.find("kml:coordinates", KML_NS)
        if coords_elem is None or not coords_elem.text:
            return None
        coordinates = parse_coordinates(coords_elem.text)
        altitude_mode = get_element_text(point_elem, "kml:altitudeMode")
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
        coordinates = parse_coordinates(coords_elem.text)
        altitude_mode = get_element_text(linestring_elem, "kml:altitudeMode")
        return PlacemarkGeometry(
            kind="LineString",
            coordinates=coordinates,
            altitude_mode=altitude_mode,
        )

    # Additional geometries can be added here as needed
    return None


def parse_line_style(placemark_elem: ET.Element) -> Optional[LineStyleInfo]:
    """Parse inline LineStyle data if present on the Placemark.

    Args:
        placemark_elem: XML element representing a KML Placemark

    Returns:
        LineStyleInfo object if line style found, None otherwise
    """
    linestring_style = placemark_elem.find("kml:Style/kml:LineStyle", KML_NS)
    if linestring_style is None:
        return None

    color = get_element_text(linestring_style, "kml:color")

    width_text = get_element_text(linestring_style, "kml:width")
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


def parse_coordinates(coords_text: str) -> list[CoordinateTriple]:
    """Parse a whitespace-separated coordinate string into triples.

    Args:
        coords_text: Whitespace-separated coordinate string from KML

    Returns:
        List of CoordinateTriple objects parsed from the text
    """
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


def get_element_text(element: ET.Element, tag: str) -> Optional[str]:
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


def coordinates_match(
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


def deduplicate_coordinates(
    coordinates: list[CoordinateTriple],
) -> list[CoordinateTriple]:
    """Remove consecutive duplicate coordinates.

    Args:
        coordinates: List of CoordinateTriple objects

    Returns:
        List with consecutive duplicates removed
    """
    deduped: list[CoordinateTriple] = []

    for coord in coordinates:
        if not deduped or not coordinates_match(deduped[-1], coord):
            deduped.append(coord)

    return deduped


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate approximate distance between two points using haversine formula.

    This function uses the haversine formula to calculate the great-circle distance
    between two points on Earth given their latitude and longitude in degrees.
    The formula accurately handles the spherical shape of Earth and is robust for
    navigation calculations.

    Args:
        lat1: Latitude of starting point in decimal degrees
        lon1: Longitude of starting point in decimal degrees
        lat2: Latitude of ending point in decimal degrees
        lon2: Longitude of ending point in decimal degrees

    Returns:
        Distance in meters (approximate, using Earth radius = 6371 km)

    Example:
        >>> distance = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
        >>> # Distance from New York to Los Angeles: ~3,944 km
    """
    from math import radians, cos, sin, asin, sqrt

    # Convert all coordinates from degrees to radians for trigonometric calculations
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    # Calculate angle differences between the two points in radians
    longitude_delta_rad = lon2_rad - lon1_rad
    latitude_delta_rad = lat2_rad - lat1_rad

    # Haversine formula: a = sin²(Δφ/2) + cos(φ1) * cos(φ2) * sin²(Δλ/2)
    # where φ is latitude, λ is longitude, Δ is difference
    haversine_component = (
        sin(latitude_delta_rad / 2) ** 2
        + cos(lat1_rad) * cos(lat2_rad) * sin(longitude_delta_rad / 2) ** 2
    )

    # Calculate central angle: c = 2 * atan2(√a, √(1−a))
    # Simplified to: c = 2 * asin(√a)
    central_angle_rad = 2 * asin(sqrt(haversine_component))

    # Earth's mean radius in meters
    earth_radius_m = 6371000

    # Distance = radius × central angle
    return central_angle_rad * earth_radius_m
