# Tasks: Refactor Export Logic

## Overview

Refactor mission export logic to eliminate PPTX code duplication and optimize
map generation through caching.

## Phase 1: Extract PPTX Builder Module

### Task 1.1: Create pptx_builder.py skeleton

- [ ] Create `backend/starlink-location/app/mission/exporter/pptx_builder.py`
- [ ] Add module docstring and imports
- [ ] Define function signatures for:
  - `create_pptx_presentation()`
  - `add_route_map_slide()`
  - `add_timeline_table_slides()`
  - `_paginate_timeline_rows()`
  - `_add_timeline_table()`
- [ ] Update `app/mission/exporter/__init__.py` to export new functions

**Validation:** File exists, imports work, functions have type hints

**Dependencies:** None

**Parallel:** Can run in parallel with spec review

### Task 1.2: Extract pagination logic

- [ ] Copy pagination logic from `exporter/__main__.py` lines 1969-2034
- [ ] Extract into `_paginate_timeline_rows()` function
- [ ] Add comprehensive docstring with examples
- [ ] Write unit tests for edge cases:
  - Empty dataframe
  - Single page (≤7 rows)
  - Exactly 10 rows (should create 2 pages of 7 + 3)
  - 11 rows (should prevent orphan on last page)

**Validation:** All pagination tests pass

**Dependencies:** Task 1.1 complete

### Task 1.3: Extract timeline table creation logic

- [ ] Copy table creation logic from `exporter/__main__.py` lines 2065-2200
- [ ] Extract into `_add_timeline_table()` function
- [ ] Preserve status coloring logic (NOMINAL/SOF/DEGRADED/CRITICAL)
- [ ] Preserve transport state coloring (yellow/red for warnings)
- [ ] Add unit tests for status badge application

**Validation:** Table rendering logic isolated and tested

**Dependencies:** Task 1.2 complete

### Task 1.4: Implement add_timeline_table_slides()

- [ ] Implement function using extracted pagination and table helpers
- [ ] Add header/footer/logo to each slide
- [ ] Use `pptx_styling` helpers for consistent branding
- [ ] Add footer text with mission date
- [ ] Test with sample timeline data (1 slide, 3 slides, edge cases)

**Validation:** Function generates correct number of slides with proper
formatting

**Dependencies:** Tasks 1.2-1.3 complete

### Task 1.5: Implement add_route_map_slide()

- [ ] Copy route map slide logic from `exporter/__main__.py` lines 1897-1950
- [ ] Add map caching support (check cache before generating)
- [ ] Log cache hit/miss events
- [ ] Center map image on slide
- [ ] Add header/footer/logo
- [ ] Add footer text with mission ID and organization

**Validation:** Route map slide created correctly, cache parameter respected

**Dependencies:** Task 1.1 complete

**Parallel:** Can run in parallel with 1.2-1.4

### Task 1.6: Implement create_pptx_presentation()

- [ ] Initialize Presentation with correct dimensions (10×5.62 inches)
- [ ] Call `add_route_map_slide()` with all parameters
- [ ] Call `add_timeline_table_slides()` for timeline data
- [ ] Return complete Presentation object
- [ ] Add comprehensive docstring with parameter descriptions

**Validation:** Function generates complete presentation

**Dependencies:** Tasks 1.4-1.5 complete

## Phase 2: Update Export Functions

### Task 2.1: Update generate_pptx_export() in exporter

- [ ] Open `backend/starlink-location/app/mission/exporter/__main__.py`
- [ ] Replace lines 1822-2205 with call to `create_pptx_presentation()`
- [ ] Pass all required parameters (mission, timeline, route_manager, etc.)
- [ ] Keep title slide creation logic (mission-level metadata)
- [ ] Verify return value format (bytes from Presentation.save())

**Validation:** Single-leg PPTX export works, output identical to baseline

**Dependencies:** Phase 1 complete

### Task 2.2: Update generate_mission_combined_pptx() in package

- [ ] Open `backend/starlink-location/app/mission/package/__main__.py`
- [ ] Replace lines 398-689 (leg slide generation) with call to
  `create_pptx_presentation()`
- [ ] Keep mission title slide creation (lines 350-397)
- [ ] Loop through legs and call `create_pptx_presentation()` for each
- [ ] Append returned slides to main presentation

**Validation:** Multi-leg PPTX export works, output identical to baseline

**Dependencies:** Task 2.1 complete

### Task 2.3: Manual output comparison

- [ ] Export 2-leg mission before refactor, save as `baseline.pptx`
- [ ] Export same mission after refactor, save as `refactored.pptx`
- [ ] Open both in PowerPoint/LibreOffice
- [ ] Compare slide count, layout, formatting, content
- [ ] Verify no visual regressions
- [ ] Document any intentional differences (if any)

**Validation:** Output matches baseline

**Dependencies:** Task 2.2 complete

## Phase 3: Implement Map Caching

### Task 3.1: Add map_cache parameter to export functions

- [ ] Update `generate_timeline_export()` signature to accept
  `map_cache: dict[str, bytes] | None`
- [ ] Update `generate_xlsx_export()` to accept and pass through `map_cache`
- [ ] Update `generate_pdf_export()` to accept and pass through `map_cache`
- [ ] Update `generate_pptx_export()` to accept and pass through `map_cache`
- [ ] Update all callers to pass `None` initially (no behavior change)

**Validation:** All export functions accept cache parameter, tests pass

**Dependencies:** Phase 2 complete

### Task 3.2: Implement cache lookup in pptx_builder

- [ ] Update `add_route_map_slide()` to check `map_cache` before generation
- [ ] Add cache hit logging: `logger.info(f"Cache hit for route {route_id}")`
- [ ] Add cache miss logging: `logger.info(f"Cache miss for route {route_id},
  generating map")`
- [ ] Store generated map in cache: `map_cache[route_id] = map_bytes`
- [ ] Handle case where `map_cache` is None (no caching)

**Validation:** Cache lookups work, logging confirms hits/misses

**Dependencies:** Task 3.1 complete

### Task 3.3: Enable caching in mission package export

- [ ] Update `_add_per_leg_exports_to_zip()` to create `map_cache = {}`
- [ ] Pass `map_cache` to all `generate_timeline_export()` calls
- [ ] Update `_add_combined_mission_exports_to_zip()` to reuse same cache
- [ ] Clear cache after export complete: `map_cache.clear()`
- [ ] Add logging for cache statistics (hits, misses, total maps generated)

**Validation:** Multi-leg export logs show cache hits

**Dependencies:** Task 3.2 complete

### Task 3.4: Measure performance improvement

- [ ] Export 2-leg mission, measure total time and map generation count
- [ ] Export 5-leg mission, measure total time and map generation count
- [ ] Compare with baseline (from logs before refactor)
- [ ] Verify ≥50% reduction in map generation calls
- [ ] Document performance metrics in commit message

**Validation:** Performance targets met (see spec scenarios)

**Dependencies:** Task 3.3 complete

## Phase 4: Cleanup and Testing

### Task 4.1: Remove old duplicated code

- [ ] Verify all tests pass with refactored code
- [ ] Remove commented-out code blocks (if any)
- [ ] Run `ruff check` and `black` on modified files
- [ ] Run `mypy` on modified files
- [ ] Verify no unused imports remain

**Validation:** Linters pass, no dead code remains

**Dependencies:** Phase 3 complete

### Task 4.2: Update documentation

- [ ] Add docstrings to all new functions in `pptx_builder.py`
- [ ] Update `docs/development/export-architecture.md` (if exists)
- [ ] Add performance benchmarks to docs
- [ ] Document map caching behavior for future maintainers

**Validation:** All functions have comprehensive docstrings

**Dependencies:** Task 4.1 complete

### Task 4.3: Integration testing

- [ ] Test single-leg export (CSV, XLSX, PPTX, PDF)
- [ ] Test multi-leg mission export (2 legs, 5 legs)
- [ ] Test mission with no routes (edge case)
- [ ] Test mission with same route repeated across legs
- [ ] Verify no "Failed to generate PPTX" errors in logs
- [ ] Verify cache logging appears correctly

**Validation:** All export scenarios work correctly

**Dependencies:** Phase 3 complete

**Parallel:** Can run in parallel with Task 4.2

### Task 4.4: Regression testing

- [ ] Run full backend test suite: `pytest backend/starlink-location/tests`
- [ ] Verify no new test failures introduced
- [ ] Check Docker build completes: `docker compose build backend`
- [ ] Test export from running Docker container
- [ ] Verify no error logs during container startup

**Validation:** All tests pass, no regressions

**Dependencies:** Tasks 4.1-4.3 complete

## Phase 5: Deployment

### Task 5.1: Final validation

- [ ] Review all code changes
- [ ] Ensure git diff shows only intended changes
- [ ] Verify no debugging code or console logs remain
- [ ] Run pre-commit hooks: `pre-commit run --all-files`
- [ ] Verify all TODOs addressed or documented

**Validation:** Code ready for commit

**Dependencies:** Phase 4 complete

### Task 5.2: Create commit

- [ ] Stage all changes: `git add backend/starlink-location/app/mission`
- [ ] Create descriptive commit message:
  - Summary: "refactor: consolidate PPTX generation and optimize map caching"
  - Body: Include performance metrics and summary of changes
- [ ] Verify commit includes all modified files
- [ ] Push to feature branch (if using branches)

**Validation:** Clean commit created

**Dependencies:** Task 5.1 complete

## Summary

**Total estimated time:** 8-12 hours

**Parallelization opportunities:**

- Tasks 1.2-1.4 can run sequentially, but 1.5 can run in parallel
- Tasks 4.2 and 4.3 can run in parallel

**Critical path:**

1.1 → 1.2 → 1.3 → 1.4 → 1.6 → 2.1 → 2.2 → 3.1 → 3.2 → 3.3 → 4.1 → 4.4 → 5.1 →
5.2

**Rollback plan:**

If issues arise during deployment, revert the commit and restore previous export
functions from git history.
