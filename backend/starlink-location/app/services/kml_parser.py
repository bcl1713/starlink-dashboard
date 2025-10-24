"""KML file parser for converting KML routes to ParsedRoute objects."""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from app.models.route import ParsedRoute, RouteMetadata, RoutePoint

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


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

    # Extract all LineString coordinates
    points: list[RoutePoint] = []
    point_sequence = 0

    # Find all LineString elements
    for linestring in root.findall(".//kml:LineString", KML_NS):
        coords_elem = linestring.find("kml:coordinates", KML_NS)
        if coords_elem is None or not coords_elem.text:
            continue

        # Parse coordinates
        coords_text = coords_elem.text.strip()
        for coord_str in coords_text.split():
            parts = coord_str.split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    altitude = float(parts[2]) if len(parts) > 2 else None

                    points.append(
                        RoutePoint(
                            latitude=lat,
                            longitude=lon,
                            altitude=altitude,
                            sequence=point_sequence,
                        )
                    )
                    point_sequence += 1
                except ValueError:
                    logger.warning(f"Failed to parse coordinate: {coord_str}")
                    continue

    if not points:
        raise KMLParseError("No coordinate data found in KML file")

    # Create metadata
    metadata = RouteMetadata(
        name=route_name,
        description=route_description,
        file_path=str(file_path.absolute()),
        point_count=len(points),
    )

    # Create ParsedRoute
    parsed_route = ParsedRoute(metadata=metadata, points=points)

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
    return elem.text if elem is not None else None


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
