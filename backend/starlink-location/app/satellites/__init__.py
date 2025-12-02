"""Satellite geometry and constraint engine for mission planning.

This module provides:
- Satellite catalog management (POIs, coverage data)
- Azimuth/elevation calculations
- Coverage sampling for Ka transport
- Rule evaluation for communication constraints
"""

from app.satellites.catalog import (
    SatelliteCatalog,
    get_satellite_catalog,
    load_satellite_catalog,
)
from app.satellites.coverage import CoverageEvent, CoverageSampler
from app.satellites.geometry import (
    azimuth_elevation_from_ecef,
    ecef_from_geodetic,
    geodetic_from_ecef,
    is_in_azimuth_range,
    look_angles,
)
from app.satellites.kmz_importer import (
    extract_kmz,
    kmz_to_geojson,
    load_geojson_polygon,
    load_commka_coverage,
)

__all__ = [
    "SatelliteCatalog",
    "load_satellite_catalog",
    "get_satellite_catalog",
    "ecef_from_geodetic",
    "geodetic_from_ecef",
    "look_angles",
    "azimuth_elevation_from_ecef",
    "is_in_azimuth_range",
    "CoverageSampler",
    "CoverageEvent",
    "extract_kmz",
    "kmz_to_geojson",
    "load_commka_coverage",
    "load_geojson_polygon",
]
