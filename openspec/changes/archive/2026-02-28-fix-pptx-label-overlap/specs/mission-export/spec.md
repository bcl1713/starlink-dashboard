## MODIFIED Requirements

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning.

**CHANGE:** Footer text styling and positioning updated for better visual
integration with gold bar branding, and mission date now displays actual leg
start date instead of export generation time. Slide titles now use human-readable
leg names instead of technical IDs, and footers display parent mission metadata
for multi-leg exports to improve readability and professionalism.

**CHANGE:** Route map generation MUST handle IDL crossings in all rendering
paths, including the fallback path used when route points lack timing data.

**CHANGE:** Timeline table font size reduced to 8pt for all cells (header and
data) to prevent column overflow. The segment column header is now blank to
eliminate unnecessary text wrapping.

**CHANGE:** Route map POI labels MUST use automatic collision avoidance to
prevent overlapping labels when markers are close together. Labels SHALL be
dynamically repositioned with leader lines connecting displaced labels to
their markers.

#### Scenario: Export leg with styled route map slide

**Given** a mission leg with a route and map
**When** user exports the mission as PowerPoint
**Then** each route map slide includes:

- Gold header bar and footer bar (0.15" height each)
- Light gray content background (RGB 248, 249, 250)
- Slide title "Leg X - Route Map" in 24pt bold
- Route map image centered within content area
- **POI labels automatically positioned to avoid overlap**
- **Leader lines connecting displaced labels to their markers**
- **Footer text with mission leg start date, mission ID, and organization**
- **Footer text positioned within the gold bar (y=5.47 inches)**
- **Footer text styled as 7pt white font for readability on gold background**
- Logo image in top-left corner (if exists)

#### Scenario: Export leg with color-coded timeline slide

**Given** a mission leg with timeline segments including NOMINAL, SOF,
DEGRADED, and CRITICAL statuses
**When** user exports the mission as PowerPoint
**Then** each timeline slide includes:

- Gold header bar and footer bar
- Light gray content background
- Slide title "Leg X - Timeline" in 24pt bold
- Timeline table header row with 8pt bold white text on dark blue background
- **The first column header (segment) SHALL be blank (empty string)**
- Each segment row displays:
  - Segment number (8pt)
  - Color-coded status badge with white text (8pt bold):
    - NOMINAL: Green (RGB 22, 163, 74)
    - SOF: Blue (RGB 2, 132, 199)
    - DEGRADED: Orange (RGB 234, 88, 12)
    - CRITICAL: Red (RGB 220, 38, 38)
  - Start time, end time, duration, reason (all 8pt)
  - Transport state indicators (✓ or ⚠)
- Visual separator (1px gray line) between segments
- **Footer with "Date: YYYY-MM-DD | Mission ID | Organization" where date
  is the mission leg start date**
- **Footer text positioned within the gold bar (y=5.47 inches)**
- **Footer text styled as 7pt white font**
- Logo image (if exists)

#### Scenario: Timeline table font size is uniform 8pt

**Given** a mission leg with timeline segments
**When** user exports the mission as PowerPoint
**Then** all table header cells SHALL use 8pt bold font
**And** all table data cells SHALL use 8pt font
**And** no cell in the timeline table SHALL use a font size larger than 8pt

#### Scenario: Segment column header is blank

**Given** a mission leg with timeline segments
**When** user exports the mission as PowerPoint
**Then** the first column of the timeline table header row SHALL display an empty string
**And** the first column of each data row SHALL still display the segment number
