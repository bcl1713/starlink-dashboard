# Tasks: Fix PowerPoint Footer Styling and Date

## Implementation Checklist

### Phase 1: Fix Mission Date Bug

- [x] Import `mission_start_timestamp` from `app.mission.exporter.formatting`
      in `__main__.py`
- [x] Replace the broken date logic (lines 2029-2037) with correct
      implementation
- [x] Use `mission_start = mission_start_timestamp(timeline)` to get actual
      mission start
- [x] Format date as `mission_date = mission_start.strftime("%Y-%m-%d")`
- [ ] Test with mission that has timeline segments
- [ ] Test edge case: mission with no segments (should fall back to
      `timeline.created_at`)

### Phase 2: Update Footer Styling Function

- [x] Add `font_size` parameter to `add_footer_text()` function in
      `pptx_styling.py`
  - Default: `Pt(10)` for backward compatibility
  - Type: `int` (point size)
- [x] Add `color` parameter to `add_footer_text()` function
  - Default: `TEXT_BLACK` for backward compatibility
  - Type: `RGBColor`
- [x] Update function signature:
      `def add_footer_text(slide, text, bottom=5.5, font_size=10, color=None)`
- [x] Update font size application: `paragraph.font.size = Pt(font_size)`
- [x] Update color application:
      `paragraph.font.color.rgb = color if color else TEXT_BLACK`
- [x] Update docstring to document new parameters

### Phase 3: Reposition Footer Text in Route Map Slides

- [x] Locate route map slide footer calls (around line 1940 in `__main__.py`)
- [x] Change `add_footer_text(slide, footer_text, bottom=5.3)` to
      `add_footer_text(slide, footer_text, bottom=5.47, font_size=7, color=TEXT_WHITE)`
- [ ] Verify footer text appears within the gold bar (y=5.47 to y=5.62)
- [ ] Test visual appearance in generated PPTX

### Phase 4: Reposition Footer Text in Timeline Slides

- [x] Locate timeline slide footer calls (around line 2060 in `__main__.py`)
- [x] Change `add_footer_text(slide, footer_text, bottom=5.3)` to
      `add_footer_text(slide, footer_text, bottom=5.47, font_size=7, color=TEXT_WHITE)`
- [ ] Verify footer text appears within the gold bar
- [ ] Test visual appearance in generated PPTX

### Phase 5: Testing & Validation

- [ ] Generate test PPTX with sample mission data
- [ ] Visual inspection: Verify footer shows mission leg date (not current
      date)
- [ ] Visual inspection: Verify footer text is inside gold bar at bottom
- [ ] Visual inspection: Verify 7pt white text is readable on gold background
- [ ] Visual inspection: Verify footer text is properly centered
- [ ] Test with mission containing multiple legs
- [ ] Test with mission containing timeline segments
- [ ] Test edge case: mission with no segments
- [ ] Verify no changes to other slide elements (headers, content, tables)
- [x] Verify CSV export unchanged (no code changes to CSV export)
- [x] Verify XLSX export unchanged (no code changes to XLSX export)
- [x] Verify PDF export unchanged (no code changes to PDF export)
- [x] Run syntax validation: `python -m py_compile` on modified files
- [x] Run code formatting: `black` on modified files
- [x] Run linting: `ruff check` on modified files

### Phase 6: Documentation & Cleanup

- [x] Add code comment explaining mission date extraction at implementation
      site
- [x] Update `add_footer_text()` docstring with parameter descriptions
- [x] Verify all changes pass pre-commit hooks
- [x] Update this tasks.md checklist as work progresses

## Validation Steps

After implementation:

1. Export a test mission with at least 2 legs
2. Open generated PPTX in PowerPoint/LibreOffice
3. Verify footer elements:
   - Date matches mission leg start date (from first timeline segment)
   - Footer text appears inside the gold bar
   - Text is 7pt white and readable
   - Text is properly centered
4. Confirm correct date for each leg (different legs may have different dates)
5. Run linters: `black`, `ruff check`, `mypy`

## Acceptance Criteria

- [ ] Footer displays mission leg start date (not current date/time)
- [ ] Footer text positioned within gold bar (y=5.47, inside y=5.47-5.62
      range)
- [ ] Footer text uses 7pt white font
- [ ] Footer text is properly centered and readable
- [ ] All route map slides have updated footer styling
- [ ] All timeline slides have updated footer styling
- [ ] No regressions in other export formats (CSV, XLSX, PDF)
- [ ] No regressions in other slide elements
- [ ] Code passes all formatting checks (Black, Ruff)
- [ ] Function remains backward compatible (default parameters work)

## Files Modified

- `backend/starlink-location/app/mission/exporter/__main__.py`
  - Fix mission date extraction (lines 2036-2038)
  - Update route map footer calls (lines 1943-1950) - bottom=5.49
  - Update timeline footer calls (lines 2059-2063) - bottom=5.49
- `backend/starlink-location/app/mission/exporter/pptx_styling.py`
  - Add `font_size` and `color` parameters to `add_footer_text()` (lines
    119-144)
- `backend/starlink-location/app/mission/package/__main__.py`
  - Import TEXT_WHITE and mission_start_timestamp (lines 317, 329)
  - Fix mission date extraction (lines 471-473)
  - Update route map footer calls (lines 465-472) - bottom=5.49
  - Update timeline footer calls (lines 545-551) - bottom=5.49
