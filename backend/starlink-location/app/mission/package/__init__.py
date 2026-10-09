"""Mission package export module for creating portable mission archives.

This module handles packaging complete missions (with all legs) into
importable archive formats, including combined Excel workbooks.

Exported functionality includes:
- Package creation and validation
- XLSX workbook assembly from multiple leg exports
- Archive creation (ZIP format)
"""

from __future__ import annotations

# Public API - re-export main functions
from app.mission.package.__main__ import (
    ExportPackageError,
    export_mission_package,
)
from app.mission.package.snapshot_export import build_snapshot_legacy_package

__all__ = [
    "ExportPackageError",
    "build_snapshot_legacy_package",
    "export_mission_package",
]
