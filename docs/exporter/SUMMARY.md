# Mission Export System - Executive Summary

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

---

## Export Format Details

### CSV Export

- Simple tabular format
- Single sheet: segment timeline data
- Columns: Segment #, Mission ID, Status, Start/End times (UTC/Eastern/T+),
  Duration, Transport states, Impacted systems, Reasons, Metadata
- Generated from `_segment_rows()` DataFrame

### XLSX Export

- Multi-sheet workbook:
  1. **Summary**: Map image (750x500px), Timeline chart (850x300px), Summary
     table with color coding
  1. **Timeline**: Full segment rows (detailed version)
  1. **Advisories**: Timeline advisory events (if any)
  1. **Statistics**: Mission metrics (if any)
- Color coding: Green (NOMINAL), Yellow (DEGRADED), Red (CRITICAL)
- Images embedded as OpenpyxlImage objects
- Column widths optimized for readability

### PDF Export

- Landscape letter-size pages
- Content:
  1. Header with logo, mission name
  2. Statistics table
  3. Route map (6.5" x 4.3") with color-coded segments, POI markers, legend
  4. Transport timeline chart (7" x 2.3")
  5. Detailed timeline table (paginated as needed)
- Advanced styling: Row alternation, per-column coloring, safety-of-flight
  detection
- Generated using reportlab.platypus

### PPTX Export

- Multi-slide presentation:
  1. Route map slide (9"W x 6.5"H)
  2. Timeline table slides (paginated, 10 rows per slide, min 3 on last slide)
- Color-coded rows: Red (CRITICAL, 2+ bad systems), Yellow
  (DEGRADED/WARNING/SOF), White (nominal)
- Generated using python-pptx
- Same pagination logic as PDF

### Combined Exports (package_exporter.py)

**Combined CSV:**

- Single file with all legs concatenated
- Leg boundary markers (LEG START, LEG END)
- Includes segments and advisories for each leg

**Combined XLSX:**

- Mission Summary sheet (overview + leg index)
- Imported sheets from each leg's XLSX (with L{idx} prefix)
- One sheet per leg's summary, timeline, advisories, statistics

**Combined PDF:**

- Cover page (mission overview, table of contents)
- Per-leg sections with dividers
- Summary page
- Generated by merging individual leg PDFs

**Combined PPTX:**

- Title slide (mission name, leg count)
- Per-leg slides (reuses `generate_pptx_export()` logic)
- Native generation (not combining individual leg PPTXs)

---

## Key Algorithms & Techniques

### Timestamp Formatting

Three parallel formats for mission times:

- **UTC:** "2024-12-03 14:30Z"
- **Eastern:** "2024-12-03 09:30EST" (DST-aware)
- **Mission Relative:** "T+02:30" (hours:minutes from mission start)

### Map Generation (4K, 3840x2160 @ 300 DPI)

**Features:**

- Cartopy map projections with dynamic centering
- International Date Line (IDL) crossing handling (normalizes to 0-360 space)
- Bounds calculation with aspect ratio matching to canvas
- Color-coded route segments based on timeline status
- POI markers: Departure (green), Arrival (red), Waypoints (blue diamond)
- Satellite transitions and AAR blocks as POIs
- Legend inset with status colors

**IDL Handling:**

- Detects lon jumps > 180 degrees
- Centers projection on route midpoint
- Normalizes coordinates to 0-360 range
- Splits segments at boundaries for proper rendering

### Status Color Mapping

- **Nominal** (green #2ecc71) - All systems operational
- **Degraded** (yellow #f1c40f) - Some systems offline or warning
- **Critical** (red #e74c3c) - 2+ bad systems or safety-of-flight issue
- **Unknown** (gray #95a5a6) - No timeline data

### Safety-of-Flight Detection

- Checked via reason strings: "safety-of-flight" or "aar"
- Overrides status display to "SOF" in tables
- Applied to both PDF and PPTX rendering

### Table Pagination (PPTX)

- 10 rows per slide maximum
- Minimum 3 rows on final slide
- If last chunk < 3 rows, redistributes items between last two chunks
- Ensures readable tables on fixed-size slides

---

## Performance Characteristics

### Map Generation

- ~5-15 seconds for typical routes (depends on cartopy complexity)
- Cartopy coastline data: ~25 MB on disk
- PNG output: 2-5 MB per map (4K resolution, high quality)

### Chart Generation

- ~1-2 seconds per timeline
- PNG output: 100-300 KB per chart

### XLSX Generation

- Per-leg: ~5-10 seconds (includes map/chart embedding)
- Combined multi-leg: ~30-60 seconds (N × leg time)
- Image scaling and embedding: most expensive operation

### PDF Generation

- Per-leg: ~3-8 seconds
- Combined multi-leg: ~20-50 seconds (PDF merging is fast)

### ZIP Archive

- Per-leg exports: ~5-15 seconds per leg
- Combined exports: ~30-60 seconds
- POI/KML archival: negligible (<100 ms)
- Archive creation (zip compression): 5-10 seconds

### Total End-to-End

- Single leg (all 4 formats): ~30-50 seconds
- 3-leg mission (all formats, combined + per-leg): ~3-5 minutes
- Output size: ~15-30 MB (depending on map resolution)

---

## Integration Points

### RouteManager Integration

```python
route = route_manager.get_route(mission.route_id)
# Use: route.points (list of Waypoint with lat/lon/expected_arrival_time)
#      route.waypoints (with roles: departure, arrival)
# Files: routes_dir/{route_id}.kml
```

### POIManager Integration

```python
pois = poi_manager.list_pois(route_id=..., mission_id=...)
# POI fields: id, name, latitude, longitude, category, role
# Uses: Mission event POIs (AAR, satellite swaps, Ka transitions)
```

### Storage Integration

```python
mission = load_mission_v2(mission_id)
timeline = load_mission_timeline(leg_id)
# Returns: Pydantic models with full nested structure
```

---

## Recommended Refactoring

See `EXPORTER-REFACTORING-PLAN.md` for detailed plan.

**Quick Summary:**

1. Extract pure utilities (formatting, transport display)
2. Separate data processing layer (DataFrames from rendering)
3. Isolate visualization (map, chart generation)
4. Split by format (CSV, XLSX, PDF, PPTX modules)
5. Extract packaging logic
6. Extract combined export logic (lower priority)

**Result:** 2 monolithic files → 16 focused modules

- Each module: Single responsibility, clear dependencies
- Easier to test, modify, and extend
- No regression in functionality or performance

---

## Testing Recommendations

### Unit Tests (Phase 1-2)

- Formatting functions (100% coverage)
- Transport display utilities (100% coverage)
- Data builders (90%+ coverage)
- No mocking needed

### Integration Tests (Phase 3-4)

- Visualization rendering (snapshot tests for PNG)
- Format generation (structure validation)
- Manager integration (mock managers)
- Performance benchmarks

### System Tests (Phase 5-6)

- Archive structure and contents
- Multi-leg export consistency
- End-to-end workflows
- Error handling and recovery

---

## Deployment Notes

### Docker Considerations

- Matplotlib configured for headless mode (Agg backend)
- Cartopy data directory: ~25 MB, mounted as volume
- PNG generation: CPU intensive, consider async processing for large exports

### System Requirements

- RAM: 2+ GB per export job (image buffering)
- CPU: 2+ cores (Cartopy uses threading)
- Disk: Temp space for archive creation (~50-100 MB per job)

### Configuration

- `EASTERN_TZ = ZoneInfo("America/New_York")` - Hardcoded, consider
  parametrization
- `LOGO_PATH = assets/logo.png` - Must exist for header image
- Sheet name limit: 31 characters (Excel standard, enforced in
  package_exporter.py)

---

## Future Enhancement Opportunities

1. **Streaming Exports:** Replace full buffering with streaming for large
   archives
1. **Format Plugins:** Plugin architecture for custom export formats
1. **Async Processing:** Async/celery for long-running exports
1. **Caching:** Cache DataFrames and images to reduce re-computation
1. **Configuration:** Externalize colors, formats, templates
1. **Export Templates:** Custom PDF/PowerPoint templates
1. **Database Exports:** Direct database export (CSV/Parquet)
1. **Real-time Updates:** WebSocket for export progress
1. **Batch Operations:** Export multiple missions in one request
1. **Archive Formats:** Tar.gz, tar.bz2, 7z support
