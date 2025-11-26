"""Mission package export utilities for creating portable mission archives."""

import hashlib
import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.mission.models import Mission, MissionLeg
from app.mission.storage import load_mission_v2, get_mission_path, load_mission_timeline
from app.mission.exporter import generate_timeline_export, TimelineExportFormat
from app.services.route_manager import RouteManager
from app.services.poi_manager import POIManager

logger = logging.getLogger(__name__)

# Global manager instances (set by main.py during startup)
_route_manager: Optional[RouteManager] = None
_poi_manager: Optional[POIManager] = None


def set_route_manager(route_manager: RouteManager) -> None:
    """Set the route manager instance (called by main.py during startup)."""
    global _route_manager
    _route_manager = route_manager


def set_poi_manager(poi_manager: POIManager) -> None:
    """Set the POI manager instance (called by main.py during startup)."""
    global _poi_manager
    _poi_manager = poi_manager


class ExportPackageError(RuntimeError):
    """Raised when mission package export fails."""


def generate_mission_combined_csv(mission: Mission) -> bytes:
    """Generate combined CSV timeline for all legs in mission.

    Combines all leg timelines into a single CSV with leg boundaries marked.
    """
    import csv

    output = io.StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        "Mission", mission.name,
        "Total Legs", len(mission.legs),
        "Generated", datetime.now(timezone.utc).isoformat()
    ])
    writer.writerow([])  # Blank line

    # Write combined timeline
    writer.writerow(["Leg ID", "Leg Name", "Event Time", "Event Type", "Details"])

    for leg in mission.legs:
        try:
            # Load timeline for this leg
            timeline = load_mission_timeline(leg.id)
            if not timeline:
                continue

            # Add leg boundary marker
            writer.writerow([leg.id, leg.name, "LEG START", "---", "---"])

            # Add timeline events (simplified - adjust based on actual timeline structure)
            # This is a placeholder - you'll need to adapt based on MissionLegTimeline structure
            writer.writerow([leg.id, leg.name, "TODO", "Extract timeline events", "..."])

            writer.writerow([leg.id, leg.name, "LEG END", "---", "---"])
            writer.writerow([])  # Blank line between legs

        except Exception as e:
            logger.error(f"Failed to include leg {leg.id} in combined CSV: {e}")

    return output.getvalue().encode('utf-8')


def generate_mission_combined_xlsx(mission: Mission) -> bytes:
    """Generate combined XLSX timeline with one sheet per leg plus summary.

    Creates workbook with:
    - Summary sheet (mission overview)
    - One sheet per leg with timeline
    """
    import io
    try:
        from openpyxl import Workbook
    except ImportError:
        logger.error("openpyxl not installed")
        return b""

    wb = Workbook()

    # Summary sheet
    ws = wb.active
    ws.title = "Mission Summary"
    ws.append(["Mission Name", mission.name])
    ws.append(["Mission ID", mission.id])
    ws.append(["Total Legs", len(mission.legs)])
    ws.append(["Generated", datetime.now(timezone.utc).isoformat()])
    ws.append([])
    ws.append(["Leg ID", "Leg Name", "Description"])

    for leg in mission.legs:
        ws.append([leg.id, leg.name, leg.description or ""])

    # Individual leg sheets
    for idx, leg in enumerate(mission.legs):
        ws_leg = wb.create_sheet(title=f"Leg {idx+1}")
        ws_leg.append(["Leg Name", leg.name])
        ws_leg.append(["Leg ID", leg.id])
        ws_leg.append([])
        ws_leg.append(["Timeline", "TODO: Add timeline data"])

    # Save to bytes
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.read()


def generate_mission_combined_pptx(mission: Mission) -> bytes:
    """Generate combined PPTX slides for entire mission.

    Creates presentation with:
    - Title slide (mission overview)
    - One slide per leg
    - Summary slide
    """
    import io
    try:
        from pptx import Presentation
        from pptx.util import Inches
    except ImportError:
        logger.error("python-pptx not installed")
        return b""

    prs = Presentation()

    # Title slide
    title_slide = prs.slides.add_slide(prs.slide_layouts[0])
    title = title_slide.shapes.title
    subtitle = title_slide.placeholders[1]
    title.text = mission.name
    subtitle.text = f"Mission ID: {mission.id}\n{len(mission.legs)} Legs"

    # Leg slides
    for leg in mission.legs:
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        title = slide.shapes.title
        content = slide.placeholders[1]
        title.text = leg.name
        content.text = f"Leg ID: {leg.id}\nDescription: {leg.description or 'N/A'}"

    # Save to bytes
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output.read()


def generate_mission_combined_pdf(mission: Mission) -> bytes:
    """Generate combined PDF report for entire mission.

    Creates PDF with:
    - Cover page (mission overview)
    - One section per leg
    - Summary page
    """
    import io
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        logger.error("reportlab not installed")
        return b""

    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=letter)
    width, height = letter

    # Cover page
    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, height - 100, mission.name)
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 140, f"Mission ID: {mission.id}")
    c.drawString(100, height - 160, f"Total Legs: {len(mission.legs)}")
    c.showPage()

    # Leg pages
    for leg in mission.legs:
        c.setFont("Helvetica-Bold", 18)
        c.drawString(100, height - 100, f"Leg: {leg.name}")
        c.setFont("Helvetica", 12)
        c.drawString(100, height - 140, f"Leg ID: {leg.id}")
        c.drawString(100, height - 160, f"Description: {leg.description or 'N/A'}")
        c.showPage()

    c.save()
    output.seek(0)
    return output.read()


def export_mission_package(mission_id: str, route_manager: Optional[RouteManager] = None, poi_manager: Optional[POIManager] = None) -> bytes:
    """Export complete mission as zip archive.

    Package structure:
        mission-{id}.zip
        ├── mission.json
        ├── manifest.json
        ├── legs/
        │   ├── {leg-id-1}.json
        │   └── {leg-id-2}.json
        ├── routes/
        │   ├── {route-id-1}.kml
        │   └── {route-id-2}.kml
        ├── pois/
        │   ├── {leg-id-1}-pois.json
        │   └── {leg-id-2}-pois.json
        ├── exports/
        │   ├── mission/
        │   │   ├── mission-timeline.csv
        │   │   ├── mission-timeline.xlsx
        │   │   ├── mission-slides.pptx
        │   │   └── mission-report.pdf
        │   └── legs/
        │       ├── {leg-id-1}/
        │       │   ├── timeline.csv
        │       │   ├── timeline.xlsx
        │       │   ├── slides.pptx
        │       │   └── report.pdf
        │       └── {leg-id-2}/
        │           ├── timeline.csv
        │           ├── timeline.xlsx
        │           ├── slides.pptx
        │           └── report.pdf

    Args:
        mission_id: Mission to export
        route_manager: Optional RouteManager instance for fetching route KML files (uses global if not provided)
        poi_manager: Optional POIManager instance for fetching mission POIs (uses global if not provided)

    Returns:
        Zip file as bytes
    """
    mission = load_mission_v2(mission_id)

    if not mission:
        raise ExportPackageError(f"Mission {mission_id} not found")

    # Use global managers if not provided
    rm = route_manager or _route_manager
    pm = poi_manager or _poi_manager

    buffer = io.BytesIO()
    manifest_files = {
        "mission_data": ["mission.json", "manifest.json"],
        "legs": [],
        "routes": [],
        "pois": [],
        "mission_exports": [],
        "per_leg_exports": [],
    }

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add mission metadata
        zf.writestr("mission.json", json.dumps(mission.model_dump(), indent=2, default=str))
        logger.info(f"Added mission.json for {mission.id}")

        # Add leg JSON files
        for leg in mission.legs:
            leg_json = json.dumps(leg.model_dump(), indent=2, default=str)
            leg_path = f"legs/{leg.id}.json"
            zf.writestr(leg_path, leg_json)
            manifest_files["legs"].append(leg_path)
            logger.info(f"Added leg file: {leg_path}")

        # Add route KML files for each leg
        if rm:
            for leg in mission.legs:
                if leg.route_id:
                    try:
                        route = rm.get_route(leg.route_id)
                        if route:
                            # Try to read the KML file from disk
                            routes_dir = Path(rm.routes_dir)
                            kml_file = routes_dir / f"{leg.route_id}.kml"
                            if kml_file.exists():
                                with open(kml_file, "rb") as f:
                                    kml_content = f.read()
                                route_path = f"routes/{leg.route_id}.kml"
                                zf.writestr(route_path, kml_content)
                                manifest_files["routes"].append(route_path)
                                logger.info(f"Added route KML: {route_path}")
                            else:
                                logger.warning(f"Route KML file not found at {kml_file} for leg {leg.id}")
                        else:
                            logger.warning(f"Route {leg.route_id} not found for leg {leg.id}")
                    except Exception as e:
                        logger.error(f"Failed to add route KML for leg {leg.id}: {e}")

        # Add POI data for each leg
        if pm:
            # Track all POI IDs we've seen to collect satellite POIs at the end
            all_poi_ids = set()

            for leg in mission.legs:
                try:
                    # Get POIs associated with this leg's route and mission
                    leg_pois = []

                    # Get mission-scoped POIs
                    mission_pois = pm.list_pois(mission_id=mission.id)
                    leg_pois.extend(mission_pois)

                    # Get route-specific POIs if leg has a route
                    if leg.route_id:
                        route_pois = pm.list_pois(route_id=leg.route_id)
                        leg_pois.extend(route_pois)

                    # Track POI IDs
                    for poi in leg_pois:
                        all_poi_ids.add(poi.id)

                    if leg_pois:
                        pois_data = {
                            "leg_id": leg.id,
                            "mission_id": mission.id,
                            "route_id": leg.route_id,
                            "pois": [poi.model_dump(mode='json') for poi in leg_pois],
                            "count": len(leg_pois),
                        }
                        poi_path = f"pois/{leg.id}-pois.json"
                        zf.writestr(poi_path, json.dumps(pois_data, indent=2, default=str))
                        manifest_files["pois"].append(poi_path)
                        logger.info(f"Added POI data: {poi_path} with {len(leg_pois)} POIs")
                except Exception as e:
                    logger.error(f"Failed to add POI data for leg {leg.id}: {e}")

            # Export satellite POIs (category="satellite") separately
            try:
                all_pois = pm.list_pois()
                satellite_pois = [poi for poi in all_pois if poi.category == "satellite"]

                if satellite_pois:
                    satellite_data = {
                        "type": "satellite_pois",
                        "pois": [poi.model_dump(mode='json') for poi in satellite_pois],
                        "count": len(satellite_pois),
                    }
                    satellite_path = "pois/satellites.json"
                    zf.writestr(satellite_path, json.dumps(satellite_data, indent=2, default=str))
                    manifest_files["pois"].append(satellite_path)
                    logger.info(f"Added satellite POI data: {satellite_path} with {len(satellite_pois)} satellites")
            except Exception as e:
                logger.error(f"Failed to add satellite POI data: {e}")

        # Generate per-leg exports (load timeline for each leg)
        for leg in mission.legs:
            # Load timeline for this specific leg
            leg_timeline = load_mission_timeline(leg.id)
            if not leg_timeline:
                logger.warning(f"No timeline found for leg {leg.id}, skipping exports for this leg")
                continue

            try:
                # CSV export
                csv_export = generate_timeline_export(
                    export_format=TimelineExportFormat.CSV,
                    mission=leg,  # Pass the leg as mission (MissionLeg has same fields)
                    timeline=leg_timeline,
                )
                csv_path = f"exports/legs/{leg.id}/timeline.csv"
                zf.writestr(csv_path, csv_export.content)
                manifest_files["per_leg_exports"].append(csv_path)
                logger.info(f"Generated CSV for leg {leg.id}")
            except Exception as e:
                logger.error(f"Failed to generate CSV for leg {leg.id}: {e}")

            try:
                # XLSX export
                xlsx_export = generate_timeline_export(
                    export_format=TimelineExportFormat.XLSX,
                    mission=leg,
                    timeline=leg_timeline,
                )
                xlsx_path = f"exports/legs/{leg.id}/timeline.xlsx"
                zf.writestr(xlsx_path, xlsx_export.content)
                manifest_files["per_leg_exports"].append(xlsx_path)
                logger.info(f"Generated XLSX for leg {leg.id}")
            except Exception as e:
                logger.error(f"Failed to generate XLSX for leg {leg.id}: {e}")

            try:
                # PPTX export
                pptx_export = generate_timeline_export(
                    export_format=TimelineExportFormat.PPTX,
                    mission=leg,
                    timeline=leg_timeline,
                )
                pptx_path = f"exports/legs/{leg.id}/slides.pptx"
                zf.writestr(pptx_path, pptx_export.content)
                manifest_files["per_leg_exports"].append(pptx_path)
                logger.info(f"Generated PPTX for leg {leg.id}")
            except Exception as e:
                logger.error(f"Failed to generate PPTX for leg {leg.id}: {e}")

            try:
                # PDF export
                pdf_export = generate_timeline_export(
                    export_format=TimelineExportFormat.PDF,
                    mission=leg,
                    timeline=leg_timeline,
                )
                pdf_path = f"exports/legs/{leg.id}/report.pdf"
                zf.writestr(pdf_path, pdf_export.content)
                manifest_files["per_leg_exports"].append(pdf_path)
                logger.info(f"Generated PDF for leg {leg.id}")
            except Exception as e:
                logger.error(f"Failed to generate PDF for leg {leg.id}: {e}")

            # Generate combined mission-level exports
            try:
                logger.info(f"Generating combined mission-level exports for {mission.id}")

                # Combined CSV
                mission_csv = generate_mission_combined_csv(mission)
                mission_csv_path = "exports/mission/mission-timeline.csv"
                zf.writestr(mission_csv_path, mission_csv)
                manifest_files["mission_exports"].append(mission_csv_path)

                # Combined XLSX
                mission_xlsx = generate_mission_combined_xlsx(mission)
                mission_xlsx_path = "exports/mission/mission-timeline.xlsx"
                zf.writestr(mission_xlsx_path, mission_xlsx)
                manifest_files["mission_exports"].append(mission_xlsx_path)

                # Combined PPTX
                mission_pptx = generate_mission_combined_pptx(mission)
                mission_pptx_path = "exports/mission/mission-slides.pptx"
                zf.writestr(mission_pptx_path, mission_pptx)
                manifest_files["mission_exports"].append(mission_pptx_path)

                # Combined PDF
                mission_pdf = generate_mission_combined_pdf(mission)
                mission_pdf_path = "exports/mission/mission-report.pdf"
                zf.writestr(mission_pdf_path, mission_pdf)
                manifest_files["mission_exports"].append(mission_pdf_path)

                logger.info("Combined mission-level exports complete")

            except Exception as e:
                logger.error(f"Failed to generate combined mission exports: {e}")

        # Create comprehensive manifest with file listing and statistics
        manifest = {
            "version": "2.0",
            "mission_id": mission.id,
            "mission_name": mission.name,
            "mission_description": mission.description or "",
            "leg_count": len(mission.legs),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "file_structure": {
                "mission_data": manifest_files["mission_data"],
                "legs": manifest_files["legs"],
                "routes": manifest_files["routes"],
                "pois": manifest_files["pois"],
                "mission_exports": manifest_files["mission_exports"],
                "per_leg_exports": manifest_files["per_leg_exports"],
            },
            "statistics": {
                "total_files": (
                    len(manifest_files["mission_data"]) +
                    len(manifest_files["legs"]) +
                    len(manifest_files["routes"]) +
                    len(manifest_files["pois"]) +
                    len(manifest_files["mission_exports"]) +
                    len(manifest_files["per_leg_exports"])
                ),
                "leg_files": len(manifest_files["legs"]),
                "route_files": len(manifest_files["routes"]),
                "poi_files": len(manifest_files["pois"]),
                "mission_export_files": len(manifest_files["mission_exports"]),
                "per_leg_export_files": len(manifest_files["per_leg_exports"]),
            },
        }

        manifest_json = json.dumps(manifest, indent=2)
        zf.writestr("manifest.json", manifest_json)
        logger.info(f"Created manifest.json with {manifest['statistics']['total_files']} files")

    buffer.seek(0)
    return buffer.read()
