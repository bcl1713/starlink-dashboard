"""KMZ/KML to GeoJSON conversion for satellite coverage overlays.

Handles ingestion of KML/KMZ files (Ka coverage from CommKa source) and converts
to standardized GeoJSON format for point-in-polygon testing and Grafana display.
"""

# FR-004: File exceeds 300 lines (305 lines) because KMZ importer handles
# ZIP extraction, KML parsing, GeoJSON generation, and coordinate transformation.
# Splitting would fragment the import pipeline. Deferred to v0.4.0.

import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# KML namespace
KML_NS = {"kml": "http://www.opengis.net/kml/2.2"}


def _names_match(candidate: Optional[str], expected: Optional[str]) -> bool:
    """Return True when a Placemark name should satisfy the requested polygon."""
    if not expected:
        return True
    if not candidate:
        return False

    candidate_norm = candidate.replace("_", " ").strip().upper()
    expected_norm = expected.strip().upper()
    if candidate_norm == expected_norm:
        return True

    tokens = candidate_norm.replace("-", " ").split()
    return expected_norm in tokens


def extract_kmz(kmz_path: Path, extract_to: Optional[Path] = None) -> Optional[Path]:
    """Extract KMZ (zipped KML) to a temporary directory.

    Args:
        kmz_path: Path to .kmz file
        extract_to: Directory to extract to (created if needed); if None, uses temp

    Returns:
        Path to extracted directory, or None if extraction failed
    """
    try:
        if extract_to is None:
            import tempfile

            extract_to = Path(tempfile.mkdtemp(prefix="kmz_"))
        else:
            extract_to.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(kmz_path, "r") as z:
            z.extractall(extract_to)

        logger.info(f"Extracted KMZ to {extract_to}")
        return extract_to

    except (zipfile.BadZipFile, IOError) as e:
        logger.error(f"Failed to extract KMZ: {e}")
        return None


def find_kml_file(directory: Path) -> Optional[Path]:
    """Find the main KML file in extracted KMZ directory.

    KMZ may contain multiple KML files; usually the first or named 'doc.kml'.
    """
    # Try common names first
    for name in ["doc.kml", "Document.kml"]:
        candidate = directory / name
        if candidate.exists():
            return candidate

    # Fall back to any .kml file
    for kml_file in directory.glob("*.kml"):
        return kml_file

    return None


def parse_kml(kml_path: Path) -> Optional[ET.Element]:
    """Parse KML file and return root element."""
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
        return root
    except ET.ParseError as e:
        logger.error(f"Failed to parse KML {kml_path}: {e}")
        return None


def extract_polygon_from_kml(
    kml_root: ET.Element, polygon_name: Optional[str] = None
) -> Optional[List[Tuple[float, float]]]:
    """Extract polygon coordinates from KML Polygon geometry.

    Args:
        kml_root: Parsed KML root element
        polygon_name: If specified, only extract polygon with this name

    Returns:
        List of (lon, lat) tuples for the polygon exterior ring
    """
    # Find all Placemarks in the KML
    placemarks = kml_root.findall(".//kml:Placemark", KML_NS)

    for placemark in placemarks:
        # Check name if filtering
        name_elem = placemark.find("kml:name", KML_NS)
        name_value = name_elem.text if name_elem is not None else None
        if polygon_name and not _names_match(name_value, polygon_name):
            continue

        # Look for Polygon geometry
        polygon = placemark.find(".//kml:Polygon", KML_NS)
        if polygon is None:
            continue

        # Extract outer boundary coordinates
        outer = polygon.find(
            "kml:outerBoundaryIs/kml:LinearRing/kml:coordinates", KML_NS
        )
        if outer is None or outer.text is None:
            logger.warning(f"Polygon {polygon_name} has no outer boundary")
            continue

        coordinates = []
        for coord_str in outer.text.strip().split():
            parts = coord_str.strip().split(",")
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coordinates.append((lon, lat))
                except ValueError:
                    logger.warning(f"Invalid coordinate: {coord_str}")
                    continue

        return coordinates

    return None


def polygon_to_geojson_feature(
    coordinates: List[Tuple[float, float]],
    name: str,
    properties: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert polygon coordinates to GeoJSON Feature.

    Args:
        coordinates: List of (lon, lat) tuples forming polygon exterior ring
        name: Feature name/identifier
        properties: Optional properties dict for the feature

    Returns:
        GeoJSON Feature object with Polygon geometry
    """
    if not properties:
        properties = {}

    properties["name"] = name

    # GeoJSON uses [lon, lat] format
    return {
        "type": "Feature",
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [coordinates],  # Wrap in array (outer ring + holes)
        },
    }


def kmz_to_geojson(
    kmz_path: Path,
    output_path: Optional[Path] = None,
    polygon_mappings: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, Any]]:
    """Convert KMZ file to GeoJSON FeatureCollection.

    Args:
        kmz_path: Path to .kmz file
        output_path: If provided, save GeoJSON to this file
        polygon_mappings: Dict mapping KML polygon names to satellite IDs
                         (e.g., {"PORB": "POR"})

    Returns:
        GeoJSON FeatureCollection dict, or None if conversion failed
    """
    # Extract KMZ
    extract_dir = extract_kmz(kmz_path)
    if extract_dir is None:
        return None

    # Find KML file
    kml_path = find_kml_file(extract_dir)
    if kml_path is None:
        logger.error("No KML file found in KMZ")
        return None

    # Parse KML
    kml_root = parse_kml(kml_path)
    if kml_root is None:
        return None

    # Default mappings for CommKa satellite coverage
    if polygon_mappings is None:
        polygon_mappings = {
            "PORB": "POR",
            "PORA": "POR",
            "IOR": "IOR",
            "AOR": "AOR",
        }

    features = []

    # Extract polygons (each should correspond to a satellite coverage area)
    for polygon_name, satellite_id in polygon_mappings.items():
        coords = extract_polygon_from_kml(kml_root, polygon_name)
        if coords is None:
            logger.warning(f"Polygon '{polygon_name}' not found in KML")
            continue

        feature = polygon_to_geojson_feature(
            coords,
            satellite_id,
            properties={"satellite_id": satellite_id, "coverage_region": polygon_name},
        )
        features.append(feature)
        logger.info(
            f"Extracted {polygon_name} for {satellite_id} ({len(coords)} points)"
        )

    if not features:
        logger.error("No polygons extracted from KML")
        return None

    # Create FeatureCollection
    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    # Save to file if requested
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(geojson, f, indent=2)
        logger.info(f"Saved GeoJSON to {output_path}")

    return geojson


def load_commka_coverage(
    kmz_path: Path, output_dir: Path = Path("data/sat_coverage")
) -> Optional[Path]:
    """Load CommKa KMZ and convert to GeoJSON.

    Convenience function for standard CommKa coverage ingestion.

    Args:
        kmz_path: Path to CommKa.kmz
        output_dir: Directory to save commka.geojson

    Returns:
        Path to generated commka.geojson, or None if failed
    """
    output_path = output_dir / "commka.geojson"

    # Skip if already converted
    if output_path.exists():
        logger.info(f"CommKa GeoJSON already exists at {output_path}")
        return output_path

    # Convert
    geojson = kmz_to_geojson(kmz_path, output_path)
    if geojson is None:
        return None

    logger.info(f"CommKa coverage loaded: {len(geojson['features'])} regions")
    return output_path


def load_geojson_polygon(geojson_path: Path) -> Optional[Dict[str, Any]]:
    """Load a GeoJSON file containing polygon(s).

    Args:
        geojson_path: Path to .geojson file

    Returns:
        Parsed GeoJSON dict, or None if file not found
    """
    if not geojson_path.exists():
        logger.warning(f"GeoJSON file not found: {geojson_path}")
        return None

    try:
        with open(geojson_path, "r") as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load GeoJSON {geojson_path}: {e}")
        return None
