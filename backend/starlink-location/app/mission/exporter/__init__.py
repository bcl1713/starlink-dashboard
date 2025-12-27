"""Mission timeline export module.

Transforms `MissionLegTimeline` data into CSV, XLSX, PDF, and PPTX deliverables
with parallel timestamp formats (UTC, Eastern, and T+ offsets) suitable for
customer-facing mission briefs.

This module is organized into:
- formatting: Pure timestamp and value formatting functions
- transport_utils: Transport state and display utilities
- excel_utils: Excel workbook manipulation utilities
- pptx_styling: PowerPoint styling and branding utilities
- pptx_builder: Reusable PPTX presentation generation functions
- __main__: Core export generation logic and format handlers
"""

from __future__ import annotations

# Public API - re-export main classes and functions
from app.mission.exporter.__main__ import (
    ExportArtifact,
    ExportGenerationError,
    TimelineExportFormat,
    generate_timeline_export,
    _generate_route_map,
    _segment_rows,
)
from app.mission.exporter.transport_utils import (
    TRANSPORT_DISPLAY,
    STATE_COLUMNS,
)
from app.mission.exporter.pptx_styling import (
    add_header_bar,
    add_footer_bar,
    add_slide_title,
    add_footer_text,
    add_content_background,
    add_status_badge,
    add_segment_separator,
    add_logo,
    BRAND_GOLD,
    CONTENT_GRAY,
    STATUS_NOMINAL,
    STATUS_SOF,
    STATUS_DEGRADED,
    STATUS_CRITICAL,
    TEXT_BLACK,
    TEXT_WHITE,
)
from app.mission.exporter.pptx_builder import (
    add_mission_slides_to_presentation,
    add_route_map_slide,
    add_timeline_table_slides,
)
from app.mission.models import Transport  # Re-exported for package module

__all__ = [
    "ExportArtifact",
    "ExportGenerationError",
    "TimelineExportFormat",
    "generate_timeline_export",
    "_generate_route_map",
    "_segment_rows",
    "TRANSPORT_DISPLAY",
    "STATE_COLUMNS",
    "Transport",
    # Styling functions
    "add_header_bar",
    "add_footer_bar",
    "add_slide_title",
    "add_footer_text",
    "add_content_background",
    "add_status_badge",
    "add_segment_separator",
    "add_logo",
    # Color constants
    "BRAND_GOLD",
    "CONTENT_GRAY",
    "STATUS_NOMINAL",
    "STATUS_SOF",
    "STATUS_DEGRADED",
    "STATUS_CRITICAL",
    "TEXT_BLACK",
    "TEXT_WHITE",
    # PPTX builder functions
    "add_mission_slides_to_presentation",
    "add_route_map_slide",
    "add_timeline_table_slides",
]
