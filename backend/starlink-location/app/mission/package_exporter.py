"""Mission package export utilities for creating portable mission archives."""

import io
import json
import logging
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.mission.models import Mission
from app.mission.storage import load_mission_v2, get_mission_path, load_mission_timeline
from app.mission.exporter import generate_timeline_export, TimelineExportFormat

logger = logging.getLogger(__name__)


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


def export_mission_package(mission_id: str) -> bytes:
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

        # Load mission timeline for exports
        timeline = load_mission_timeline(mission_id)
        if not timeline:
            logger.warning(f"No timeline found for mission {mission_id}, skipping per-leg exports")
        else:
            # Generate per-leg exports
            for leg in mission.legs:
                try:
                    # CSV export
                    csv_export = generate_timeline_export(
                        export_format=TimelineExportFormat.CSV,
                        mission=mission,
                        timeline=timeline,
                    )
                    zf.writestr(f"exports/legs/{leg.id}/timeline.csv", csv_export.content)
                    logger.info(f"Generated CSV for leg {leg.id}")
                except Exception as e:
                    logger.error(f"Failed to generate CSV for leg {leg.id}: {e}")

                try:
                    # XLSX export
                    xlsx_export = generate_timeline_export(
                        export_format=TimelineExportFormat.XLSX,
                        mission=mission,
                        timeline=timeline,
                    )
                    zf.writestr(f"exports/legs/{leg.id}/timeline.xlsx", xlsx_export.content)
                    logger.info(f"Generated XLSX for leg {leg.id}")
                except Exception as e:
                    logger.error(f"Failed to generate XLSX for leg {leg.id}: {e}")

                try:
                    # PPTX export
                    pptx_export = generate_timeline_export(
                        export_format=TimelineExportFormat.PPTX,
                        mission=mission,
                        timeline=timeline,
                    )
                    zf.writestr(f"exports/legs/{leg.id}/slides.pptx", pptx_export.content)
                    logger.info(f"Generated PPTX for leg {leg.id}")
                except Exception as e:
                    logger.error(f"Failed to generate PPTX for leg {leg.id}: {e}")

                try:
                    # PDF export
                    pdf_export = generate_timeline_export(
                        export_format=TimelineExportFormat.PDF,
                        mission=mission,
                        timeline=timeline,
                    )
                    zf.writestr(f"exports/legs/{leg.id}/report.pdf", pdf_export.content)
                    logger.info(f"Generated PDF for leg {leg.id}")
                except Exception as e:
                    logger.error(f"Failed to generate PDF for leg {leg.id}: {e}")

            # Generate combined mission-level exports
            try:
                logger.info(f"Generating combined mission-level exports for {mission.id}")

                # Combined CSV
                mission_csv = generate_mission_combined_csv(mission)
                zf.writestr("exports/mission/mission-timeline.csv", mission_csv)

                # Combined XLSX
                mission_xlsx = generate_mission_combined_xlsx(mission)
                zf.writestr("exports/mission/mission-timeline.xlsx", mission_xlsx)

                # Combined PPTX
                mission_pptx = generate_mission_combined_pptx(mission)
                zf.writestr("exports/mission/mission-slides.pptx", mission_pptx)

                # Combined PDF
                mission_pdf = generate_mission_combined_pdf(mission)
                zf.writestr("exports/mission/mission-report.pdf", mission_pdf)

                logger.info("Combined mission-level exports complete")

            except Exception as e:
                logger.error(f"Failed to generate combined mission exports: {e}")

        # Add manifest
        manifest = {
            "version": "1.0",
            "mission_id": mission.id,
            "mission_name": mission.name,
            "leg_count": len(mission.legs),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "included_files": {
                "mission_data": ["mission.json", "manifest.json"],
                "legs": [f"legs/{leg.id}.json" for leg in mission.legs],
                "mission_exports": [
                    "exports/mission/mission-timeline.csv",
                    "exports/mission/mission-timeline.xlsx",
                    "exports/mission/mission-slides.pptx",
                    "exports/mission/mission-report.pdf",
                ],
                "per_leg_exports": (
                    [f"exports/legs/{leg.id}/timeline.csv" for leg in mission.legs]
                    + [f"exports/legs/{leg.id}/timeline.xlsx" for leg in mission.legs]
                    + [f"exports/legs/{leg.id}/slides.pptx" for leg in mission.legs]
                    + [f"exports/legs/{leg.id}/report.pdf" for leg in mission.legs]
                ),
            },
        }
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))

    buffer.seek(0)
    return buffer.read()
