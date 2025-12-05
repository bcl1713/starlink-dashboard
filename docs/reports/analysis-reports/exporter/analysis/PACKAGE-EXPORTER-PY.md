# Package Exporter Analysis (package_exporter.py)

## package_exporter.py - Detailed Analysis

### Package Exporter: Classes and Data Structures

1. **ExportPackageError** (line 29)
   - Custom exception for package export failures

### Package Exporter: Core Functions by Category

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

### Package Exporter: Key Dependencies

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
