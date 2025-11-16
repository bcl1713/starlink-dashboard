"""Satellite catalog management for mission planning.

Manages satellite metadata including POIs and coverage data. Integrates with
HCX KMZ coverage files for Ka satellites and optional math-based fallback.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Satellite:
    """Satellite metadata including position, coverage, and transport info."""

    satellite_id: str  # e.g., 'X-1', 'AOR', 'Ku-Leo-1'
    transport: str  # 'X', 'Ka', or 'Ku'
    longitude: Optional[float] = None  # For geostationary satellites
    slot: Optional[str] = None  # Orbital slot name
    coverage_geojson_path: Optional[Path] = None  # Path to coverage polygon GeoJSON
    coverage_polygon: Optional[dict] = None  # Loaded GeoJSON feature (lazy loaded)
    color: str = "#FFFFFF"  # Display color for Grafana overlays
    metadata: Optional[dict] = None  # Additional metadata

    def load_coverage(self) -> Optional[dict]:
        """Load and cache coverage polygon from GeoJSON file."""
        if self.coverage_polygon is not None:
            return self.coverage_polygon

        if self.coverage_geojson_path is None:
            return None

        try:
            with open(self.coverage_geojson_path, "r") as f:
                geojson_data = json.load(f)
                # Store as GeoJSON Feature for point-in-polygon testing
                if geojson_data.get("type") == "Feature":
                    self.coverage_polygon = geojson_data
                elif geojson_data.get("type") == "Polygon":
                    self.coverage_polygon = {"type": "Feature", "geometry": geojson_data}
                else:
                    logger.warning(
                        f"Unexpected GeoJSON type for {self.satellite_id}: "
                        f"{geojson_data.get('type')}"
                    )
                    return None
                return self.coverage_polygon
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load coverage for {self.satellite_id}: {e}")
            return None

    def get_coverage_polygon(self) -> Optional[dict]:
        """Get coverage polygon (lazy loading from GeoJSON)."""
        if self.coverage_polygon is not None:
            return self.coverage_polygon
        return self.load_coverage()


class SatelliteCatalog:
    """Manages satellite metadata for mission planning.

    Supports:
    - Geostationary satellites (X, Ka) with longitude/slot info
    - LEO constellations (Ku) with math-based coverage fallback
    - Coverage polygons from KMZ/GeoJSON sources
    """

    def __init__(self):
        """Initialize empty satellite catalog."""
        self.satellites: Dict[str, Satellite] = {}
        self._transport_index: Dict[str, List[str]] = {}  # transport -> [sat_id, ...]

    def add_satellite(self, satellite: Satellite) -> None:
        """Add satellite to catalog.

        Args:
            satellite: Satellite metadata object
        """
        self.satellites[satellite.satellite_id] = satellite

        # Maintain transport index
        if satellite.transport not in self._transport_index:
            self._transport_index[satellite.transport] = []
        self._transport_index[satellite.transport].append(satellite.satellite_id)

        logger.debug(f"Added satellite {satellite.satellite_id} ({satellite.transport})")

    def get_satellite(self, satellite_id: str) -> Optional[Satellite]:
        """Retrieve satellite metadata by ID."""
        return self.satellites.get(satellite_id)

    def get_by_transport(self, transport: str) -> List[Satellite]:
        """Get all satellites for a transport (X, Ka, or Ku)."""
        sat_ids = self._transport_index.get(transport, [])
        return [self.satellites[sat_id] for sat_id in sat_ids]

    def list_all(self) -> List[Satellite]:
        """List all satellites in catalog."""
        return list(self.satellites.values())

    def validate_satellite(self, satellite_id: str) -> bool:
        """Check if satellite ID exists in catalog."""
        return satellite_id in self.satellites


# Global catalog instance (initialized on startup)
_catalog: Optional[SatelliteCatalog] = None


def load_satellite_catalog(
    data_dir: Path = Path("data/satellites"),
    sat_coverage_dir: Path = Path("data/sat_coverage"),
) -> SatelliteCatalog:
    """Load satellite catalog from data files.

    Initializes catalog with:
    1. Default X/Ka/Ku satellite definitions
    2. HCX KMZ polygons (converted to GeoJSON)
    3. Custom catalog.yaml if present

    Args:
        data_dir: Directory containing catalog.yaml (created if missing)
        sat_coverage_dir: Directory containing KMZ and GeoJSON files

    Returns:
        Initialized SatelliteCatalog instance
    """
    global _catalog

    # Create directories if needed
    data_dir.mkdir(parents=True, exist_ok=True)
    sat_coverage_dir.mkdir(parents=True, exist_ok=True)

    catalog = SatelliteCatalog()

    # Add default satellites (X, Ka, Ku)
    _add_default_satellites(catalog, sat_coverage_dir)

    # Load custom catalog from YAML if present
    catalog_yaml = data_dir / "catalog.yaml"
    if catalog_yaml.exists():
        _load_yaml_catalog(catalog, catalog_yaml, sat_coverage_dir)
        logger.info(f"Loaded custom catalog from {catalog_yaml}")
    else:
        logger.info("No custom catalog.yaml found; using default satellites only")

    _catalog = catalog
    return catalog


def get_satellite_catalog() -> SatelliteCatalog:
    """Get the global catalog instance (initialize if needed)."""
    global _catalog
    if _catalog is None:
        _catalog = load_satellite_catalog()
    return _catalog


def _add_default_satellites(
    catalog: SatelliteCatalog, sat_coverage_dir: Path
) -> None:
    """Add default X, Ka, and Ku satellite definitions."""

    # X transport: Fixed geostationary
    catalog.add_satellite(
        Satellite(
            satellite_id="X-1",
            transport="X",
            longitude=None,  # To be defined by mission planner
            slot="X-Slot-1",
            color="#FF6B6B",
        )
    )

    # Ka transport: Three operational beams (Atlantic, Pacific, Indian)
    hcx_coverage = sat_coverage_dir / "hcx.geojson"

    catalog.add_satellite(
        Satellite(
            satellite_id="AOR",
            transport="Ka",
            longitude=-30.0,
            slot="Atlantic Ocean Region",
            coverage_geojson_path=hcx_coverage if hcx_coverage.exists() else None,
            color="#4CAF50",
        )
    )

    catalog.add_satellite(
        Satellite(
            satellite_id="POR",
            transport="Ka",
            longitude=154.0,
            slot="Pacific Ocean Region",
            coverage_geojson_path=hcx_coverage if hcx_coverage.exists() else None,
            color="#66BB6A",
        )
    )

    catalog.add_satellite(
        Satellite(
            satellite_id="IOR",
            transport="Ka",
            longitude=60.0,
            slot="Indian Ocean Region",
            coverage_geojson_path=hcx_coverage if hcx_coverage.exists() else None,
            color="#81C784",
        )
    )

    # Ku transport: LEO constellation (always-on, no specific longitude)
    catalog.add_satellite(
        Satellite(
            satellite_id="Ku-Leo",
            transport="Ku",
            longitude=None,
            slot="LEO-Constellation",
            color="#00BCD4",
        )
    )

    logger.info("Initialized default satellite catalog (X-1, AOR/POR/IOR, Ku-Leo)")


def _load_yaml_catalog(
    catalog: SatelliteCatalog, yaml_path: Path, sat_coverage_dir: Path
) -> None:
    """Load custom satellite definitions from YAML.

    YAML format:
    ```yaml
    satellites:
      - id: X-Custom
        transport: X
        longitude: 120.5
        slot: Custom-Slot
        coverage_file: optional_path.geojson
        color: "#AABBCC"
    ```
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed; skipping custom catalog.yaml")
        return

    try:
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f) or {}

        for sat_def in data.get("satellites", []):
            sat_id = sat_def.get("id")
            if not sat_id:
                logger.warning("Satellite definition missing 'id' field; skipping")
                continue

            transport = sat_def.get("transport", "X")
            longitude = sat_def.get("longitude")
            slot = sat_def.get("slot")
            color = sat_def.get("color", "#FFFFFF")

            coverage_file = sat_def.get("coverage_file")
            coverage_path = None
            if coverage_file:
                coverage_path = sat_coverage_dir / coverage_file

            satellite = Satellite(
                satellite_id=sat_id,
                transport=transport,
                longitude=longitude,
                slot=slot,
                coverage_geojson_path=coverage_path,
                color=color,
            )
            catalog.add_satellite(satellite)
            logger.info(f"Loaded custom satellite {sat_id} from YAML")

    except Exception as e:
        logger.error(f"Error loading YAML catalog from {yaml_path}: {e}")
