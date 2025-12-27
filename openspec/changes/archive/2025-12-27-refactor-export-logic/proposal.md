# Proposal: Refactor Export Logic

## Problem Statement

Mission export logic contains significant duplication that causes maintainability
issues and performance inefficiencies:

1. **PPTX generation code duplicated across two modules:**
   - `app/mission/package/__main__.py::generate_mission_combined_pptx()` (lines
     289-706)
   - `app/mission/exporter/__main__.py::generate_pptx_export()` (lines 1822-2205)
   - Both contain ~400 lines of near-identical slide generation logic

2. **Route map generated multiple times per export:**
   - Single 2-leg mission export triggers 7 map generations
   - Each leg export: 2× map generation (XLSX + PDF)
   - Mission-level export: 3× map generation (XLSX + PPTX + PDF)
   - Evidence from logs: identical "Map generation - Route has 42 valid points"
     messages appear 7 times

3. **Code maintenance burden:**
   - Recent PPTX styling updates (footer text, date formatting) required changes
     in both files
   - Inconsistencies easily introduced when updating only one location
   - 417 lines of duplicated PPTX generation logic increases codebase size
     unnecessarily

## Goals

1. **Eliminate PPTX generation duplication:** Extract common slide generation
   logic into reusable functions
2. **Optimize map generation:** Cache generated maps within a single export
   operation
3. **Improve maintainability:** Single source of truth for PPTX styling and
   export logic

## Non-Goals

- Changing export file formats or output structure
- Modifying mission data models or API contracts
- Optimizing map generation algorithm itself (just caching)
- Refactoring CSV, XLSX, or PDF export logic (those are already modular)

## Impact Analysis

### Files Affected

- `backend/starlink-location/app/mission/package/__main__.py` (1203 lines, will
  shrink)
- `backend/starlink-location/app/mission/exporter/__main__.py` (2283 lines, will
  shrink)
- New file: `backend/starlink-location/app/mission/exporter/pptx_builder.py`
  (common logic)

### Performance Impact

**Before (2-leg mission export):**

- 7 route map generations (~3-5 seconds each) = 21-35 seconds
- 2 PPTX generations with duplicated logic

**After (2-leg mission export):**

- 2 route map generations (1 per leg) with caching = 6-10 seconds
- 2 PPTX generations using shared logic (same performance, less code)

**Expected improvement:** 15-25 second reduction per mission export with 2+ legs

### Risk Assessment

- **Low risk:** Changes are internal refactoring with no external API changes
- **Testability:** Existing PPTX output can be compared byte-for-byte or
  visually
- **Rollback:** Easy - keep old functions until new ones validated

## Success Criteria

1. PPTX export output identical to current behavior (verified by manual
   inspection)
2. Mission export time reduced by 50%+ for multi-leg missions
3. PPTX generation logic exists in single location only
4. All existing export tests pass without modification
5. No errors in export logs (specifically "Failed to generate PPTX" should not
   appear)

## Open Questions

1. Should map caching be in-memory (per export operation) or persistent (across
   operations)?
   - **Recommendation:** In-memory only, scoped to single export operation
2. Should we cache other artifacts (timeline charts, etc.)?
   - **Recommendation:** Not yet - map generation is the main bottleneck
3. Should we extract common logic for XLSX/PDF exports too?
   - **Recommendation:** No - those are already reasonably modular

## Dependencies

- None - self-contained refactoring

## Timeline

- **Estimated effort:** 1-2 days
- **Phase 1:** Extract PPTX slide generation to reusable functions (4 hours)
- **Phase 2:** Implement map caching for export operations (2 hours)
- **Phase 3:** Testing and validation (2 hours)
