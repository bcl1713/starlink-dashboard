# PPTX Labeling Specification

## MODIFIED Requirements

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning. **Slide titles and footers MUST use human-readable mission and leg
names instead of technical identifiers.**

**CHANGE:** Updated slide titles and footers to use human-readable leg names
(`mission.name`) and mission metadata (`mission.name | mission.description`)
instead of technical IDs.

#### Scenario: Export leg with human-readable slide title

**Given** a mission leg with id "leg-1" and name "Leg 1"
**And** the mission has description "Test Flight"
**When** user exports the mission as PowerPoint
**Then** the route map slide title displays "Leg 1 - Route Map"
**And** the timeline slide title displays "Leg 1 - Timeline"
**And** the slide title does NOT display "leg-1"

#### Scenario: Export leg with mission metadata in footer

**Given** a mission leg with name "Leg 1"
**And** the mission has name "26-05"
**And** the mission has description "CONUS California"
**When** user exports the mission as PowerPoint
**Then** the route map slide footer displays "26-05 | CONUS California"
**And** the timeline slide footer displays "Date: YYYY-MM-DD | 26-05 | CONUS California"
**And** the footer text appears in white 7pt font within the gold bar
**And** the footer does NOT display "Organization"

#### Scenario: Export leg with styled route map slide

**Given** a mission leg with name "Leg 6 Rev 6" and a route map
**And** the mission has name "Operation Falcon" and description "Transcontinental mission"
**When** user exports the mission as PowerPoint
**Then** each route map slide includes:

- Gold header bar and footer bar (0.15" height each)
- Light gray content background (RGB 248, 249, 250)
- **Slide title "Leg 6 Rev 6 - Route Map" in 24pt bold**
- Route map image centered within content area
- **Footer text "Operation Falcon | Transcontinental mission"**
- Footer text positioned within the gold bar (y=5.47 inches)
- Footer text styled as 7pt white font for readability on gold background
- Logo image in top-left corner (if exists)

#### Scenario: Export leg with color-coded timeline slide

**Given** a mission leg with name "Leg 6 Rev 6" and timeline segments
**And** the leg start date is 2025-01-15
**And** the mission has name "Operation Falcon" and description "Transcontinental mission"
**When** user exports the mission as PowerPoint
**Then** each timeline slide includes:

- Gold header bar and footer bar
- Light gray content background
- **Slide title "Leg 6 Rev 6 - Timeline" in 24pt bold**
- Each segment row displays color-coded status badges and timing data
- **Footer with "Date: 2025-01-15 | Operation Falcon | Transcontinental mission"**
- Footer text positioned within the gold bar (y=5.47 inches)
- Footer text styled as 7pt white font
- Logo image (if exists)

#### Scenario: Fallback to leg ID when mission object unavailable

**Given** a standalone timeline export without a mission object
**When** user exports the timeline as PowerPoint
**Then** the slide title falls back to using the timeline's mission_leg_id
**And** the footer falls back to displaying the mission_leg_id
**And** the export succeeds without error

#### Scenario: Fallback to mission ID when name is missing

**Given** a mission leg with id "mission-001" but no name field
**When** user exports the mission as PowerPoint
**Then** the slide title displays the mission.id value
**And** the footer displays the mission.id value
**And** the export succeeds without error

#### Scenario: Handle missing mission description

**Given** a mission leg with name "Leg 1"
**And** the mission has name "26-05" but no description
**When** user exports the mission as PowerPoint
**Then** the footer displays "26-05" (without trailing separator)
**And** the export succeeds without error
**And** no placeholder text like "Organization" appears

#### Scenario: Multi-leg mission package with parent mission metadata

**Given** a multi-leg mission with:
- Mission name: "26-05"
- Mission description: "CONUS California"
- Leg 1: name "Leg 1 - Departure"
- Leg 2: name "Leg 2 - Return"
**When** user exports the mission package as ZIP
**Then** Leg 1 slides display title "Leg 1 - Departure - Route Map"
**And** Leg 1 footer displays "26-05 | CONUS California"
**And** Leg 2 slides display title "Leg 2 - Return - Route Map"
**And** Leg 2 footer displays "26-05 | CONUS California"
**And** each leg slide title uses the leg's own name
**And** all leg footers use the parent mission's name and description

#### Scenario: Fallback to leg metadata when parent mission not found

**Given** a mission leg with name "Leg 1" and description "Standalone leg"
**And** a parent_mission_id is provided but the parent mission does not exist
**When** user exports the mission as PowerPoint
**Then** the slide title displays "Leg 1 - Route Map"
**And** the footer falls back to leg metadata: "Leg 1 | Standalone leg"
**And** the export succeeds without error
**And** a warning is logged about the missing parent mission
