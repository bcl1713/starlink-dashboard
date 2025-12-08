# Implementation Strategy

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
| excel_utils.py            | 130        | pkg_exporter.py 33-122       |
| data_builders.py          | 200        | exporter.py 1287-1414        |
| segment_processing.py     | 220        | exporter.py 206-385          |
| map_utils.py              | 300        | exporter.py helpers          |
| render_map.py             | 450        | exporter.py 428-1119         |
| render_chart.py           | 220        | exporter.py 1122-1284        |
| export_csv.py             | 60         | exporter.py 1443-1450        |
| export_xlsx.py            | 180        | exporter.py 1492-1600        |
| export_pdf.py             | 400        | exporter.py 1603-1869        |
| export_pptx.py            | 400        | exporter.py 1872-2143        |
| archive_builder.py        | 300        | pkg_exporter.py 853-1152     |
| combined_exports.py       | 550        | pkg_exporter.py 213-669      |
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
