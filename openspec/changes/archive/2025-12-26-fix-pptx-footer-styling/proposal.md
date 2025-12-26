# Proposal: Fix PowerPoint Footer Styling and Date

## Change ID

`fix-pptx-footer-styling`

## Type

Bug Fix + Enhancement

## Status

Proposed

## Summary

Fix PowerPoint export footer to display mission leg start date (instead of
current date) and improve footer styling by positioning text within the gold
bar with smaller font size and white color for better readability and
professional appearance.

## Motivation

### Current State

The PowerPoint export footer implementation has two issues:

1. **Incorrect Date (Bug)**: The code attempts to use `timeline.mission_start`
   which doesn't exist on the `MissionLegTimeline` model, causing it to always
   fall back to `datetime.now(timezone.utc)` and display the current date
   instead of the actual mission leg date.

2. **Poor Footer Styling**: The footer text is positioned below the gold bar
   (at y=5.3 inches) with 10pt black text, making it disconnected from the
   visual branding and harder to read.

Located in:

- `backend/starlink-location/app/mission/exporter/__main__.py:2029-2060`
  (date bug and footer positioning)
- `backend/starlink-location/app/mission/exporter/pptx_styling.py:119-137`
  (footer text styling function)

### Problem

**Date Bug:**
The footer displays the wrong date (export generation time) instead of the
mission leg's actual start date. This is misleading for operational planning
and briefings where the mission date is critical information.

The code at lines 2029-2037 in `__main__.py`:

```python
try:
    mission_date = (
        timeline.mission_start.strftime("%Y-%m-%d")
        if timeline.mission_start
        else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    )
except Exception:
    mission_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

However, `MissionLegTimeline` model (lines 488-524 in `models.py`) has no
`mission_start` field, so this always falls back to the current date.

**Styling Issues:**

- Footer text positioned outside/below the gold bar looks disconnected from
  the visual branding
- 10pt black text is too large and doesn't contrast well against the slide
  background
- Footer lacks the professional, integrated appearance expected for executive
  briefings

### Desired Outcome

**Date Fix:**

- Use the correct mission leg start date by importing and calling
  `mission_start_timestamp(timeline)` from the `formatting` module
- This function correctly extracts the earliest segment's `start_time` as
  the mission date

**Footer Styling:**

- Position footer text centered within the gold bar (at y=5.47 inches)
- Use 7pt white text for subtle, professional appearance with good contrast
  against gold background
- Maintain the same footer content format:
  "Date: YYYY-MM-DD | Mission ID | Organization"

## Scope

### In Scope

1. **Fix Mission Date Bug**
   - Import `mission_start_timestamp` from `app.mission.exporter.formatting`
   - Replace broken `timeline.mission_start` logic with correct function call
   - Use actual mission leg start date in footer

2. **Update Footer Text Styling Function**
   - Add optional `font_size` parameter to `add_footer_text()` in `pptx_styling.py`
   - Add optional `color` parameter to `add_footer_text()`
   - Default to current behavior (10pt, black) for backward compatibility

3. **Reposition Footer Text**
   - Move footer text from y=5.3 to y=5.47 (inside the gold bar)
   - Apply 7pt white text styling
   - Ensure text is properly centered within the gold bar

4. **Apply Changes to All Slide Types**
   - Route map slides (Slide 2+)
   - Timeline slides (Slide 3+)
   - Consistent styling across all slides with footers

### Out of Scope

- Changing footer content format (keep "Date: YYYY-MM-DD | Mission ID | Organization")
- Modifying title slide (it has no footer text)
- Changing gold bar dimensions or position
- Modifying other export formats (CSV, XLSX, PDF)
- Adding new footer fields or information

## Dependencies

### Internal

- `app.mission.exporter.formatting.mission_start_timestamp()` - Already
  exists, provides correct mission start date extraction
- `app.mission.models.MissionLegTimeline` - Existing model with timeline
  segments
- `pptx_styling.py` color constants (`TEXT_WHITE`, `BRAND_GOLD`) - Already
  defined

### External

- python-pptx library (already in use)

## Alternatives Considered

### Alternative 1: Add `mission_start` field to `MissionLegTimeline` model

**Rejected:** This would require:

- Modifying the data model
- Updating all places where timelines are created
- Database/file migration considerations
- More extensive changes for a simple bug fix

The existing `mission_start_timestamp()` function already provides the needed
functionality by extracting from segments.

### Alternative 2: Keep footer text outside gold bar

**Rejected:** User specifically requested footer text be positioned within
the gold bar for better visual integration and professional appearance.

### Alternative 3: Use larger font size (e.g., 9pt or 8pt)

**Rejected:** User requested 7pt (very small) for minimal visual footprint
while maintaining readability.

## Risk Assessment

### Low Risk

- Changes are isolated to footer rendering
- No data model modifications
- No API changes
- Backward compatible (optional parameters with defaults)
- Other export formats unaffected

### Testing Required

- Visual inspection of generated PPTX files
- Verify correct mission date appears in footer
- Verify footer text is visible and readable within gold bar
- Confirm no regression in other slide elements
- Test with and without timeline segments (edge cases)

## Success Criteria

- [ ] Footer displays actual mission leg start date (not current date)
- [ ] Footer text is positioned within the gold bar (y=5.47)
- [ ] Footer text uses 7pt white font
- [ ] Footer text is properly centered and readable
- [ ] All timeline and route map slides show consistent footer styling
- [ ] No regressions in other export formats or slide elements
- [ ] Code passes all linting and formatting checks
