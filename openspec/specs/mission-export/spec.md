# mission-export Specification

## Purpose
TBD - created by archiving change enhance-pptx-styling. Update Purpose after archive.
## Requirements
### Requirement: Supported Export Formats

Mission and leg timeline exports MUST support CSV and PPTX formats only. PDF and XLSX formats are no longer supported to reduce complexity and improve performance.

**CHANGE:** Removed support for PDF and XLSX export formats. Only CSV (data analysis) and PPTX (presentations) are now supported.

#### Scenario: Export mission timeline as CSV

**Given** a mission with timeline data
**When** user requests CSV export
**Then** the system generates a CSV file with timeline segments, advisories, and statistics
**And** the CSV contains all data in machine-readable format suitable for analysis

#### Scenario: Export mission timeline as PPTX

**Given** a mission with timeline data
**When** user requests PPTX export
**Then** the system generates a PowerPoint presentation with:
- Title slide with mission metadata
- Route map slide with color-coded timeline status
- Timeline table slide with segment details
- Professional styling (gold headers/footers, logos, color-coded status)
**And** the PPTX is suitable for executive briefings and operational planning

#### Scenario: Request unsupported PDF format

**Given** a mission with timeline data
**When** user requests PDF export via API
**Then** the system returns a 400 Bad Request error
**And** the error message indicates "Unsupported export format: pdf"
**And** the error message suggests using PPTX for presentations or CSV for data

#### Scenario: Request unsupported XLSX format

**Given** a mission with timeline data
**When** user requests XLSX export via API
**Then** the system returns a 400 Bad Request error
**And** the error message indicates "Unsupported export format: xlsx"
**And** the error message suggests using CSV for tabular data

#### Scenario: Mission package contains only CSV and PPTX

**Given** a mission with 2 legs
**When** user exports the mission as a package (ZIP file)
**Then** the package contains:
- Per-leg exports: `exports/legs/{leg-id}/timeline.csv` for each leg
- Per-leg exports: `exports/legs/{leg-id}/slides.pptx` for each leg
- Mission-level exports: `exports/mission/mission-timeline.csv`
- Mission-level exports: `exports/mission/mission-slides.pptx`
**And** the package does NOT contain any `.pdf` or `.xlsx` files
**And** the total file count is 6 (4 leg files + 2 mission files)

#### Scenario: Export performance improvement

**Given** a mission with 2 legs requiring timeline exports
**When** the mission package is generated
**Then** the export completes in approximately 50% less time compared to generating 4 formats
**And** no PDF or XLSX generation overhead occurs

### Requirement: Migration Path for Legacy Formats

Users requiring PDF or XLSX functionality MUST use alternative approaches since these formats are no longer supported.

**CHANGE:** Added migration guidance for users who previously relied on PDF/XLSX exports.

#### Scenario: User needs PDF output

**Given** a user previously relied on PDF exports
**When** they need a PDF version of mission data
**Then** they should export as PPTX
**And** convert PPTX to PDF using PowerPoint, LibreOffice, or online converters
**And** the PDF retains all visual styling and content from PPTX

#### Scenario: User needs XLSX output

**Given** a user previously relied on XLSX exports
**When** they need Excel-compatible data
**Then** they should export as CSV
**And** import CSV into Excel, LibreOffice Calc, or Google Sheets
**And** the tabular data is fully preserved

#### Scenario: Automated systems request PDF/XLSX

**Given** an automated system configured to download PDF or XLSX exports
**When** the system makes an API request with format=pdf or format=xlsx
**Then** the API returns a 400 error with clear message
**And** the error message includes recommended format alternatives
**And** system administrators can update automation to use CSV or PPTX

### Requirement: Professional PPTX Styling

PowerPoint exports MUST use professional styling with branded colors, headers,
footers, and visual hierarchy suitable for executive briefings and operational
planning.

**CHANGE:** Footer text styling and positioning updated for better visual
integration with gold bar branding, and mission date now displays actual leg
start date instead of export generation time. Slide titles now use human-readable
leg names instead of technical IDs, and footers display parent mission metadata
for multi-leg exports to improve readability and professionalism.

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

#### Scenario: Slide titles use human-readable leg names

**Given** a mission leg with name "Leg 1 - Departure"
**When** user exports the mission as PowerPoint
**Then** the route map slide title displays "Leg 1 - Departure - Route Map"
**And** the timeline slide title displays "Leg 1 - Departure - Timeline"
**And** the slide titles do NOT display the technical leg ID (e.g., "leg-1")

#### Scenario: Multi-leg mission uses parent mission metadata in footer

**Given** a parent mission with name "26-05" and description "CONUS California"
**And** the mission contains a leg with name "Leg 1 - Departure"
**When** user exports the mission package as a ZIP file
**Then** the leg's PowerPoint slides display:
- Slide title: "Leg 1 - Departure - Route Map"
- Footer: "Date: 2025-01-15 | 26-05 | CONUS California"
**And** the footer uses the parent mission's name and description
**And** the footer does NOT use the leg's individual metadata

#### Scenario: Standalone leg export uses leg metadata in footer

**Given** a standalone mission leg with name "Leg 1" and description "Test Flight"
**And** no parent mission is associated
**When** user exports the leg as PowerPoint
**Then** the slide footer displays "Date: 2025-01-15 | Leg 1 | Test Flight"
**And** the footer uses the leg's own metadata

#### Scenario: Missing description handled gracefully

**Given** a mission with name "26-05" but no description
**When** user exports the mission as PowerPoint
**Then** the footer displays "Date: 2025-01-15 | 26-05"
**And** the footer does NOT display a trailing separator (no " | ")
**And** the footer does NOT display "Organization" placeholder text

#### Scenario: Fallback to leg ID when name missing

**Given** a mission leg with no name field set (edge case)
**When** user exports the mission as PowerPoint
**Then** the slide title falls back to the leg ID (e.g., "leg-1 - Route Map")
**And** the export succeeds without error

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

### Requirement: Update Leg Route via KML Upload

The system SHALL provide an endpoint at `PUT /api/v2/missions/{mission_id}/legs/{leg_id}/route` that accepts a KML file upload and updates the leg's route while preserving satellite configurations. The endpoint MUST replace the route file on disk, update the route_id if the filename changes, preserve X satellite transitions and Ka/Ku outage configurations, validate AAR windows against the new route's waypoint names, remove AAR windows that reference waypoints no longer present in the updated route, regenerate the mission timeline with the new route geometry, delete existing route-associated POIs and re-import POIs from the new KML's waypoint placemarks, and return the updated leg with warnings if AAR windows were removed.

**Rationale:** Mission planners frequently receive updated routes in the weeks before a mission due to timing adjustments, waypoint changes, or path modifications. Forcing users to delete and recreate entire legs to update a route loses hours of satellite planning work and is error-prone. This capability enables in-place route updates while preserving all manually configured satellite planning.

#### Scenario: Update route with compatible AAR windows

**Given** a mission leg exists with:
- Route ID "leg-6-rev-5" containing waypoint "REFUEL_POINT_ALPHA"
- X satellite transitions configured
- Ka outage windows defined
- An AAR window referencing "REFUEL_POINT_ALPHA"

**When** a PUT request is sent to `/api/v2/missions/{mission_id}/legs/{leg_id}/route` with a KML file named "leg-6-rev-6.kml" that still contains waypoint "REFUEL_POINT_ALPHA"

**Then** the response has status code 200

**And** the leg's route_id is updated to "leg-6-rev-6"

**And** the old route file "leg-6-rev-5.kml" is deleted from disk

**And** the new route file "leg-6-rev-6.kml" is saved

**And** all X satellite transitions are preserved in the leg configuration

**And** all Ka outage windows are preserved

**And** the AAR window referencing "REFUEL_POINT_ALPHA" is preserved

**And** the mission timeline is regenerated with the new route geometry

**And** old POIs associated with "leg-6-rev-5" are deleted

**And** new POIs are imported from "leg-6-rev-6.kml" waypoint placemarks

**And** the response includes no warnings about removed AAR windows

#### Scenario: Update route removes AAR windows with missing waypoints

**Given** a mission leg exists with:
- Route ID "leg-6-rev-5" containing waypoints "REFUEL_ALPHA" and "REFUEL_BRAVO"
- AAR windows referencing "REFUEL_ALPHA" and "REFUEL_BRAVO"
- X satellite transitions configured

**When** a PUT request is sent to `/api/v2/missions/{mission_id}/legs/{leg_id}/route` with a KML file named "leg-6-rev-6.kml" that only contains waypoint "REFUEL_ALPHA"

**Then** the response has status code 200

**And** the leg's AAR windows are updated to only include the window referencing "REFUEL_ALPHA"

**And** the AAR window referencing "REFUEL_BRAVO" is removed

**And** the response includes a warning: "Removed 1 AAR window(s) due to missing waypoints: REFUEL_BRAVO"

**And** X satellite transitions are preserved

**And** the mission timeline is regenerated successfully

#### Scenario: Leg not found

**Given** no leg exists with ID "nonexistent-leg" in mission "test-mission"

**When** a PUT request is sent to `/api/v2/missions/test-mission/legs/nonexistent-leg/route` with a valid KML file

**Then** the response has status code 404

**And** the error message indicates "Leg nonexistent-leg not found in mission"

#### Scenario: Invalid KML file

**Given** a mission leg exists with ID "leg-1"

**When** a PUT request is sent to `/api/v2/missions/mission-1/legs/leg-1/route` with a malformed KML file that fails parsing

**Then** the response has status code 400

**And** the error message indicates "Failed to parse KML file"

**And** the original route file remains unchanged on disk

**And** the leg's route_id and configuration remain unchanged

#### Scenario: Mission not found

**Given** no mission exists with ID "nonexistent-mission"

**When** a PUT request is sent to `/api/v2/missions/nonexistent-mission/legs/leg-1/route` with a valid KML file

**Then** the response has status code 404

**And** the error message indicates "Mission nonexistent-mission not found"

#### Scenario: Timeline regeneration after route update

**Given** a mission leg exists with route "original-route.kml" and satellite transitions

**When** the route is updated via PUT to `/api/v2/missions/{mission_id}/legs/{leg_id}/route` with "updated-route.kml"

**Then** the timeline JSON file at `data/missions/{leg_id}.timeline.json` is regenerated

**And** the timeline uses the new route geometry for GPS projections

**And** satellite transitions remain at their configured locations relative to the route

**And** timing data reflects the new route's speed profile and waypoint timestamps

#### Scenario: Route file replacement on disk

**Given** a mission leg exists with route_id "route-v1" stored at `/data/routes/route-v1.kml`

**When** a PUT request updates the route with a file named "route-v2.kml"

**Then** the file `/data/routes/route-v1.kml` is deleted from disk

**And** the file `/data/routes/route-v2.kml` is created with the new KML content

**And** the route manager's cache is updated to reflect the new route

**And** the leg's route_id field is updated to "route-v2"

### Requirement: Frontend Route Update UI

The leg detail page SHALL provide a "Update Route" button that allows users to upload a replacement KML file. The UI MUST display the current route filename, MUST provide a file upload input that accepts only .kml files, MUST show upload progress, MUST display success confirmation with the new route name, MUST show warnings if AAR windows were removed due to missing waypoints, and MUST refresh the route map and timeline visualizations after successful upload.

**Rationale:** Users need a convenient way to update leg routes directly from the leg detail view without complex workflows.

#### Scenario: Upload replacement route successfully

**Given** the user is viewing a leg detail page for a leg with route "leg-6-rev-5.kml"

**When** the user clicks the "Update Route" button

**Then** a file upload dialog appears

**When** the user selects a file "leg-6-rev-6.kml" and confirms

**Then** a loading indicator is shown

**And** the KML file is uploaded to `PUT /api/v2/missions/{mission_id}/legs/{leg_id}/route`

**When** the upload completes successfully with no warnings

**Then** a success message is displayed: "Route updated to leg-6-rev-6"

**And** the route map visualization refreshes to show the new route path

**And** the timeline table refreshes to show updated timing data

**And** the displayed route filename updates to "leg-6-rev-6.kml"

#### Scenario: Upload route with AAR window warnings

**Given** the user is viewing a leg detail page

**When** the user uploads a new route KML file

**And** the API response includes warnings: "Removed 2 AAR window(s) due to missing waypoints: REFUEL_ALPHA, REFUEL_BRAVO"

**Then** a warning banner is displayed with the message

**And** the route update is still applied successfully

**And** the user can review the updated leg configuration and add new AAR windows if needed

#### Scenario: Upload invalid KML file

**Given** the user is viewing a leg detail page

**When** the user uploads a malformed KML file

**Then** an error message is displayed: "Failed to parse KML file"

**And** the route is not updated

**And** the original route visualization remains unchanged

#### Scenario: Upload non-KML file

**Given** the user is viewing a leg detail page

**When** the user attempts to select a file with extension .gpx or .geojson

**Then** the file input rejects the file

**And** a validation message is displayed: "Only .kml files are allowed"

### Requirement: API Client Integration

The frontend missions API service SHALL include an `updateLegRoute` method that accepts a mission ID, leg ID, and KML file. The method MUST send a PUT request to `/api/v2/missions/{missionId}/legs/{legId}/route` with multipart/form-data encoding, MUST be type-safe using TypeScript interfaces, and MUST return a Promise resolving to the updated MissionLeg object with any warnings.

**Rationale:** Provides type-safe, reusable API integration for route updates with proper file upload handling.

#### Scenario: API service updateLegRoute method

**Given** the missions API service is imported

**When** `missionsApi.updateLegRoute(missionId, legId, kmlFile)` is called

**Then** a PUT request is sent to `/api/v2/missions/{missionId}/legs/{legId}/route`

**And** the request uses multipart/form-data encoding

**And** the KML file is sent as the "file" field

**And** the response is typed as `{ leg: MissionLeg, warnings?: string[] }`

#### Scenario: React Query hook for route updates

**Given** a component uses the `useUpdateLegRoute()` hook

**When** the mutation is triggered with a KML file

**Then** the API call is executed

**And** on success, the leg cache is invalidated

**And** the mission cache is invalidated

**And** the UI re-fetches fresh mission and leg data

