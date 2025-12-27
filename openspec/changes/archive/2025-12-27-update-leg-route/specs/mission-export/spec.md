## ADDED Requirements

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
