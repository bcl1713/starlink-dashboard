"""Mission package export utilities for creating portable mission archives."""

import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.mission.models import Mission
from app.mission.storage import load_mission_v2, get_mission_path
from app.mission.exporter import generate_timeline_export, TimelineExportFormat

logger = logging.getLogger(__name__)


class ExportPackageError(RuntimeError):
    """Raised when mission package export fails."""


def export_mission_package(mission_id: str) -> bytes:
    """Export complete mission as zip archive.

    Package includes:
    - mission.json (top-level metadata)
    - legs/*.json (all leg configurations)
    - routes/*.kml (KML files for each leg)
    - pois/*.json (POI data for each leg)
    - exports/leg-{id}/ (PDF, XLSX, PPTX, CSV for each leg)
    - manifest.json (package metadata)

    Args:
        mission_id: Mission to export

    Returns:
        Zip file as bytes
    """
    mission = load_mission_v2(mission_id)

    if not mission:
        raise ExportPackageError(f"Mission {mission_id} not found")

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add mission metadata
        zf.writestr("mission.json", json.dumps(mission.model_dump(), indent=2, default=str))

        # Add manifest
        manifest = {
            "version": "1.0",
            "mission_id": mission.id,
            "mission_name": mission.name,
            "leg_count": len(mission.legs),
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        # TODO: Add legs, routes, POIs, exports in subsequent tasks

    buffer.seek(0)
    return buffer.read()
