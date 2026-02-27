## MODIFIED Requirements

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning.

**CHANGE:** Route map generation MUST handle IDL crossings in all rendering
paths, including the fallback path used when route points lack timing data.

#### Scenario: Export leg with styled route map slide

**Given** a mission leg with a route and map
**When** user exports the mission as PowerPoint
**Then** each route map slide includes:

- Gold header bar and footer bar (0.15" height each)
- Light gray content background (RGB 248, 249, 250)
- Slide title "Leg X - Route Map" in 24pt bold
- Route map image centered within content area
- **Footer text with mission leg start date, mission ID, and organization**
- **Footer text positioned within the gold bar (y=5.47 inches)**
- **Footer text styled as 7pt white font for readability on gold background**
- Logo image in top-left corner (if exists)

#### Scenario: IDL-crossing route renders without wrapping in PPTX map

**Given** a mission leg with a route that crosses the International Date Line
**And** the route points may or may not have `expected_arrival_time` populated
**When** user exports the mission as PowerPoint
**Then** the route map SHALL render all route segments taking the short path across the IDL
**And** no route segment SHALL wrap around the globe through 0° longitude
**And** this SHALL apply regardless of whether route points have timing data
**And** the map projection SHALL center on the route's midpoint in Pacific view

#### Scenario: IDL-crossing route with mixed timing data

**Given** a mission leg with a route that crosses the IDL
**And** some route points have `expected_arrival_time` and some do not
**When** the PPTX route map is generated
**Then** timed segments SHALL render with color-coded status and correct IDL handling
**And** untimed segments SHALL render with fallback coloring and correct IDL handling
**And** there SHALL be no visual discontinuity at the boundary between timed and untimed segments
