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
    GroundEntryPoint,
    TimelineExportFormat,
    _generate_route_map,
    _segment_rows,
    generate_timeline_export,
    get_cached_ground_entry_point,
)
from app.mission.exporter.pptx_builder import (
    add_mission_slides_to_presentation,
    add_route_map_slide,
    add_timeline_table_slides,
)
from app.mission.exporter.pptx_styling import (
    BRAND_GOLD,
    CONTENT_GRAY,
    STATUS_CRITICAL,
    STATUS_DEGRADED,
    STATUS_NOMINAL,
    STATUS_SOF,
    TEXT_BLACK,
    TEXT_WHITE,
    add_content_background,
    add_footer_bar,
    add_footer_text,
    add_header_bar,
    add_logo,
    add_segment_separator,
    add_slide_title,
    add_status_badge,
)
from app.mission.exporter.transport_utils import (
    STATE_COLUMNS,
    TRANSPORT_DISPLAY,
)
from app.mission.models import Transport  # Re-exported for package module

__all__ = [
    # Color constants
    "BRAND_GOLD",
    "CONTENT_GRAY",
    "STATE_COLUMNS",
    "STATUS_CRITICAL",
    "STATUS_DEGRADED",
    "STATUS_NOMINAL",
    "STATUS_SOF",
    "TEXT_BLACK",
    "TEXT_WHITE",
    "TRANSPORT_DISPLAY",
    "ExportArtifact",
    "ExportGenerationError",
    "GroundEntryPoint",
    "TimelineExportFormat",
    "Transport",
    "_generate_route_map",
    "_segment_rows",
    "add_content_background",
    "add_footer_bar",
    "add_footer_text",
    # Styling functions
    "add_header_bar",
    "add_logo",
    # PPTX builder functions
    "add_mission_slides_to_presentation",
    "add_route_map_slide",
    "add_segment_separator",
    "add_slide_title",
    "add_status_badge",
    "add_timeline_table_slides",
    "generate_timeline_export",
    "get_cached_ground_entry_point",
]
