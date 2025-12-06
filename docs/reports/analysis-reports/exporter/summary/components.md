# Mission Export System - Components & Architecture

## Overview

The mission export system comprises two interdependent modules (3,518 total
lines) responsible for transforming mission timeline data into deliverable
formats and portable mission archives.

## Components at a Glance

### exporter.py (2220 lines)

Single-leg timeline export generator

**Responsibility:** Transform MissionLegTimeline into 4 export formats

- CSV: Tabular timeline data
- XLSX: Multi-sheet with embedded map/chart images
- PDF: Formatted landscape document with maps and tables
- PPTX: Slide presentation with paginated timeline

**Key Classes:**

- `TimelineExportFormat` - Export format enum (CSV, XLSX, PDF, PPTX)
- `ExportArtifact` - Container for generated export (content, media_type,
  extension)
- `ExportGenerationError` - Exception for export failures

**Main Entry Point:**

```python
generate_timeline_export(format, mission, timeline, parent_mission_id, route_manager, poi_manager) -> ExportArtifact
```

**Dependencies:**

- matplotlib, cartopy, PIL (visualization)
- pandas, openpyxl, reportlab, python-pptx (format generation)
- RouteManager, POIManager (data sources)

---

### package_exporter.py (1298 lines)

Mission-level packaging and archive creation

**Responsibility:** Create portable mission archives with all legs, routes,
POIs, and exports

**Main Features:**

- Per-leg exports (CSV/XLSX/PDF/PPTX for each leg)
- Combined mission exports (single CSV/XLSX/PDF/PPTX for entire mission)
- Archive metadata (mission.json, leg JSONs)
- Route KML files
- POI data (leg-specific and satellite POIs)
- Manifest with archive inventory

**Main Entry Point:**

```python
export_mission_package(mission_id, route_manager, poi_manager) -> IO[bytes]
```

**Archive Structure:**

```text
mission-{id}.zip
├── mission.json (metadata)
├── manifest.json (inventory)
├── legs/ (1 JSON per leg)
├── routes/ (1 KML per route)
├── pois/ (leg-specific + satellites)
└── exports/
    ├── mission/ (combined exports)
    └── legs/ (per-leg exports)
```

---

## Data Flow

```text
Mission Data (Timeline, Route, POIs)
    ↓
[exporter.py: generate_timeline_export()]
    ├─ CSV → timeline.csv
    ├─ XLSX → timeline.xlsx (with embedded images)
    ├─ PDF → report.pdf (formatted document)
    └─ PPTX → slides.pptx (presentation)
    ↓
[package_exporter.py: export_mission_package()]
    ├─ Per-leg exports (4 formats × N legs)
    ├─ Combined mission exports (4 formats × 1 mission)
    ├─ Route KMLs
    ├─ POI JSONs
    ├─ Mission metadata
    └─ Manifest
    ↓
    mission-{id}.zip (portable archive)
```

---

## Current Architecture Issues

### 1. Mixed Concerns (2 files, 3500+ lines)

- Timestamp formatting, data processing, visualization rendering, and packaging
  all tightly coupled
- Hard to modify one aspect without affecting others
- Difficult to unit test visualization without running full export

### 2. Visualization Bloat (~700 lines in exporter.py)

- `_generate_route_map()` alone: 691 lines
  - Map projection, bounds calculation, IDL handling, POI placement, legend
- `_generate_timeline_chart()`: 162 lines
- Heavy matplotlib/cartopy dependencies not needed for CSV/text exports

### 3. Code Duplication in package_exporter.py

- PDF pagination logic appears in both `generate_pptx_export()` and
  `generate_mission_combined_pptx()`
- Table styling duplicated across PDF and PPTX formats
- Worksheet operations scattered across multiple functions

### 4. Tight Manager Coupling

- RouteManager and POIManager deeply nested in visualization code
- Hard to mock for unit tests
- Makes it difficult to add new data sources

### 5. Difficult Error Handling

- Combined exports swallow errors and return error files/sheets
- No clear way to distinguish export failures from system errors
- Hard to provide meaningful user feedback

---

## Critical Dependencies

### External Libraries

**Visualization Stack:**

- matplotlib (charting)
- cartopy (map projections)
- PIL (image handling)

**Format Generators:**

- pandas (data manipulation)
- openpyxl (Excel generation)
- reportlab (PDF generation)
- python-pptx (PowerPoint generation)
- PyPDF2 (PDF merging for combined exports)

**Utilities:**

- zipfile (archive creation)
- tempfile (temporary file management)

### Internal Dependencies

**Data Sources:**

- RouteManager (route data, KML files)
- POIManager (point of interest data)
- Storage loaders (load_mission_v2, load_mission_timeline)

**Models:**

- Mission, MissionLegTimeline, TimelineSegment, TimelineAdvisory
- Transport, TransportState, TimelineStatus
