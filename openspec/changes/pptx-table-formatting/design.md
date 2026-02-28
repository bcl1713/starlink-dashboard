## Context

The PPTX timeline table in `pptx_builder.py` uses a `columns_to_show` list for headers and `Pt(10)` for header / `Pt(9)` for data font sizes. The "Segment #" header text wraps in narrow columns and is redundant since the data rows already show the segment number.

## Goals / Non-Goals

**Goals:**
- Blank out the "Segment #" column header to eliminate unnecessary wrapping
- Set all table text (header and data) to 8pt to reduce column overflow

**Non-Goals:**
- Changing column widths or weight distribution
- Modifying column content or adding/removing columns
- Changing any other slide styling (colors, status badges, etc.)

## Decisions

### 1. Blank header cell vs. removing the column

**Decision:** Keep the column but display an empty string for its header.

**Rationale:** The segment number data is still useful in rows — only the header label is unnecessary. Removing the column entirely would lose the segment numbering. Using an empty string for the header eliminates wrapping with zero layout impact.

### 2. Uniform 8pt font size

**Decision:** Set both header and data row font sizes to `Pt(8)`.

**Rationale:** The current 10pt header / 9pt data sizes cause overflow in time and reasons columns. A uniform 8pt keeps text readable while giving columns more breathing room. This is simpler than per-column font sizing and consistent across the table.

## Risks / Trade-offs

- [Slightly smaller text] → 8pt is still standard for dense data tables in presentations; readability is acceptable at screen and projected sizes.
- [Header row less visually distinct] → Header still has bold + white-on-dark-blue styling, so the size difference isn't needed for visual hierarchy.
