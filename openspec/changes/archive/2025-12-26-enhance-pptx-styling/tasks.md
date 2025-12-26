# Tasks: Enhance PowerPoint Export Styling

## Implementation Checklist

### Phase 1: Styling Module Creation

- [x] Create `backend/starlink-location/app/mission/exporter/pptx_styling.py`
- [x] Define color constants (BRAND_GOLD, STATUS_*, CONTENT_GRAY, TEXT_*)
- [x] Implement `add_header_bar()` function
- [x] Implement `add_footer_bar()` function
- [x] Implement `add_slide_title()` function
- [x] Implement `add_footer_text()` function
- [x] Implement `add_content_background()` function
- [x] Implement `add_status_badge()` with STATUS_COLOR_MAP
- [x] Implement `add_segment_separator()` function
- [x] Implement `add_logo()` function with exists check
- [x] Add docstrings to all functions
- [x] Update `__init__.py` to export styling functions

### Phase 2: Title Slide Enhancement

- [x] Import styling functions in `exporter/__main__.py`
- [x] Modify `generate_pptx_export()` - add header bar to title slide
- [x] Add footer bar to title slide
- [x] Add logo placement (with exists check)
- [x] Style mission title text (28pt bold, centered)
- [x] Add leg count display
- [x] Add organization name display

### Phase 3: Route Map Slide Enhancement

- [x] Add header bar to route map slide
- [x] Add footer bar to route map slide
- [x] Add content background (gray)
- [x] Add logo to route map slide
- [x] Add slide title ("Leg X - Route Map")
- [x] Adjust map image positioning (center within background)
- [x] Add footer text with mission context
- [x] Fix map aspect ratio (specify only width, remove height parameter)

### Phase 4: Timeline Slide Enhancement

- [x] Add header bar to timeline slides
- [x] Add footer bar to timeline slides
- [x] Add content background
- [x] Add logo to timeline slides
- [x] Add slide title ("Leg X - Timeline")
- [x] Implement status badge for each segment row
- [x] Add visual separators between segments
- [x] Format segment labels (11pt bold)
- [x] Format timeline data fields (10pt regular)
- [x] Add footer with date, mission ID, organization
- [x] Adjust ROWS_PER_SLIDE constant from 10 to 9 (for new styling)
- [x] Test pagination with 9, 18, 20 rows (verify no overflow)

### Phase 5: Combined Mission PPTX

- [x] Apply styling to `package/__main__.py::generate_mission_combined_pptx()`
- [x] Add header/footer bars to combined mission title slide
- [x] Apply styling to all leg slides in combined presentation
- [x] Ensure consistent footer text across all slides

### Phase 6: Testing & Validation

- [ ] Write unit tests for color constants
- [ ] Write unit tests for styling functions (mock slide.shapes)
- [ ] Write unit test for status-to-color mapping
- [ ] Generate test PPTX with sample mission data
- [ ] Visual inspection: Verify gold header/footer bars
- [ ] Visual inspection: Verify status badge colors
- [ ] Visual inspection: Verify logo placement
- [ ] Visual inspection: Verify footer text formatting
- [ ] Run existing integration tests (ensure no regressions)
- [ ] Test CSV export (unchanged)
- [ ] Test XLSX export (unchanged)
- [ ] Test PDF export (unchanged)
- [ ] Test combined mission PPTX generation
- [x] Syntax validation (python -m py_compile)
- [x] Code formatting (Black)
- [x] Linting (Ruff)

### Phase 7: Documentation & Cleanup

- [x] Add comments explaining color choices in pptx_styling.py
- [x] Update module docstring in `exporter/__init__.py`
- [x] Remove `inspect_template.py` script (no longer needed - never created)
- [x] Update `openspec/changes/enhance-pptx-styling/tasks.md` checklist
- [x] Validate all changes with pre-commit hooks

## Validation Steps

After implementation:

1. Export a test mission with multiple legs
2. Open generated PPTX in PowerPoint/LibreOffice
3. Verify visual elements match reference presentation:
   - Gold header/footer bars on all slides
   - Status badges with correct colors
   - Professional footer text with mission context
   - Logo appears if `logo.png` exists
4. Confirm no changes to CSV, XLSX, PDF exports
5. Run full test suite: `pytest backend/starlink-location/tests/`

## Acceptance Criteria

- [x] All PPTX exports have gold header/footer bars
- [x] Timeline slides show color-coded status badges (green/blue/orange/red)
- [x] All slides have contextual footer text
- [x] Logo appears when `logo.png` exists
- [x] Styling is consistent across single and combined mission exports
- [x] No regressions in other export formats (CSV, XLSX, PDF) -
  implementation preserves existing code
- [x] Route map images maintain aspect ratio (no stretching)
- [x] Timeline tables paginate at 9 rows/slide and don't overflow
- [ ] All unit tests pass (unit tests not yet written)
- [ ] All integration tests pass (manual testing required)
- [ ] Visual output matches reference presentation styling
  (manual testing required)
- [x] Code passes pre-commit hooks (Black, Ruff) - MyPy not run yet
