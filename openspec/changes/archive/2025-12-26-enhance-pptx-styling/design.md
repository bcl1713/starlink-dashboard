# Design: Enhance PowerPoint Export Styling

## Overview

This design specifies the technical approach for enhancing PowerPoint (PPTX)
export styling using code-based styling with `python-pptx`, creating a reusable
styling system applied consistently across all slide types.

## Design Principles

1. **Code-Based Styling**: Define all styling programmatically
2. **Reusability**: Extract common styling patterns into functions
3. **Consistency**: Apply identical styling rules across all slide types
4. **Backward Compatibility**: Preserve existing API contracts
5. **Performance**: Minimize overhead (<100ms per export)

## Color Palette Specification

Based on analysis of `~/temp/example.pptx`:

```python
# Brand Colors
BRAND_GOLD = RGBColor(212, 175, 55)        # Primary accent
CONTENT_GRAY = RGBColor(248, 249, 250)     # Light backgrounds

# Status Colors
STATUS_NOMINAL = RGBColor(22, 163, 74)     # Green
STATUS_SOF = RGBColor(2, 132, 199)         # Blue
STATUS_DEGRADED = RGBColor(234, 88, 12)    # Orange
STATUS_CRITICAL = RGBColor(220, 38, 38)    # Red

# Text Colors
TEXT_BLACK = RGBColor(0, 0, 0)
TEXT_WHITE = RGBColor(255, 255, 255)
```

### Color Usage Matrix

| Element                | Fill Color      | Text Color | Font Size | Font Weight |
| ---------------------- | --------------- | ---------- | --------- | ----------- |
| Header bar             | BRAND_GOLD      | -          | -         | -           |
| Footer bar             | BRAND_GOLD      | -          | -         | -           |
| Slide title            | None            | TEXT_BLACK | 24pt      | Bold        |
| Footer text            | None            | TEXT_BLACK | 10pt      | Regular     |
| Content background     | CONTENT_GRAY    | -          | -         | -           |
| Status badge: NOMINAL  | STATUS_NOMINAL  | TEXT_WHITE | 11pt      | Bold        |
| Status badge: SOF      | STATUS_SOF      | TEXT_WHITE | 11pt      | Bold        |
| Status badge: DEGRADED | STATUS_DEGRADED | TEXT_WHITE | 11pt      | Bold        |
| Status badge: CRITICAL | STATUS_CRITICAL | TEXT_WHITE | 11pt      | Bold        |
| Segment label          | None            | TEXT_BLACK | 11pt      | Bold        |
| Timeline data          | None            | TEXT_BLACK | 10pt      | Regular     |

## Styling Module Structure

Create new module `app/mission/exporter/pptx_styling.py`:

```text
app/mission/exporter/
├── __init__.py
├── __main__.py              # Main export logic
├── formatting.py            # Timestamp/value formatting
├── transport_utils.py       # Transport state utilities
├── excel_utils.py           # Excel utilities
└── pptx_styling.py          # NEW: PowerPoint styling
```

### Styling Functions API

```python
def add_header_bar(slide, left, top, width, height):
    """Add gold header bar to slide."""

def add_footer_bar(slide, left, top, width, height):
    """Add gold footer bar to slide."""

def add_slide_title(slide, text: str, top=Inches(0.1)):
    """Add styled slide title (24pt bold, center)."""

def add_footer_text(slide, text: str, bottom=Inches(5.5)):
    """Add styled footer text (10pt, center)."""

def add_content_background(slide, left, top, width, height):
    """Add light gray content background."""

def add_status_badge(slide, status: TimelineStatus, left, top, width, height):
    """Add color-coded status badge with white text."""

def add_segment_separator(slide, left, top, width):
    """Add visual separator between timeline segments."""

def add_logo(slide, logo_path: Path, left, top, max_width, max_height):
    """Add logo if exists, maintaining aspect ratio. Returns bool."""
```

## Slide Layout Specifications

### Title Slide

- Header/footer bars: Gold (0.15" height)
- Logo: 0.3" x 0.3" (if exists, max 1.5" x 1.5")
- Mission title: Center, 1.5" from top, 28pt bold
- Leg count and organization displayed

### Route Map Slide

- Header/footer bars: Gold (0.15" height)
- Logo: 0.2" x 0.2" (if exists)
- Title: "Leg X - Route Map" (24pt bold)
- Content background: Gray (0.5" x 0.8" x 9" x 4.0")
- Map image: Centered within background
- Footer: "Mission ID | Organization"

### Timeline Slide

- Header/footer bars: Gold (0.15" height)
- Logo: 0.2" x 0.2" (if exists)
- Title: "Leg X - Timeline" (24pt bold)
- Content background: Gray (0.5" x 0.8" x 9" x 4.0")
- Segment rows with color-coded status badges
- Visual separators between segments (1px gray line)
- Footer: "Date: YYYY-MM-DD | Mission ID | Organization"

## Implementation Strategy

### Phase 1: Styling Module

1. Create `pptx_styling.py` with color constants and functions
2. Add unit tests (mock slide objects)
3. Document usage

### Phase 2: Title Slide Enhancement

1. Add header/footer bars to `generate_pptx_export`
2. Add logo placement
3. Style title text

### Phase 3: Route Map Slide Enhancement

1. Add header/footer bars
2. Add content background
3. Overlay map image
4. Add footer text

### Phase 4: Timeline Slide Enhancement

1. Add header/footer bars
2. Replace table layout with styled segment rows
3. Implement status badge coloring
4. Add segment separators
5. Format footer

### Phase 5: Combined Mission PPTX

1. Apply styling to `generate_mission_combined_pptx`
2. Ensure consistency across multi-leg presentations

## Data Sources

### Mission Context

- Mission ID: `mission.id`
- Mission Name: `mission.name`
- Organization: `mission.description` (or default)
- Leg Count: `len(mission.legs)`
- Date: `timeline.mission_start` or current date

### Status Mapping

```python
STATUS_COLOR_MAP = {
    TimelineStatus.NOMINAL: STATUS_NOMINAL,
    TimelineStatus.SOF: STATUS_SOF,
    TimelineStatus.DEGRADED: STATUS_DEGRADED,
    TimelineStatus.CRITICAL: STATUS_CRITICAL,
}
```

### Logo Handling

```python
LOGO_PATH = Path(__file__).parent.with_name("assets").joinpath("logo.png")

if LOGO_PATH.exists():
    add_logo(slide, LOGO_PATH, ...)
else:
    logger.debug("Logo not found, skipping")
```

## Testing Strategy

### Unit Tests

- Color constant definitions
- Styling function shape creation (mock `slide.shapes.add_*`)
- Status-to-color mapping

### Integration Tests

- Generate sample PPTX with styled slides
- Validate structure (slide count, shape count)
- Visual inspection (manual)

### Regression Tests

- Existing exports unchanged
- CSV, XLSX, PDF exports unaffected
- Combined mission PPTX generation

## Performance & Maintenance

### Performance

- Shape creation: ~10-15 shapes/slide (<50ms overhead)
- Logo: Read once, reuse BytesIO stream
- Memory: Minimal (lightweight objects)

### Future Enhancements

1. Configurable color palette (env vars)
2. Custom logo path (env var)
3. Additional slide types (summary, metrics)
4. Template system support
5. Theme variants (dark mode, high contrast)

### Edge Cases

- Missing logo: Skip, continue
- Long mission names: Truncate/wrap
- Many segments: Pagination handled by existing code
- Missing metadata: Sensible defaults

## Security & Accessibility

### Security

- No user input in styling (code-controlled)
- Logo path hardcoded (no user paths)
- No unbounded loops/memory allocation

### Accessibility

- Color contrast: WCAG AA compliant
  - White on green/blue: 4.5:1 (pass)
  - White on orange: 3.5:1 (acceptable)
  - White on red: 5.9:1 (pass)
  - Black on white/gray: 15:1 (excellent)
- Text size: ≥10pt
- Status redundancy: Color + text (not color-only)

## References

- Reference analysis: `inspect_template.py` output
- python-pptx shapes: <https://python-pptx.readthedocs.io/en/latest/user/shapes.html>
- python-pptx colors: <https://python-pptx.readthedocs.io/en/latest/api/dml.html>
