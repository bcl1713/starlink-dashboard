# Proposal: Enhance PowerPoint Export Styling

## Change ID

`enhance-pptx-styling`

## Type

Enhancement

## Status

Proposed

## Summary

Enhance PowerPoint (PPTX) mission export slides with professional styling based on
provided reference presentation, including branded headers/footers, consistent color
scheme, improved layout, and polished visual presentation suitable for executive
briefings and operational planning.

## Motivation

### Current State

The current PowerPoint export functionality (`generate_pptx_export` in
`app/mission/exporter/__main__.py`) creates basic slides with:

- Generic default template (python-pptx library defaults)
- Plain black text on white backgrounds
- No headers or footers
- Minimal visual hierarchy
- No color-coded status indicators
- Basic table formatting without visual polish

While functional, the output lacks the professional appearance expected for
military/government briefings and operational planning presentations.

### Problem

Stakeholders require mission briefing slides that:

1. Look professional and polished for executive audiences
2. Use consistent branding and color schemes
3. Provide visual hierarchy through styled headers and status colors
4. Include contextual information (mission name, date, organization) in footers
5. Match the visual standards of existing operational presentations

The current implementation does not meet these requirements, forcing users to
manually reformat generated slides or avoid using the export feature entirely.

### Desired Outcome

PowerPoint exports should match the styling of the reference presentation
(`~/temp/example.pptx`), featuring:

- **Gold accent color** (RGB 212, 175, 55) for headers and branding bars
- **Light gray backgrounds** (RGB 248, 249, 250) for content areas
- **Status color coding**:
  - Green (RGB 22, 163, 74) for "NOMINAL"
  - Blue (RGB 2, 132, 199) for "SOF" (Safety of Flight)
  - Orange (RGB 234, 88, 12) for "DEGRADED"
  - Red (RGB 220, 38, 38) for "CRITICAL"
- **Professional headers** with mission name and leg identifier
- **Informative footers** with mission ID, organization name, and date
- **Branded logo placement** (when logo is available)
- **Visual separators** between timeline segments
- **Improved typography** with proper font sizing and alignment

## Scope

### In Scope

1. **Styling System Implementation**

   - Define color constants for brand palette (gold, status colors, grays)
   - Create reusable styling functions for headers, footers, status badges
   - Implement visual separator/divider elements

2. **Title Slide Enhancement**

   - Add gold header and footer bars
   - Place logo (if available) with proper sizing
   - Display mission name, ID, and organization
   - Add leg count summary

3. **Route Map Slide Enhancement**

   - Add gold header and footer bars with mission context
   - Add slide title ("Leg X - Route Map")
   - Style footer with mission ID and organization
   - Maintain map aspect ratio (specify only width, not height, when adding
     images to prevent stretching)

4. **Timeline Slide Enhancement**

   - Add gold header and footer bars
   - Implement color-coded status badges (NOMINAL/SOF/DEGRADED/CRITICAL)
   - Add visual separators between segments
   - Style footer with date, mission ID, and organization
   - Improve segment layout with proper spacing and alignment
   - Adjust table pagination from 10 to 9 rows per slide to accommodate new
     header/footer bars and content background (reduced vertical space)

5. **Combined Mission PPTX**
   - Apply styling to `generate_mission_combined_pptx` function
   - Ensure consistent styling across all slides in multi-leg presentations

### Out of Scope

- Changing slide dimensions (keep current 10" x 5.62" widescreen format)
- Adding new slide types or content beyond current functionality
- Creating fully templated slides with locked placeholders
- Implementing slide animations or transitions
- Supporting user-customizable color schemes (fixed palette for v1)
- PDF export styling (remains unchanged)
- Excel export styling (remains unchanged)
- CSV export (remains unchanged)

### Dependencies

- Existing `python-pptx` library (already in requirements.txt)
- Logo asset at `app/mission/assets/logo.png` (referenced in code, may or may
  not exist)
- Current timeline export infrastructure remains unchanged
- Current mission package export infrastructure remains unchanged

### Breaking Changes

None. This is a visual enhancement only. The API contract, file formats, and
export behavior remain identical.

## Impact Assessment

### Benefits

- **Professional Appearance**: Slides suitable for executive and operational
  briefings
- **Visual Clarity**: Color-coded status makes timeline interpretation faster
- **Brand Consistency**: Matches organizational presentation standards
- **Reduced Manual Work**: Eliminates need to manually reformat exported slides
- **Enhanced Communication**: Better visual hierarchy improves information
  comprehension

### Risks

- **Slight Performance Impact**: Additional shape creation and styling adds
  minimal overhead
- **Maintenance Burden**: Styling code adds complexity to export module
  - _Mitigation_: Extract styling to separate functions for reusability and
    testability

### Compatibility

- **Backward Compatible**: Existing exports continue to work
- **Forward Compatible**: Color palette can be extracted to configuration in
  future versions

## Alternatives Considered

### 1. Using PPTX Template File

**Approach**: Load a pre-designed .pptx template and populate placeholders

**Pros**:

- Non-developers can modify template
- Styling fully decoupled from code

**Cons**:

- Requires creating and maintaining template file
- python-pptx template support is limited for complex layouts
- Harder to dynamically create variable-length timeline slides
- Must bundle template file with application

**Decision**: Rejected. Code-based styling provides more flexibility for
dynamic content (variable segment counts) and eliminates external dependencies.

### 2. Extracting Styling to Existing Template

**Approach**: Analyze provided example.pptx and create a template from it

**Pros**:

- Leverages existing design work
- Could preserve exact layout

**Cons**:

- Example uses highly manual layout (individual text boxes, not tables)
- Not scalable to variable segment counts
- Difficult to maintain

**Decision**: Rejected. Reference presentation used for styling inspiration, but
implementation uses programmatic layout for flexibility.

### 3. Minimal Styling (Status Quo)

**Approach**: Keep current basic styling, rely on manual post-processing

**Pros**:

- Zero development effort
- No maintenance burden

**Cons**:

- Poor user experience
- Wasted time on manual reformatting
- Inconsistent presentation quality

**Decision**: Rejected. Professional styling is a core requirement for
stakeholder acceptance.

## Success Criteria

1. **Visual Parity**: Generated slides match reference presentation styling:
   - Gold header/footer bars (RGB 212, 175, 55)
   - Light gray content backgrounds (RGB 248, 249, 250)
   - Color-coded status badges matching reference
2. **Functional Completeness**: All slide types (title, map, timeline) use new
   styling
3. **No Regressions**: Existing functionality (exports, imports, timeline
   generation) remains unchanged
4. **Code Quality**: Styling code is modular, reusable, and documented
5. **User Validation**: Stakeholder approval of visual output
6. **Map Aspect Ratio**: Route map images maintain original aspect ratio (no
   stretching or distortion)
7. **Table Pagination**: Timeline tables paginate at 9 rows per slide (adjusted
   from 10 for new styling) and fit within slide boundaries without overflow

## Related Changes

None (first OpenSpec change proposal)

## References

- Reference presentation: `~/temp/example.pptx`
- Current exporter implementation:
  `backend/starlink-location/app/mission/exporter/__main__.py:1814-2160`
- Current package exporter:
  `backend/starlink-location/app/mission/package/__main__.py:289-571`
- python-pptx documentation: <https://python-pptx.readthedocs.io/>
