# Refactoring Roadmap: Phases 4-6

## Phase 4: Export Formats (Medium Risk)

**Goal:** One module per format for clarity

### 4.1 Create `export_csv.py` (50-80 lines)

**Source:** exporter.py lines 1443-1450

**Candidates:**

- `generate_csv_export(timeline, mission) -> bytes`

**Dependencies:**

- pandas
- data_builders.py

### 4.2 Create `export_xlsx.py` (150-200 lines)

**Source:** exporter.py lines 1492-1600

**Candidates:**

```python
generate_xlsx_export(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes
```

**Dependencies:**

- openpyxl, pandas
- data_builders.py
- render_map.py, render_chart.py

### 4.3 Create `export_pdf.py` (350-420 lines)

**Source:** exporter.py lines 1603-1869

**Candidates:**

```python
generate_pdf_export(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes
```

**Dependencies:**

- reportlab
- data_builders.py
- render_map.py, render_chart.py
- formatting.py
- transport_utils.py

**New:** Extract `_pdf_table_styling()` helper for reuse

### 4.4 Create `export_pptx.py` (350-420 lines)

**Source:** exporter.py lines 1872-2143

**Candidates:**

```python
generate_pptx_export(timeline, mission, parent_mission_id, route_manager, poi_manager) -> bytes
```

**Dependencies:**

- python-pptx
- data_builders.py
- render_map.py
- formatting.py
- transport_utils.py

**New:** Extract `_pptx_table_styling()` helper for reuse

---

## Phase 5: Package Assembly (Medium Risk)

**Goal:** Separate ZIP packaging from export generation

### 5.1 Create `archive_builder.py` (250-300 lines)

**Source:** package_exporter.py lines 853-1152

**Candidates:**

- `_add_mission_metadata_to_zip(zf, mission, manifest_files)`
- `_add_route_kmls_to_zip(zf, mission, route_manager, manifest_files)`
- `_add_pois_to_zip(zf, mission, poi_manager, manifest_files)`

  ```python
  _add_per_leg_exports_to_zip(zf, mission, route_manager, poi_manager, manifest_files)
  ```

  ```python
  _add_combined_mission_exports_to_zip(
      zf, mission, route_manager, poi_manager, manifest_files
  )
  ```

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

### 5.2 Refactor `package_exporter.py` (50-100 lines)

**Remaining:** Only orchestration and error handling

**Candidates:**

- `export_mission_package(mission_id, route_manager, poi_manager) -> IO[bytes]`
- Error handling, temp file management

**Dependencies:**

- archive_builder.py functions
- mission storage

---

## Phase 6: Combined Mission Exports (Lower Priority)

**Goal:** Separate multi-leg aggregation from single-leg export

### 6.1 Create `combined_exports.py` (500-600 lines)

**Source:** package_exporter.py lines 213-669

**Candidates:**

- `generate_mission_combined_csv(mission, output_path) -> bytes | None`

  ```python
  generate_mission_combined_xlsx(mission, route_manager, poi_manager, output_path) -> bytes | None
  ```

  ```python
  generate_mission_combined_pptx(mission, route_manager, poi_manager, output_path) -> bytes | None
  ```

  ```python
  generate_mission_combined_pdf(mission, route_manager, poi_manager, output_path) -> bytes | None
  ```

**Dependencies:**

- pandas, openpyxl, PyPDF2, python-pptx
- mission models, storage
- export format modules (CSV, XLSX, PDF, PPTX)

**Benefits:**

- Clear multi-leg aggregation logic
- Enables standalone combined export API
- Easier to test pagination logic
