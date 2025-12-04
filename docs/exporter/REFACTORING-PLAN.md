# Export Module Refactoring Plan

## Quick Reference

### Files to Refactor

- **exporter.py** (2220 lines) - Single-leg timeline export with 4 formats (CSV,
  XLSX, PDF, PPTX)
- **package_exporter.py** (1298 lines) - Mission-level packaging and archive
  creation
- **Total:** 3518 lines, highly interdependent

### Current Architecture Issues

1. **Mixed Concerns:** Formatting, data processing, rendering, and packaging all
   in two files
1. **Visualization Bloat:** Map/chart generation adds ~700 lines to exporter.py
1. **Code Reuse Problems:** Combined export functions duplicate
   pagination/styling logic from single-leg exports
1. **Tight Coupling:** Manager dependencies deeply nested in visualization code

---

## Refactoring Roadmap

### Phase 1: Pure Utilities (Low Risk, High Value)

**Goal:** Extract pure functions with zero manager/visualization dependencies

#### 1.1 Create `formatting.py` (80-120 lines)

**Source:** exporter.py lines 135-177 + related utilities

**Candidates:**

- `_ensure_timezone(dt: datetime) -> datetime`
- `_mission_start_timestamp(timeline) -> datetime`
- `_format_utc(dt: datetime) -> str`
- `_format_eastern(dt: datetime) -> str`
- `_format_offset(delta: timedelta) -> str`
- `_format_seconds_hms(value: float | int) -> str`
- `_compose_time_block(moment, mission_start) -> str`
- `_humanize_metric_name(key: str) -> str`

**Benefits:**

- Reusable in other modules
- Easy to unit test
- No external dependencies except zoneinfo
- Clear, single responsibility

**Implementation:**

```python
# formatting.py
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

EASTERN_TZ = ZoneInfo("America/New_York")

def ensure_timezone(value: datetime) -> datetime: ...
def mission_start_timestamp(timeline) -> datetime: ...
# ... etc
```

#### 1.2 Create `excel_utils.py` (100-150 lines)

**Source:** package_exporter.py lines 33-102, 104-122

**Candidates:**

- `_create_mission_summary_sheet(wb, mission)`
- `_copy_worksheet_content(source_sheet, target_sheet)`
- `_add_error_sheet(wb, leg_idx, leg, error_message)`

**Benefits:**

- Isolated Excel manipulation
- Reusable in other mission modules
- Single responsibility

#### 1.3 Create `transport_utils.py` (50-80 lines)

**Source:** exporter.py lines 67-194 + constants

**Candidates:**

- `TRANSPORT_DISPLAY` dict
- `STATE_COLUMNS` list
- `STATUS_COLORS` dict
- `_serialize_transport_list(transports)`
- `_is_x_ku_conflict_reason(reason)`
- `_segment_is_x_ku_warning(segment)`
- `_display_transport_state(state, warning_override=False)`

**Benefits:**

- Shared between exporter.py and package_exporter.py
- Consistent transport display across formats
- Easy to modify color schemes/display names

---

### Phase 2: Data Processing Layer (Medium Risk)

**Goal:** Separate data transformation from format generation

#### 2.1 Create `data_builders.py` (180-220 lines)

**Source:** exporter.py lines 1287-1414

**Candidates:**

- `_segment_rows(timeline, mission) -> pd.DataFrame`
- `_advisory_rows(timeline, mission) -> pd.DataFrame`
- `_statistics_rows(timeline) -> pd.DataFrame`
- `_summary_table_rows(timeline, mission) -> pd.DataFrame`

**Dependencies:**

- pandas
- mission models
- formatting.py utilities
- transport_utils.py

**Benefits:**

- Decouples data from rendering
- Easier to test pandas logic
- Enables DataFrame caching
- Reusable for future analytics

#### 2.2 Create `segment_processing.py` (200-250 lines)

**Source:** exporter.py lines 206-385

**Candidates:**

- `_aar_block_rows(timeline, mission, mission_start) -> list`
- `_parse_iso_timestamp(raw: str) -> datetime`
- `_build_aar_record(start, end, mission, timeline, mission_start) -> dict`
- `_segment_at_time(timeline, timestamp) -> TimelineSegment | None`
- `_get_detailed_segment_statuses(start_time, end_time, timeline) -> list`

**Dependencies:**

- mission models
- formatting.py
- transport_utils.py

**Benefits:**

- Isolates AAR logic
- Better testability
- Enables future segment analysis features

---

### Phase 3: Map/Chart Rendering (High Risk)

**Goal:** Abstract visualization dependencies

#### 3.1 Create `map_utils.py` (300-350 lines)

**Source:** exporter.py lines 387-425, + map-related helpers

**Candidates:**

- `_interpolate_position_at_time(target_time, p1, p2)`
- `_base_map_canvas() -> bytes`
- Helper functions for IDL handling, bounds calculation, aspect ratio

**Dependencies:**

- matplotlib, cartopy, PIL
- mission models

**Benefits:**

- Centralizes geospatial logic
- Can be mocked in tests
- Reusable for future mapping features

#### 3.2 Create `render_map.py` (400-500 lines)

**Source:** exporter.py lines 428-1119

**Candidates:**

- `generate_route_map(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes`

**Keep As:** Public function (currently `_generate_route_map()`)

**Dependencies:**

- matplotlib, cartopy
- mission models
- route_manager, poi_manager
- map_utils.py
- segment_processing.py (for status colors)
- transport_utils.py

**Benefits:**

- Isolates heavy visualization
- Can be mocked in tests
- Enables lazy loading

#### 3.3 Create `render_chart.py` (200-250 lines)

**Source:** exporter.py lines 1122-1284

**Candidates:**

- `generate_timeline_chart(timeline) -> bytes`

**Keep As:** Public function (currently `_generate_timeline_chart()`)

**Dependencies:**

- matplotlib
- mission models
- transport_utils.py

---

### Phase 4: Export Formats (Medium Risk)

**Goal:** One module per format for clarity

#### 4.1 Create `export_csv.py` (50-80 lines)

**Source:** exporter.py lines 1443-1450

**Candidates:**

- `generate_csv_export(timeline, mission) -> bytes`

**Dependencies:**

- pandas
- data_builders.py

#### 4.2 Create `export_xlsx.py` (150-200 lines)

**Source:** exporter.py lines 1492-1600

**Candidates:**

- `generate_xlsx_export(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes`

**Dependencies:**

- openpyxl, pandas
- data_builders.py
- render_map.py, render_chart.py

#### 4.3 Create `export_pdf.py` (350-420 lines)

**Source:** exporter.py lines 1603-1869

**Candidates:**

- `generate_pdf_export(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes`

**Dependencies:**

- reportlab
- data_builders.py
- render_map.py, render_chart.py
- formatting.py
- transport_utils.py

**New:** Extract `_pdf_table_styling()` helper for reuse

#### 4.4 Create `export_pptx.py` (350-420 lines)

**Source:** exporter.py lines 1872-2143

**Candidates:**

- `generate_pptx_export(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes`

**Dependencies:**

- python-pptx
- data_builders.py
- render_map.py
- formatting.py
- transport_utils.py

**New:** Extract `_pptx_table_styling()` helper for reuse

---

### Phase 5: Package Assembly (Medium Risk)

**Goal:** Separate ZIP packaging from export generation

#### 5.1 Create `archive_builder.py` (250-300 lines)

**Source:** package_exporter.py lines 853-1152

**Candidates:**

- `_add_mission_metadata_to_zip(zf, mission, manifest_files)`
- `_add_route_kmls_to_zip(zf, mission, route_manager, manifest_files)`
- `_add_pois_to_zip(zf, mission, poi_manager, manifest_files)`
- `_add_per_leg_exports_to_zip(zf, mission, route_manager, poi_manager, manifest_files)`
- `_add_combined_mission_exports_to_zip(zf, mission, route_manager, poi_manager, manifest_files)`
- `_create_export_manifest(mission, manifest_files) -> dict`

**Dependencies:**

- zipfile, json, pathlib
- mission models
- route_manager, poi_manager
- exporter functions (from refactored modules)

**Benefits:**

- Clear separation of packaging concerns
- Easier to maintain archive structure
- Enables future archive formats (tar.gz, tar.bz2)

#### 5.2 Refactor `package_exporter.py` (50-100 lines)

**Remaining:** Only orchestration and error handling

**Candidates:**

- `export_mission_package(mission_id, route_manager, poi_manager) -> IO[bytes]`
- Error handling, temp file management

**Dependencies:**

- archive_builder.py functions
- mission storage

---

### Phase 6: Combined Mission Exports (Lower Priority)

**Goal:** Separate multi-leg aggregation from single-leg export

#### 6.1 Create `combined_exports.py` (500-600 lines)

**Source:** package_exporter.py lines 213-669

**Candidates:**

- `generate_mission_combined_csv(mission, output_path) -> bytes | None`
- `generate_mission_combined_xlsx(mission, route_manager, poi_manager, output_path) -> bytes | None`
- `generate_mission_combined_pptx(mission, route_manager, poi_manager, output_path) -> bytes | None`
- `generate_mission_combined_pdf(mission, route_manager, poi_manager, output_path) -> bytes | None`

**Dependencies:**

- pandas, openpyxl, PyPDF2, python-pptx
- mission models, storage
- export format modules (CSV, XLSX, PDF, PPTX)

**Benefits:**

- Clear multi-leg aggregation logic
- Enables standalone combined export API
- Easier to test pagination logic

---

## Refactoring Sequence

### Order of Implementation

1. **Week 1: Foundation (Phase 1)**
   - Extract formatting.py
   - Extract transport_utils.py
   - Extract excel_utils.py
   - Update imports in existing files

2. **Week 2: Data Layer (Phase 2)**
   - Extract data_builders.py
   - Extract segment_processing.py
   - Add unit tests
   - Update exporter.py to use new modules

3. **Week 3: Visualization (Phase 3)**
   - Extract map_utils.py
   - Extract render_map.py (the big one)
   - Extract render_chart.py
   - Add integration tests

4. **Week 4: Export Formats (Phase 4)**
   - Extract export_csv.py
   - Extract export_xlsx.py
   - Extract export_pdf.py
   - Extract export_pptx.py
   - Refactor exporter.py to dispatcher only

5. **Week 5: Packaging (Phase 5)**
   - Extract archive_builder.py
   - Refactor package_exporter.py
   - Add integration tests

6. **Week 6: Multi-Leg (Phase 6)**
   - Extract combined_exports.py (if time permits)
   - Optional - can be deferred

### Testing Strategy

**Phase 1-2 (Pure Functions):**

- Unit tests for formatting, transport utils, data builders
- No mocking required
- High coverage: 90%+

**Phase 3 (Visualization):**

- Integration tests with mock managers
- Snapshot tests for PNG output
- Performance tests for map generation

**Phase 4 (Export Formats):**

- Format validation tests (CSV structure, XLSX sheets, PDF pages, PPTX slides)
- Round-trip tests (export → validate content)
- Edge case tests (empty timelines, large datasets)

**Phase 5-6 (Packaging):**

- Archive structure tests
- Multi-leg integration tests
- Error handling tests

---

## File Size Estimates

| Module                    | Est. Lines | Source                       |
| ------------------------- | ---------- | ---------------------------- |
| formatting.py             | 100        | exporter.py 135-177 + utils  |
| transport_utils.py        | 70         | exporter.py 67-194           |
| excel_utils.py            | 130        | package_exporter.py 33-122   |
| data_builders.py          | 200        | exporter.py 1287-1414        |
| segment_processing.py     | 220        | exporter.py 206-385          |
| map_utils.py              | 300        | exporter.py helpers          |
| render_map.py             | 450        | exporter.py 428-1119         |
| render_chart.py           | 220        | exporter.py 1122-1284        |
| export_csv.py             | 60         | exporter.py 1443-1450        |
| export_xlsx.py            | 180        | exporter.py 1492-1600        |
| export_pdf.py             | 400        | exporter.py 1603-1869        |
| export_pptx.py            | 400        | exporter.py 1872-2143        |
| archive_builder.py        | 300        | package_exporter.py 853-1152 |
| combined_exports.py       | 550        | package_exporter.py 213-669  |
| exporter.py (new)         | 50         | Dispatcher only              |
| package_exporter.py (new) | 80         | Orchestration only           |
| **Total**                 | **3620**   | ~100 lines added for imports |

---

## Dependencies Graph (Post-Refactoring)

```text
Pure Utilities (No external data dependencies):
  - formatting.py (zoneinfo only)
  - transport_utils.py (no dependencies)

Data Processing:
  - data_builders.py → formatting.py, transport_utils.py
  - segment_processing.py → formatting.py, transport_utils.py

Rendering:
  - map_utils.py → (matplotlib, cartopy, PIL)
  - render_map.py → map_utils, segment_processing, transport_utils
  - render_chart.py → transport_utils, matplotlib

Export Formats:
  - export_csv.py → data_builders
  - export_xlsx.py → data_builders, render_map, render_chart
  - export_pdf.py → data_builders, render_map, render_chart
  - export_pptx.py → data_builders, render_map

Core Exporters:
  - exporter.py (dispatcher) → export_csv, export_xlsx, export_pdf, export_pptx

Packaging:
  - excel_utils.py (openpyxl utilities)
  - archive_builder.py → exporter (all formats)
  - combined_exports.py → exporter (all formats), excel_utils
  - package_exporter.py (orchestrator) → archive_builder, combined_exports

Benefit: Clear layers, easy to test, easy to mock visualization for unit tests
```

---

## Backward Compatibility

### Public API (exporter.py)

**Keep Unchanged:**

- `TimelineExportFormat` enum
- `ExportArtifact` dataclass
- `ExportGenerationError` exception
- `generate_timeline_export()` function

**Deprecate (with 2-release warning):**

- All `_private` functions (they're internal)
- Direct imports of visualization functions

### Public API (package_exporter.py)

**Keep Unchanged:**

- `export_mission_package()` function
- `generate_mission_combined_*()` functions
- `ExportPackageError` exception

**Deprecate:**

- All `_private` functions (they're internal)

---

## Risk Assessment

| Phase | Risk   | Mitigation                                |
| ----- | ------ | ----------------------------------------- |
| 1     | Low    | Pure functions, no state changes          |
| 2     | Low    | Pandas logic, easy to unit test           |
| 3     | High   | Visualization, snapshot tests needed      |
| 4     | Medium | Format-specific, separate test per format |
| 5     | Medium | Packaging logic, integration tests        |
| 6     | Low    | Built on stable Phase 4                   |

---

## Success Criteria

1. **Code Quality**
   - Each module has clear, single responsibility
   - Cyclomatic complexity per function < 10
   - Test coverage > 85% (excluding visualization)

2. **Performance**
   - No regression in export generation time
   - Memory usage stable or improved (lazy loading benefits)

3. **Maintainability**
   - Any format change requires < 50 lines modified
   - New format addition takes < 4 hours
   - Visualization improvements isolated to render\_\*.py

4. **Documentation**
   - Each module has docstring explaining purpose
   - Data flow diagram accurate
   - Integration points documented
