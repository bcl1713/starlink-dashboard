# Mission Export Architecture Analysis

## File Overview

### exporter.py (2220 lines)

**Primary Purpose:** Mission timeline export utilities transforming
`MissionLegTimeline` data into customer-facing deliverables (CSV, XLSX, PDF,
PPTX) with parallel timestamp formats (UTC, Eastern, T+ offsets).

**Primary Responsibility:** Single-leg/individual timeline export generation
with rich visualization and formatting

---

## exporter.py - Detailed Analysis

### Classes and Data Structures

1. **ExportGenerationError** (line 104)
   - Custom exception for export failures
   - Used throughout the module for validation and generation failures

2. **TimelineExportFormat** (line 108)
   - Enum: CSV, XLSX, PDF, PPTX
   - Includes `from_string()` class method for case-insensitive parsing
   - Handles validation with ExportGenerationError

3. **ExportArtifact** (line 126)
   - Dataclass with slots
   - Fields: content (bytes), media_type (str), extension (str)
   - Container for the generated export file

### Core Functions by Category

#### Timestamp & Formatting Utilities (Lines 135-177)

- `_ensure_timezone()` - Converts naive datetimes to UTC
- `_mission_start_timestamp()` - Infers mission zero point from earliest segment
- `_format_utc()` - UTC string format: "YYYY-MM-DD HH:MMZ"
- `_format_eastern()` - Eastern time with DST awareness
- `_format_offset()` - T+/-HH:MM format relative to mission start
- `_format_seconds_hms()` - Converts seconds to HH:MM:SS format
- `_compose_time_block()` - Combines UTC, Eastern, and T+ offset

#### Transport Display & Validation (Lines 67-194)

- Transport display mappings: X-Band, CommKa, StarShield
- `_serialize_transport_list()` - Converts Transport enums to display names
- `_is_x_ku_conflict_reason()` - Identifies X-Ku conflict warnings
- `_segment_is_x_ku_warning()` - Flags X-Ku specific warnings
- `_display_transport_state()` - Transport state with warning override

#### Data Processing for Segments (Lines 206-385)

- `_aar_block_rows()` - Extracts AAR (After Action Report) blocks from
  statistics
- `_parse_iso_timestamp()` - ISO8601 timestamp parsing with fallback
- `_build_aar_record()` - Constructs AAR row data
- `_segment_at_time()` - Finds segment containing a given timestamp
- `_get_detailed_segment_statuses()` - Color-codes route segments by timeline
  status
  - Handles AAR blocks and segment gaps
  - Maps segment status to colors: nominal (green), degraded (yellow), critical
    (red)

#### Position Interpolation (Lines 387-425)

- `_interpolate_position_at_time()` - Linear interpolation between waypoints
- Handles International Date Line (IDL) crossing logic
- Used for POI placement and map segment coloring

#### Map Generation (Lines 428-1119)

- `_generate_route_map()` - LARGE function generating 4K PNG (3840x2160 @ 300
  DPI)
  - **Phases 9-12 implementation:**
    - Phase 9: Route line drawing with IDL handling
    - Phase 10: Color-coded segments based on timeline status
    - Phase 11: POI markers (departure, arrival, mission events, satellite
      swaps)
    - Phase 12: Legend inset
  - Uses Cartopy for map projection, Matplotlib for rendering
  - Handles Pacific-centered projections for IDL crossings
  - Bounds calculation with 5% padding
  - Aspect ratio matching for canvas vs geographic bounds
  - Color-coded route segments: nominal/degraded/critical
  - POI integration from route_manager and poi_manager
  - Deployment: Matplotlib in Agg (headless) mode for Docker

#### Timeline Chart (Lines 1122-1284)

- `_generate_timeline_chart()` - Horizontal bar chart (16:5 aspect, 300 DPI PNG)
  - Three transport rows: Ku (StarShield), Ka (CommKa), X-Band
  - State colors: green (AVAILABLE), amber (DEGRADED), red (OFFLINE)
  - T+ time formatting on x-axis
  - 1-hour gridlines

#### DataFrame Builders (Lines 1287-1414)

- `_segment_rows()` - Timeline segments as pandas DataFrame
  - Columns: Segment #, Mission ID/Name, Status, Start/End times, Duration,
    Transport states, Impacted Transports, Reasons, Metadata
  - Combines regular segments with AAR blocks
  - Sorts by start time, then AAR priority

- `_advisory_rows()` - Timeline advisories as DataFrame
  - Columns: Mission ID, UTC/Eastern timestamps, T Offset, Transport, Severity,
    Event Type, Message, Metadata
  - May be empty if no advisories

- `_statistics_rows()` - Mission statistics as DataFrame
  - Humanizes metric names
  - Formats seconds values as HH:MM:SS
  - Filters underscore-prefixed keys

#### Export Format Generators (Lines 1443-2143)

**CSV Export** (Lines 1443-1450)

- Simple wrapper: pandas DataFrame to CSV
- Uses segment_rows() data

**XLSX Export** (Lines 1492-1600)

- Multi-sheet structure:
  1. Summary: Map image (750x500px), Timeline chart (850x300px), Summary table
  2. Timeline: Full segment data
  3. Advisories: Advisory events (if present)
  4. Statistics: Mission metrics (if present)
- Color-coded summary rows: green (NOMINAL), yellow (DEGRADED), red (CRITICAL)
- Column widths optimized for readability
- Images embedded as OpenpyxlImage objects

**PDF Export** (Lines 1603-1869)

- Landscape letter-size pages
- Content: 5. Header with logo (if available), mission name 6. Statistics
  table 7. Route map image (6.5" x 4.3") 8. Transport timeline chart (7" x
  2.3") 9. Timeline segments table (paginated)
- Advanced styling:
  - Status coloring: red for CRITICAL, yellow for DEGRADED/WARNING/SOF
  - Per-column coloring for transport states
  - Safety-of-Flight (SOF) detection from reasons
  - Alternating row backgrounds
  - Font sizing and alignment

**PPTX Export** (Lines 1872-2143)

- Slide 1: Route map (9"W x 6.5"H)
- Slides 2+: Timeline table (paginated, 10 rows/slide, min 3 rows on last slide)
- Pagination logic ensures minimum 3 rows on final slide
- Column widths: [0.6, 1.0, 1.75, 1.75, 1.0, 1.0, 1.0, 1.0, 1.5] weights
- Color-coded rows: red (CRITICAL, 2+ bad systems), yellow
  (DEGRADED/WARNING/SOF), white (nominal)
- SOF detection same as PDF

#### Utility Functions

- `_load_logo_flowable()` - Loads logo image (max 1.6"W x 0.9"H) from assets
- `_base_map_canvas()` - Generates blank 4K map with coastlines/borders/ocean
- `_humanize_metric_name()` - Converts metric keys to display names

#### Main Entry Point (Lines 2173-2220)

- `generate_timeline_export()` - Router function
  - Accepts: format (TimelineExportFormat), mission, timeline,
    parent_mission_id, route_manager, poi_manager
  - Returns: ExportArtifact with content/media_type/extension
  - Dispatches to format-specific generators

### Key Dependencies

**External Libraries:**

- matplotlib, cartopy (map visualization)
- PIL (image handling)
- pandas (data manipulation)
- openpyxl (Excel generation)
- reportlab (PDF generation)
- python-pptx (PowerPoint generation)

**Internal Dependencies:**

- app.mission.models (Mission, MissionLegTimeline, TimelineSegment, etc.)
- app.services.poi_manager (POIManager)
- app.services.route_manager (RouteManager)

**Constants:**

- EASTERN_TZ = ZoneInfo("America/New_York")
- STATUS_COLORS = {nominal: green, degraded: yellow, critical: red, unknown:
  gray}
- LOGO_PATH = assets/logo.png

---

## package_exporter.py - Detailed Analysis

### Classes and Data Structures

1. **ExportPackageError** (line 29)
   - Custom exception for package export failures

### Core Functions by Category

#### Excel Worksheet Operations (Lines 33-102)

- `_create_mission_summary_sheet()` - Creates "Mission Summary" sheet
  - Content: Mission name/ID, leg count, generation timestamp
  - Leg index table: Leg #, ID, Name, Description
  - Column widths optimized

- `_copy_worksheet_content()` - Deep copies worksheets from one workbook to
  another
  - Copies cell values, formatting (font, border, fill, alignment)
  - Copies column widths, row heights, merged cells
  - Copies embedded images

- `_add_error_sheet()` - Creates error sheet for failed exports
  - Shows leg name/ID and error message

#### Per-Leg XLSX Processing (Lines 124-210)

- `_process_leg_xlsx_export()` - Processes single leg's XLSX export
  - Loads leg timeline
  - Calls generate_timeline_export(TimelineExportFormat.XLSX, leg, leg_timeline)
  - Copies sheets from leg workbook to main workbook with prefix
  - Sheet name transformation: "Summary" -> "L1 Leg Name", others -> "L1
    Timeline"
  - Excel sheet name length limit: 31 characters
  - Error handling: Catches ExportGenerationError, ValueError, KeyError,
    BadZipFile, general Exception
  - Adds error sheets on failure

#### Combined Mission CSV Export (Lines 213-315)

- `generate_mission_combined_csv()` - Combines all leg timelines into single CSV
  - Header: Mission name, leg count, generation timestamp
  - For each leg:
    - Leg boundary markers (LEG START, LEG END)
    - Segment rows: Leg ID, Name, Event Time, Type, Details
    - Advisory rows: Leg ID, Name, Timestamp, Advisory type, Severity + Message
  - Optional file output or bytes return
  - Error logging per leg

#### Combined Mission XLSX Export (Lines 318-375)

- `generate_mission_combined_xlsx()` - Creates multi-sheet XLSX with mission
  overview
  - First sheet: Mission Summary (overview + leg index)
  - Per-leg sheets: Imports all sheets from each leg's XLSX export
  - Sheet naming: "L{idx} Leg Name" for summary, "L{idx} {original_name}"
  - Error handling: Returns error workbook on failure
  - Supports output to file or bytes

#### Combined Mission PPTX Export (Lines 378-669)

- `generate_mission_combined_pptx()` - Creates presentation with all legs
  - Slide 1: Title slide (mission name, leg count)
  - Per-leg slides: Uses generate_timeline_export(PPTX, leg, leg_timeline)
  - Reuses PPTX generation logic from exporter.py
  - Imports: \_generate_route_map(), \_segment_rows(), TRANSPORT_DISPLAY,
    STATE_COLUMNS, Transport
  - Pagination: 10 rows/slide, minimum 3 on last slide
  - Error slides on failure
  - Supports output to file or bytes

#### Combined Mission PDF Export (Lines 672-850)

- `generate_mission_combined_pdf()` - Creates merged PDF report
  - Uses PyPDF2.PdfMerger to combine PDFs
  - Cover page: Mission name, ID, leg count, table of contents
  - Per-leg sections: Each leg's full PDF (from generate_timeline_export(PDF,
    leg, leg_timeline))
  - Section dividers: "Leg N" page before each leg PDF
  - Summary page: Leg listing
  - Error handling: Creates error pages for failed legs, returns error PDF on
    failure
  - Supports output to file or bytes

#### Mission Metadata Archival (Lines 853-873)

- `_add_mission_metadata_to_zip()` - Adds mission.json and leg JSONs to zip
  - mission.json: Full mission model dump
  - legs/: Individual leg JSON files (one per leg)
  - Tracking: Adds paths to manifest_files["legs"] and
    manifest_files["mission_data"]

#### Route KML Archival (Lines 876-915)

- `_add_route_kmls_to_zip()` - Adds route KML files for each leg
  - Reads KML from routes_dir/{route_id}.kml
  - Stores in routes/{route_id}.kml
  - Skips legs without route_id or missing files
  - Error logging per leg

#### POI Data Archival (Lines 918-991)

- `_add_pois_to_zip()` - Adds mission-specific and satellite POIs
  - Per-leg POI files: pois/{leg_id}-pois.json
  - Filters POIs by mission_id and leg.route_id
  - Separate file: pois/satellites.json for category="satellite" POIs
  - JSON structure includes leg/mission/route IDs, POI count
  - Tracks all POI IDs for deduplication

#### Per-Leg Export Generation (Lines 994-1082)

- `_add_per_leg_exports_to_zip()` - Generates CSV, XLSX, PPTX, PDF per leg
  - For each leg, creates 4 exports:
    - exports/legs/{leg_id}/timeline.csv
    - exports/legs/{leg_id}/timeline.xlsx
    - exports/legs/{leg_id}/slides.pptx
    - exports/legs/{leg_id}/report.pdf
  - Calls generate_timeline_export() with appropriate format
  - Uses parent_mission_id for context
  - Error logging per leg and format

#### Combined Mission Export Generation (Lines 1085-1152)

- `_add_combined_mission_exports_to_zip()` - Generates mission-level combined
  exports
  - Uses tempfile.NamedTemporaryFile for streaming
  - Generates and stores:
    - exports/mission/mission-timeline.csv
    - exports/mission/mission-timeline.xlsx
    - exports/mission/mission-slides.pptx
    - exports/mission/mission-report.pdf
  - Delegates to: generate_mission_combined_csv/xlsx/pptx/pdf()

#### Manifest Creation (Lines 1155-1195)

- `_create_export_manifest()` - Generates manifest.json
  - Version 2.0
  - Export metadata: mission_id, mission_name, description, leg_count, timestamp
  - File structure: Organized by category
  - Statistics: File counts by category, total files

#### Main Entry Point (Lines 1198-1298)

- `export_mission_package()` - Creates complete mission zip archive
  - Loads mission from storage (load_mission_v2)
  - Creates tempfile.NamedTemporaryFile for output (delete=True for cleanup)
  - Orchestrates 6 steps:
    1. Add mission metadata (\_add_mission_metadata_to_zip)
    2. Add route KMLs (\_add_route_kmls_to_zip)
    3. Add POI data (\_add_pois_to_zip)
    4. Generate per-leg exports (\_add_per_leg_exports_to_zip)
    5. Generate mission-level exports (\_add_combined_mission_exports_to_zip)
    6. Create manifest (inline)
  - Returns file-like object with zip content
  - Caller must close to trigger temp file deletion

### Key Dependencies

**External Libraries:**

- openpyxl (Excel manipulation, sheet operations)
- PyPDF2 (PDF merging)
- reportlab (PDF canvas generation)
- python-pptx (PowerPoint creation)
- zipfile (archive creation)
- tempfile (temporary file handling)

**Internal Dependencies:**

- app.mission.models (Mission)
- app.mission.storage (load_mission_v2, load_mission_timeline)
- app.mission.exporter (generate_timeline_export, TimelineExportFormat,
  ExportGenerationError)
- app.services.route_manager (RouteManager)
- app.services.poi_manager (POIManager)

---

## Export Format Summary

### Supported Formats

| Format | Purpose       | Size   | Contents                                                 |
| ------ | ------------- | ------ | -------------------------------------------------------- |
| CSV    | Tabular data  | Small  | Segment timeline data                                    |
| XLSX   | Spreadsheet   | Medium | Summary sheet + images, Timeline, Advisories, Statistics |
| PDF    | Print/archive | Large  | Maps, charts, formatted tables                           |
| PPTX   | Presentation  | Large  | Map slide, paginated timeline tables                     |

### Package Structure (from export_mission_package)

```text
mission-{id}.zip
├── mission.json                  (mission metadata)
├── manifest.json                 (archive inventory)
├── legs/
│   ├── {leg-id-1}.json
│   └── {leg-id-2}.json
├── routes/
│   ├── {route-id-1}.kml
│   └── {route-id-2}.kml
├── pois/
│   ├── {leg-id-1}-pois.json
│   ├── {leg-id-2}-pois.json
│   └── satellites.json
└── exports/
    ├── mission/
    │   ├── mission-timeline.csv
    │   ├── mission-timeline.xlsx
    │   ├── mission-slides.pptx
    │   └── mission-report.pdf
    └── legs/
        ├── {leg-id-1}/
        │   ├── timeline.csv
        │   ├── timeline.xlsx
        │   ├── slides.pptx
        │   └── report.pdf
        └── {leg-id-2}/
            ├── timeline.csv
            ├── timeline.xlsx
            ├── slides.pptx
            └── report.pdf
```

---

## Decomposition Boundaries

### Logical Separation Opportunities

#### 1. **Timeline Rendering Module** (from exporter.py)

**Candidates:** Map generation, Timeline chart, PDF/PPTX table styling
**Rationale:** Heavy visualization dependencies (matplotlib, cartopy, reportlab,
pptx) **Exports:** \_generate_route_map(), \_generate_timeline_chart() **Imports
from:** exporter would still need (models, POIManager, RouteManager)

#### 2. **Timestamp & Formatting Module** (from exporter.py)

**Candidates:** All formatting utilities, humanization **Rationale:** Pure
functions, no dependencies except timezone **Functions:** \_ensure_timezone(),
\_format_utc(), \_format_eastern(), \_format_offset(), \_format_seconds_hms(),
\_compose_time_block(), \_humanize_metric_name() **Usage:** Referenced by
segment_rows, data builders

#### 3. **Data Processing Module** (from exporter.py)

**Candidates:** Segment rows, advisory rows, statistics rows, DataFrame builders
**Rationale:** Pure pandas data transformation, independent of export format
**Functions:** \_segment_rows(), \_advisory_rows(), \_statistics_rows(),
\_summary_table_rows() **Imports:** pandas, mission models

#### 4. **Map Utilities Module** (from exporter.py)

**Candidates:** Position interpolation, status coloring, POI collection, IDL
handling **Rationale:** Used by \_generate_route_map() and potentially reusable
**Functions:** \_interpolate_position_at_time(),
\_get_detailed_segment_statuses(), route_manager/poi_manager integration logic
**Imports:** mission models, managers

#### 5. **Package Assembly Module** (from package_exporter.py)

**Candidates:** ZIP archiving logic, manifest creation **Rationale:**
Orchestration of file collection and packaging **Functions:**
\_add_mission_metadata_to_zip(), \_add_route_kmls_to_zip(), \_add_pois_to_zip(),
\_create_export_manifest(), export_mission_package() **Imports:** zipfile,
tempfile, mission models, managers

#### 6. **Worksheet Operations Module** (from package_exporter.py)

**Candidates:** Excel worksheet copying and manipulation **Rationale:** Reusable
Excel utility functions **Functions:** \_copy_worksheet_content(),
\_create_mission_summary_sheet(), \_add_error_sheet() **Imports:** openpyxl

#### 7. **Combined Mission Export Module** (from package_exporter.py)

**Candidates:** generate_mission_combined_csv/xlsx/pptx/pdf() **Rationale:**
Mission-level aggregation separate from per-leg logic **Functions:**
generate_mission_combined_csv(), generate_mission_combined_xlsx(),
generate_mission_combined_pptx(), generate_mission_combined_pdf() **Imports:**
pandas, openpyxl, PyPDF2, pptx, exporter functions, storage loaders

---

## Critical Integration Points

### Data Flow

```text
Mission/Timeline Data
  ↓
[exporter.py]
  ├─ Segment Rows (CSV, XLSX)
  ├─ Map Image (PNG) → XLSX, PDF, PPTX
  ├─ Timeline Chart (PNG) → XLSX, PDF
  └─ Formatted Table → PDF, PPTX
  ↓
[package_exporter.py]
  ├─ Per-Leg CSV/XLSX/PDF/PPTX → ZIP
  ├─ Combined Mission CSV/XLSX/PDF/PPTX → ZIP
  ├─ Route KMLs → ZIP
  ├─ POI JSON → ZIP
  └─ Mission Metadata → ZIP
```

### Manager Dependencies

1. **RouteManager**
   - Used by: \_generate_route_map(), \_add_route_kmls_to_zip()
   - Methods: get_route(), list_routes(), routes_dir property

2. **POIManager**
   - Used by: \_generate_route_map() (for POI markers), \_add_pois_to_zip()
   - Methods: list_pois(), with optional route_id/mission_id filters

3. **Storage (implicit)**
   - Used by: package_exporter.py
   - Functions: load_mission_v2(), load_mission_timeline()

### Format-Specific Dependencies

**Map/Chart Visualization (exporter.py):**

- matplotlib.pyplot, cartopy, PIL → \_generate_route_map(),
  \_generate_timeline_chart()
- Used by: XLSX (embedded), PDF (embedded), PPTX (embedded)

**PDF Generation (exporter.py & package_exporter.py):**

- reportlab.platypus → generate_pdf_export(), generate_mission_combined_pdf()
- Styling: Colors, fonts, table layouts, page breaks

**Excel Manipulation (package_exporter.py):**

- openpyxl → \_copy_worksheet_content(), \_process_leg_xlsx_export(),
  generate_mission_combined_xlsx()

**PowerPoint Creation (exporter.py & package_exporter.py):**

- python-pptx → generate_pptx_export(), generate_mission_combined_pptx()
- Pagination logic for timeline tables

**ZIP Archiving (package_exporter.py):**

- zipfile → export_mission_package()
- Streaming via tempfile

---

## Suggested Refactoring Strategy

### Phase 1: Low-Risk Extraction

1. Extract timestamp/formatting utilities → `formatting.py` (no dependencies on
   models except datetime)
1. Extract DataFrame builders → `data_builders.py` (pandas-only, depends on
   exporter utilities)
1. Extract Excel worksheet ops → `excel_utils.py` (openpyxl-only)

### Phase 2: Medium-Risk Extraction

1. Extract map utilities → `map_utils.py` (position interpolation, status
   coloring, POI integration)
1. Extract combined mission exports → `combined_exports.py` (CSV, XLSX, PDF,
   PPTX aggregation)

### Phase 3: High-Risk (Visualization Layer)

1. Extract render modules → `render_map.py`, `render_chart.py`, `render_pdf.py`,
   `render_pptx.py`
1. Share common table styling logic
1. Abstract visualization dependencies

### Phase 4: Package Assembly

1. Extract ZIP logic → `package_assembly.py`
2. Keep export_mission_package() as orchestrator
3. Clear separation of concerns

---

## Dependency Graph Summary

```text
exporter.py:
  - timestamp formatting (pure)
    └─ segment/advisory rows
      └─ CSV export
    └─ composite time blocks
      └─ PDF/PPTX tables
  - map generation (cartopy, matplotlib)
    ├─ route manager
    ├─ poi manager
    └─ map image → XLSX/PDF/PPTX
  - timeline chart (matplotlib)
    └─ chart image → XLSX/PDF
  - PDF rendering (reportlab)
    ├─ map image
    ├─ chart image
    └─ formatted table
  - PPTX rendering (python-pptx)
    ├─ map image
    └─ paginated table

package_exporter.py:
  - mission metadata archival (json)
  - route KML archival (route manager)
  - POI archival (poi manager)
  - per-leg exports (calls exporter.py)
    ├─ CSV
    ├─ XLSX (with images)
    ├─ PDF
    └─ PPTX
  - combined exports (calls exporter.py functions)
    ├─ CSV (pandas)
    ├─ XLSX (openpyxl)
    ├─ PDF (PyPDF2 merging)
    └─ PPTX (native generation)
  - ZIP assembly (zipfile + tempfile)
  - manifest creation (json)
```
