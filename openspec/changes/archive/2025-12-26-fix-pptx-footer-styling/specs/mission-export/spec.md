# Spec: Mission Export

## MODIFIED Requirements

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning.

**CHANGE:** Footer text styling and positioning updated for better visual
integration with gold bar branding, and mission date now displays actual leg
start date instead of export generation time.

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

#### Scenario: Export leg with color-coded timeline slide

**Given** a mission leg with timeline segments including NOMINAL, SOF,
DEGRADED, and CRITICAL statuses
**When** user exports the mission as PowerPoint
**Then** each timeline slide includes:

- Gold header bar and footer bar
- Light gray content background
- Slide title "Leg X - Timeline" in 24pt bold
- Each segment row displays:
  - Segment number (11pt bold)
  - Color-coded status badge with white text (11pt bold):
    - NOMINAL: Green (RGB 22, 163, 74)
    - SOF: Blue (RGB 2, 132, 199)
    - DEGRADED: Orange (RGB 234, 88, 12)
    - CRITICAL: Red (RGB 220, 38, 38)
  - Start time, end time, duration, reason
  - Transport state indicators (✓ or ⚠)
- Visual separator (1px gray line) between segments
- **Footer with "Date: YYYY-MM-DD | Mission ID | Organization" where date
  is the mission leg start date**
- **Footer text positioned within the gold bar (y=5.47 inches)**
- **Footer text styled as 7pt white font**
- Logo image (if exists)

#### Scenario: Mission leg date displays correctly

**Given** a mission leg with timeline segments starting at 2025-01-15 10:00:00
UTC
**And** the PowerPoint is exported on 2025-01-20 14:30:00 UTC
**When** user opens the generated PowerPoint file
**Then** the footer displays "Date: 2025-01-15 | ..." (the leg start date)
**And** the footer does NOT display 2025-01-20 (the export generation date)

#### Scenario: Mission with no timeline segments

**Given** a mission leg with no timeline segments
**When** user exports the mission as PowerPoint
**Then** the footer date falls back to the timeline creation timestamp
**And** the export succeeds without error

#### Scenario: Footer text is readable within gold bar

**Given** any mission leg exported to PowerPoint
**When** user views the slides in presentation mode
**Then** the footer text appears inside the gold bar at the bottom
**And** the white 7pt text is clearly readable against the gold background
(RGB 212, 175, 55)
**And** the text is centered horizontally within the slide

## Status

Proposed
