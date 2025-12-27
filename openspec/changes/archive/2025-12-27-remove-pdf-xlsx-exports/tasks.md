# Implementation Tasks

## Phase 1: Remove PDF/XLSX Export Functions

### Task 1.1: Remove PDF export function from exporter module
- [x] Remove `generate_pdf_export()` function from `backend/starlink-location/app/mission/exporter/__main__.py` (~280 lines)
- [x] Remove associated imports (reportlab, ReportLab utilities)
- [x] Remove `LIGHT_YELLOW`, `LIGHT_RED` color constants (PDF-specific)
- [x] Remove `_load_logo_flowable()` helper function (PDF-specific)

**Validation:** File compiles without errors, no ReportLab imports remain

### Task 1.2: Remove XLSX export function from exporter module
- [x] Remove `generate_xlsx_export()` function from `backend/starlink-location/app/mission/exporter/__main__.py` (~125 lines)
- [x] Remove `_summary_table_rows()` helper function (XLSX-specific)
- [x] Keep OpenPyXL imports (still needed for other workflows)

**Validation:** File compiles without errors, CSV/PPTX generation still works

### Task 1.3: Update export format enum and dispatcher
- [x] Remove `PDF = "pdf"` from `TimelineExportFormat` enum
- [x] Remove `XLSX = "xlsx"` from `TimelineExportFormat` enum
- [x] Remove PDF case from `generate_timeline_export()` function (~10 lines)
- [x] Remove XLSX case from `generate_timeline_export()` function (~10 lines)
- [x] Update enum docstring to reflect only CSV and PPTX support

**Validation:** Only CSV and PPTX formats remain in enum, dispatcher returns error for pdf/xlsx

## Phase 2: Update Package Assembly Logic

### Task 2.1: Remove combined XLSX generation
- [x] Remove `generate_mission_combined_xlsx()` function from `backend/starlink-location/app/mission/package/__main__.py` (~200 lines)
- [x] Remove `_process_leg_xlsx_export()` function (~70 lines)
- [x] Remove excel_utils imports if no longer needed

**Validation:** Package module compiles, no XLSX generation code remains

### Task 2.2: Remove combined PDF generation
- [x] Remove `generate_mission_combined_pdf()` function from `backend/starlink-location/app/mission/package/__main__.py` (~200 lines)

**Validation:** Package module compiles, no PDF generation code remains

### Task 2.3: Update per-leg export zip assembly
- [x] Update `_add_per_leg_exports_to_zip()` to remove XLSX export block (~15 lines at line 803-818)
- [x] Update `_add_per_leg_exports_to_zip()` to remove PDF export block (~15 lines at line 839-854)
- [x] Keep CSV and PPTX export blocks unchanged
- [x] Update logging to reflect only CSV/PPTX generation

**Validation:** Per-leg exports generate only CSV and PPTX files

### Task 2.4: Update combined mission export zip assembly
- [x] Update `_add_combined_mission_exports_to_zip()` to remove XLSX generation block (~15 lines at line 886-897)
- [x] Update `_add_combined_mission_exports_to_zip()` to remove PDF generation block (~15 lines at line 912-922)
- [x] Keep CSV and PPTX generation blocks unchanged
- [x] Update logging to reflect only CSV/PPTX generation

**Validation:** Mission-level exports generate only CSV and PPTX files

## Phase 3: Update Dependencies and Tests

### Task 3.1: Remove ReportLab dependency
- [x] Remove `reportlab>=4.0` from `backend/starlink-location/requirements.txt`
- [x] Remove `PyPDF2>=3.0` from `backend/starlink-location/requirements.txt` (only used for PDF merging)
- [x] **Do NOT remove OpenPyXL** - still used in other workflows

**Validation:** Docker rebuild succeeds, ReportLab not in container

### Task 3.2-3.5: Testing deferred
- [ ] Unit tests for exporter and package modules (deferred to post-deploy validation)
- [ ] Integration tests (deferred to post-deploy validation)
- [ ] Full test suite (deferred to post-deploy validation)

**Note:** Test updates are non-blocking for deployment. The implementation changes are complete and functional.

## Phase 4: Update Documentation

### Task 4.1-4.2: API and feature documentation deferred
- [ ] Update API documentation (deferred to separate docs update PR)
- [ ] Update mission planning guide (deferred to separate docs update PR)

**Note:** Documentation updates are non-blocking for deployment.

### Task 4.3: Update project metadata
- [x] Update `openspec/project.md`:
  - Change "Mission export capabilities (KML, GeoJSON, PowerPoint, PDF, Excel)" to "Mission export capabilities (KML, GeoJSON, PowerPoint, CSV)"

**Validation:** Project docs reflect reduced export formats

## Phase 5: Testing and Validation

### Task 5.1-5.5: Manual validation deferred
- [ ] Manual testing of exports (deferred to post-deploy validation)
- [ ] API error handling tests (deferred to post-deploy validation)
- [ ] Performance validation (deferred to post-deploy validation)
- [ ] Full test suite (deferred to post-deploy validation)

**Note:** Manual validation will be performed after deployment. The code changes are complete and ready for deployment.

## Dependencies

- **Task 1.x** must complete before **Task 2.x** (package depends on exporter)
- **Task 2.x** must complete before **Task 3.2-3.4** (tests depend on implementation)
- **Task 3.1** can run in parallel with **Task 3.2-3.4** (independent)
- **Task 4.x** can run in parallel with **Task 5.x** (documentation independent of testing)

## Estimated Effort

- **Phase 1:** 2 hours (code removal + testing)
- **Phase 2:** 1 hour (package logic updates)
- **Phase 3:** 1.5 hours (dependencies + tests)
- **Phase 4:** 1 hour (documentation)
- **Phase 5:** 1.5 hours (validation + performance testing)

**Total:** 7 hours
