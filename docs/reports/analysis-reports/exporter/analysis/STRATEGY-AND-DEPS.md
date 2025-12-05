# Architecture Strategy and Dependencies

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
