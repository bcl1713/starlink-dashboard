# Proposal: Remove PDF and XLSX Exports

## Problem Statement

Mission and leg exports currently generate multiple file formats (CSV, XLSX, PDF, PPTX) that create operational and maintenance complexity:

1. **Format Redundancy:**
   - PPTX presentations already contain all critical mission data with visual context (maps, timelines, status)
   - PDF exports duplicate PPTX content without interactive features
   - XLSX exports duplicate CSV data with added complexity (embedded images, formatting)

2. **Maintenance Burden:**
   - Each export format requires separate generation logic, testing, and debugging
   - Recent PPTX enhancements (styling, footer updates) demonstrate ongoing maintenance needs
   - PDF generation uses ReportLab with complex table styling that requires careful updates
   - XLSX generation uses OpenPyXL with image embedding and cell formatting

3. **Performance Impact:**
   - Current exports generate 4 formats per leg (CSV, XLSX, PDF, PPTX) = 4× the work
   - Mission-level exports generate 4 combined formats
   - 2-leg mission = 12 total files (8 leg files + 4 mission files)
   - Reducing to CSV + PPTX = 6 total files (4 leg files + 2 mission files)

4. **User Confusion:**
   - Multiple overlapping formats make it unclear which to use
   - PPTX is preferred for briefings (visual, professional)
   - CSV is preferred for data analysis (machine-readable, simple)
   - PDF and XLSX add little unique value

## Goals

1. **Simplify Export Pipeline:** Reduce export formats from 4 to 2 (CSV + PPTX only)
2. **Reduce Maintenance:** Eliminate PDF and XLSX generation code and dependencies
3. **Improve Performance:** Cut export generation time by ~50% (2 formats instead of 4)
4. **Clarify Use Cases:** PPTX for presentations, CSV for data analysis

## Non-Goals

- Changing PPTX or CSV export content or structure
- Adding new export formats (JSON, KML, etc.)
- Modifying mission data models or API contracts
- Removing map or timeline chart generation (still used in PPTX)

## Impact Analysis

### Files Affected

**Export Generation (Removal):**
- `backend/starlink-location/app/mission/exporter/__main__.py`:
  - Remove `generate_pdf_export()` function (~280 lines)
  - Remove `generate_xlsx_export()` function (~125 lines)
  - Remove PDF/XLSX from `generate_timeline_export()` dispatcher (~20 lines)
  - Remove `TimelineExportFormat.PDF` and `TimelineExportFormat.XLSX` enum values

**Package Assembly (Updates):**
- `backend/starlink-location/app/mission/package/__main__.py`:
  - Remove `_process_leg_xlsx_export()` function (~70 lines)
  - Remove `generate_mission_combined_xlsx()` function (~200 lines)
  - Remove `generate_mission_combined_pdf()` function (~200 lines)
  - Update `_add_per_leg_exports_to_zip()` to skip XLSX/PDF generation (~30 lines removed)
  - Update `_add_combined_mission_exports_to_zip()` to skip XLSX/PDF (~40 lines removed)

**Dependencies (Removal from requirements.txt):**
- `reportlab>=4.0` (PDF generation)
- `openpyxl>=3.1` (XLSX generation) - **Wait, XLSX is still used for PPTX data prep**
- Actually, keep `openpyxl` since it's used in PPTX generation workflow

**Tests (Updates/Removal):**
- `backend/starlink-location/tests/unit/test_mission_exporter.py`:
  - Remove or update tests for PDF/XLSX export functions
- `backend/starlink-location/tests/unit/test_package_exporter.py`:
  - Remove or update tests for combined XLSX/PDF exports
- `backend/starlink-location/tests/integration/test_mission_scenarios.py`:
  - Update end-to-end export tests to verify only CSV/PPTX

### Dependencies Review

After reviewing the code, I found:
- **ReportLab** (PDF): Only used in `generate_pdf_export()` - can be fully removed
- **OpenPyXL** (XLSX): Used in both XLSX export AND in PPTX generation workflow - **must keep**
- **Pandas**: Used for CSV generation and data processing - keep
- **Matplotlib**: Used for map/chart generation (embedded in PPTX) - keep

### User Impact

**Breaking Change:** Users expecting PDF or XLSX exports will no longer receive them.

**Migration Path:**
- Users who need PDF: Use PPTX and export to PDF via PowerPoint/LibreOffice
- Users who need XLSX: Use CSV and import to Excel/LibreOffice Calc
- API returns 4xx error if PDF/XLSX format explicitly requested

**Documentation Updates:**
- Update API docs to reflect supported formats (CSV, PPTX only)
- Update mission planning guide to clarify export format use cases
- Add migration notes for users relying on PDF/XLSX

### Performance Impact

**Before (2-leg mission export):**
- Per-leg exports: 4 formats × 2 legs = 8 files
- Mission-level exports: 4 formats = 4 files
- Total: 12 files, ~30-45 seconds (with map caching)

**After (2-leg mission export):**
- Per-leg exports: 2 formats × 2 legs = 4 files
- Mission-level exports: 2 formats = 2 files
- Total: 6 files, ~15-25 seconds (50% reduction)

**Expected improvement:** 50% reduction in file count and generation time

### Risk Assessment

- **Medium risk:** Breaking change for API consumers expecting PDF/XLSX
- **Mitigation:** Return clear error message with recommended alternatives
- **Rollback:** Easy - keep old code in git history, can restore if needed
- **Compatibility:** PPTX and CSV formats unchanged, existing consumers unaffected

## Success Criteria

1. Export packages contain only CSV and PPTX files (no PDF, no XLSX)
2. Mission export time reduced by 40-50% for multi-leg missions
3. PDF/XLSX generation code and tests removed from codebase
4. ReportLab dependency removed from requirements.txt
5. All existing CSV and PPTX export tests pass without modification
6. API returns appropriate error for PDF/XLSX format requests

## Open Questions

1. Should we provide a conversion utility (CSV → XLSX) for users who need Excel format?
   - **Recommendation:** No - users can import CSV directly into Excel
2. Should we log deprecation warnings before removing formats?
   - **Recommendation:** No - this is a breaking change, make it clear in release notes
3. Should we version the export API to allow gradual migration?
   - **Recommendation:** No - clean break is simpler, document in migration guide

## Dependencies

- None - self-contained refactoring

## Timeline

- **Estimated effort:** 4-6 hours
- **Phase 1:** Remove PDF/XLSX generation functions (2 hours)
- **Phase 2:** Update package assembly logic (1 hour)
- **Phase 3:** Remove dependencies and update tests (1 hour)
- **Phase 4:** Update documentation (1 hour)
- **Phase 5:** Testing and validation (1 hour)
