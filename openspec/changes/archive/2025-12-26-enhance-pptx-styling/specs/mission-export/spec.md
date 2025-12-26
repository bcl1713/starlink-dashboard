# Spec: Mission Export

## ADDED Requirements

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning.

#### Scenario: Export mission with styled title slide

**Given** a mission with ID "mission-001" and name "Operation Alpha"
**When** user exports the mission as PowerPoint
**Then** the title slide includes:

- Gold header bar (RGB 212, 175, 55) at top (0.15" height)
- Gold footer bar (RGB 212, 175, 55) at bottom (0.15" height)
- Mission name displayed in 28pt bold text, centered
- Leg count summary (e.g., "2 Flight Legs")
- Organization name from mission description
- Logo image (if `logo.png` exists in assets directory)

#### Scenario: Export leg with styled route map slide

**Given** a mission leg with a route and map
**When** user exports the mission as PowerPoint
**Then** each route map slide includes:

- Gold header bar and footer bar (0.15" height each)
- Light gray content background (RGB 248, 249, 250)
- Slide title "Leg X - Route Map" in 24pt bold
- Route map image centered within content area
- Footer text with mission ID and organization
- Logo image in top-left corner (if exists)

#### Scenario: Export leg with color-coded timeline slide

**Given** a mission leg with timeline segments including NOMINAL, SOF, DEGRADED,
and CRITICAL statuses
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
- Footer with "Date: YYYY-MM-DD | Mission ID | Organization"
- Logo image (if exists)

#### Scenario: Export combined mission presentation

**Given** a mission with multiple legs
**When** user exports the combined mission PowerPoint
**Then** the presentation includes:

- Title slide with gold headers/footers and mission summary
- All leg slides (route maps and timelines) with consistent styling
- All slides use identical color scheme and branding
- All slides include appropriate footer context

#### Scenario: Export with missing logo

**Given** the logo file `logo.png` does NOT exist in assets directory
**When** user exports a mission as PowerPoint
**Then** the export succeeds without error
**And** logo is omitted from all slides
**And** a debug log message indicates logo was not found

### Requirement: Backward Compatibility

PPTX styling enhancements MUST NOT affect other export formats (CSV, XLSX, PDF)
or change the PowerPoint file structure.

#### Scenario: Other export formats unchanged

**Given** a mission with timeline data
**When** user exports as CSV, XLSX, or PDF
**Then** the output format and content remain identical to pre-enhancement behavior
**And** no visual styling changes are applied to these formats

#### Scenario: PowerPoint file structure preserved

**Given** a mission export as PowerPoint
**When** the PPTX file is generated
**Then** the file remains a valid PPTX file readable by PowerPoint, LibreOffice,
and other presentation software
**And** the slide count matches pre-enhancement behavior
**And** existing automation/scripts that process PPTX exports continue to work

## Status

Proposed
