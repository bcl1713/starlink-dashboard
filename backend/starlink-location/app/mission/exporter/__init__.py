"""Mission timeline export module.

Transforms `MissionLegTimeline` data into CSV, XLSX, PDF, and PPTX deliverables
with parallel timestamp formats (UTC, Eastern, and T+ offsets) suitable for
customer-facing mission briefs.

This module is organized into:
- formatting: Pure timestamp and value formatting functions
- transport_utils: Transport state and display utilities
- excel_utils: Excel workbook manipulation utilities
- __main__: Core export generation logic and format handlers
"""

from __future__ import annotations

# Public API - re-export main classes and functions
from app.mission.exporter.__main__ import (
    ExportArtifact,
    ExportGenerationError,
    TimelineExportFormat,
    generate_timeline_export,
)

__all__ = [
    "ExportArtifact",
    "ExportGenerationError",
    "TimelineExportFormat",
    "generate_timeline_export",
]
