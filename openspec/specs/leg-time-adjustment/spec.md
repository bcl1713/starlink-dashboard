# leg-time-adjustment Specification

## Purpose
TBD - created by archiving change adjust-leg-takeoff-time. Update Purpose after archive.
## Requirements
### Requirement: Adjusted Departure Time Field

The `MissionLeg` model SHALL include an optional `adjusted_departure_time` field that stores a user-specified departure time override. When set, this value overrides the departure time extracted from the KML route file.

#### Scenario: Create leg with adjusted departure time

**Given** a user is creating a new mission leg with route "leg-6-rev-6.kml"
**And** the KML route has original departure time "2025-10-27T16:45:00Z"
**When** the user sets `adjusted_departure_time` to "2025-10-27T16:05:00Z"
**Then** the system stores `adjusted_departure_time` as "2025-10-27T16:05:00Z"
**And** the calculated time offset is -40 minutes
**And** all waypoint timestamps are shifted -40 minutes from their KML values
**And** the mission timeline uses the adjusted times

#### Scenario: Create leg without adjusted departure time

**Given** a user is creating a new mission leg with route "leg-6-rev-6.kml"
**And** the KML route has original departure time "2025-10-27T16:45:00Z"
**When** the user does not provide `adjusted_departure_time`
**Then** `adjusted_departure_time` is `null`
**And** the system uses the original KML departure time "2025-10-27T16:45:00Z"
**And** no time offset is applied

#### Scenario: Update leg to set adjusted departure time

**Given** a mission leg exists with original departure time "2025-10-27T16:45:00Z"
**And** `adjusted_departure_time` is currently `null`
**When** the user updates the leg with `adjusted_departure_time` set to "2025-10-27T17:25:00Z"
**Then** the system stores `adjusted_departure_time` as "2025-10-27T17:25:00Z"
**And** the calculated time offset is +40 minutes
**And** the mission timeline is regenerated with all times shifted +40 minutes

#### Scenario: Clear adjusted departure time

**Given** a mission leg exists with `adjusted_departure_time` set to "2025-10-27T16:05:00Z"
**When** the user updates the leg with `adjusted_departure_time` set to `null`
**Then** `adjusted_departure_time` is cleared
**And** the system reverts to using the original KML departure time
**And** the mission timeline is regenerated with original times

### Requirement: Timeline Calculation with Time Offset

The timeline calculation SHALL automatically apply the time offset when `adjusted_departure_time` is set. All waypoint times, segment times, and advisories SHALL reflect the adjusted schedule.

#### Scenario: Calculate timeline with adjusted departure time

**Given** a mission leg has route with original departure "2025-10-27T16:45:00Z" and arrival "2025-10-27T22:30:00Z"
**And** the leg has `adjusted_departure_time` set to "2025-10-27T16:05:00Z"
**And** the route has 3 waypoints with original times: 16:45Z, 19:00Z, 22:30Z
**When** the system calculates the mission timeline
**Then** the offset is calculated as -40 minutes
**And** the effective departure time is "2025-10-27T16:05:00Z"
**And** the effective arrival time is "2025-10-27T21:50:00Z"
**And** the waypoint times are adjusted to: 16:05Z, 18:20Z, 21:50Z
**And** all timeline segments use the adjusted times

#### Scenario: Calculate timeline without adjusted departure time

**Given** a mission leg has route with original departure "2025-10-27T16:45:00Z"
**And** `adjusted_departure_time` is `null`
**When** the system calculates the mission timeline
**Then** no time offset is applied
**And** the effective departure time is "2025-10-27T16:45:00Z"
**And** all waypoint and segment times match the original KML values

#### Scenario: Satellite transitions maintain relative positioning

**Given** a mission leg has `adjusted_departure_time` set with -40 minute offset
**And** the leg has an X transition configured at original time "2025-10-27T18:30:00Z"
**When** the system calculates the mission timeline
**Then** the X transition occurs at adjusted time "2025-10-27T17:50:00Z"
**And** the transition remains at the same route distance/location
**And** transition buffers are calculated using the adjusted time

### Requirement: API Support for Adjusted Departure Time

The mission leg API endpoints SHALL accept and return the `adjusted_departure_time` field. The field SHALL be optional and nullable.

#### Scenario: POST leg with adjusted departure time

**Given** a user has a valid KML route file
**When** the user sends POST request to `/api/v2/missions/{mission_id}/legs` with:
```json
{
  "id": "leg-1",
  "name": "Leg 1",
  "route_id": "leg-6-rev-6",
  "adjusted_departure_time": "2025-10-27T16:05:00Z",
  "transports": { ... }
}
```
**Then** the response has status code 201
**And** the response body includes `adjusted_departure_time: "2025-10-27T16:05:00Z"`
**And** the leg is stored with the adjusted departure time

#### Scenario: PATCH leg to update adjusted departure time

**Given** a mission leg exists with `adjusted_departure_time` as `null`
**When** the user sends PATCH request to `/api/v2/missions/{mission_id}/legs/{leg_id}` with:
```json
{
  "adjusted_departure_time": "2025-10-27T17:25:00Z"
}
```
**Then** the response has status code 200
**And** the response body includes `adjusted_departure_time: "2025-10-27T17:25:00Z"`
**And** the leg's adjusted departure time is updated

#### Scenario: PATCH leg to clear adjusted departure time

**Given** a mission leg exists with `adjusted_departure_time` set to "2025-10-27T16:05:00Z"
**When** the user sends PATCH request to `/api/v2/missions/{mission_id}/legs/{leg_id}` with:
```json
{
  "adjusted_departure_time": null
}
```
**Then** the response has status code 200
**And** the response body includes `adjusted_departure_time: null`
**And** the timeline is regenerated using original KML times

#### Scenario: Invalid adjusted departure time format

**Given** a mission leg exists
**When** the user sends PATCH request with `adjusted_departure_time: "2025-10-27 16:05"`
**Then** the response has status code 400
**And** the error message indicates "Invalid ISO-8601 datetime format"

### Requirement: Route Update Clears Adjusted Departure Time

When a mission leg's route is updated via KML upload, the `adjusted_departure_time` field SHALL be automatically cleared. This assumes the new KML has accurate timing.

#### Scenario: Upload new route clears adjusted departure time

**Given** a mission leg exists with route "leg-6-rev-5.kml"
**And** the leg has `adjusted_departure_time` set to "2025-10-27T16:05:00Z"
**When** the user uploads a new route "leg-6-rev-6.kml" via PUT `/api/v2/missions/{mission_id}/legs/{leg_id}/route`
**Then** the response has status code 200
**And** the leg's `route_id` is updated to "leg-6-rev-6"
**And** the leg's `adjusted_departure_time` is set to `null`
**And** the timeline is regenerated using the new KML's original times

#### Scenario: Upload new route with no prior adjustment

**Given** a mission leg exists with `adjusted_departure_time` as `null`
**When** the user uploads a new route via PUT `/api/v2/missions/{mission_id}/legs/{leg_id}/route`
**Then** the response has status code 200
**And** `adjusted_departure_time` remains `null`
**And** the timeline uses the new KML's original times

### Requirement: Large Offset Warning

The system SHALL return a warning when the time offset exceeds ±8 hours (±480 minutes). The warning SHALL be informational only and SHALL NOT block the operation.

#### Scenario: Set adjusted departure time with large offset

**Given** a mission leg has original departure time "2025-10-27T16:45:00Z"
**When** the user updates the leg with `adjusted_departure_time` set to "2025-10-28T02:00:00Z"
**Then** the calculated offset is +9 hours 15 minutes
**And** the response has status code 200
**And** the response includes a warning: "Large time shift detected (>8 hours). Consider requesting new route from flight planners."
**And** the adjusted departure time is successfully applied
**And** the operation is NOT blocked

#### Scenario: Set adjusted departure time with small offset

**Given** a mission leg has original departure time "2025-10-27T16:45:00Z"
**When** the user updates the leg with `adjusted_departure_time` set to "2025-10-27T18:00:00Z"
**Then** the calculated offset is +1 hour 15 minutes
**And** the response has status code 200
**And** the response does NOT include a warning
**And** the adjusted departure time is successfully applied

### Requirement: Export Documents Use Adjusted Times

All mission exports (PPTX, CSV) SHALL use the adjusted times when `adjusted_departure_time` is set. Exports SHALL reflect the effective departure time, not the original KML time.

#### Scenario: PPTX export with adjusted departure time

**Given** a mission leg has original departure "2025-10-27T16:45:00Z"
**And** the leg has `adjusted_departure_time` set to "2025-10-27T16:05:00Z"
**When** the user exports the mission as PPTX
**Then** the PPTX footer displays date "2025-10-27" (from adjusted time)
**And** the timeline slide shows segment times based on adjusted schedule
**And** the original KML time is NOT displayed

#### Scenario: CSV export with adjusted departure time

**Given** a mission leg has `adjusted_departure_time` set with -40 minute offset
**And** the leg has timeline segments with times: 16:05Z, 18:20Z, 21:50Z (adjusted)
**When** the user exports the mission timeline as CSV
**Then** the CSV contains the adjusted segment times
**And** all timestamps reflect the -40 minute offset
**And** the original KML times are NOT present in the export

#### Scenario: PPTX export without adjusted departure time

**Given** a mission leg has `adjusted_departure_time` as `null`
**And** the original KML departure is "2025-10-27T16:45:00Z"
**When** the user exports the mission as PPTX
**Then** the PPTX footer displays date "2025-10-27" (from original KML)
**And** the timeline slide shows segment times based on original KML schedule

### Requirement: Frontend Timing Section

The leg detail page SHALL include a dedicated "Timing" section that displays original and adjusted departure times with controls for setting and clearing the adjustment.

#### Scenario: Display timing section without adjustment

**Given** the user is viewing a leg detail page
**And** the leg has original departure time "2025-10-27T16:45:00Z"
**And** `adjusted_departure_time` is `null`
**When** the page loads
**Then** the Timing section displays:
- "Original Departure: 2025-10-27 16:45:00Z" (read-only)
- "Current Departure: 2025-10-27 16:45:00Z" (editable datetime input)
- "Reset to Original" button (disabled)
**And** no adjustment indicator is shown

#### Scenario: Display timing section with adjustment

**Given** the user is viewing a leg detail page
**And** the leg has original departure time "2025-10-27T16:45:00Z"
**And** `adjusted_departure_time` is "2025-10-27T16:05:00Z"
**When** the page loads
**Then** the Timing section displays:
- "Original Departure: 2025-10-27 16:45:00Z" (read-only)
- "Current Departure: 2025-10-27 16:05:00Z" (editable datetime input)
- Visual indicator: "⚠️ Adjusted (40 min earlier)"
- "Reset to Original" button (enabled)

#### Scenario: User sets adjusted departure time

**Given** the user is viewing a leg detail page in the Timing section
**And** the original departure time is "2025-10-27T16:45:00Z"
**When** the user changes the "Current Departure" input to "2025-10-27T17:25:00Z"
**And** clicks Save
**Then** the frontend sends PATCH request with `adjusted_departure_time: "2025-10-27T17:25:00Z"`
**And** the leg is updated
**And** the timeline visualization refreshes with adjusted times
**And** the adjustment indicator shows "⚠️ Adjusted (40 min later)"

#### Scenario: User resets to original departure time

**Given** the user is viewing a leg detail page with `adjusted_departure_time` set
**When** the user clicks "Reset to Original" button
**Then** the frontend sends PATCH request with `adjusted_departure_time: null`
**And** the leg is updated
**And** the "Current Departure" input reverts to original KML time
**And** the adjustment indicator is removed
**And** the timeline visualization refreshes with original times

#### Scenario: Warning for large offset in frontend

**Given** the user is viewing a leg detail page
**And** the original departure time is "2025-10-27T16:45:00Z"
**When** the user changes the "Current Departure" input to "2025-10-28T02:00:00Z"
**And** clicks Save
**Then** the frontend calculates offset as +9 hours 15 minutes
**And** the frontend sends PATCH request with the adjusted time
**And** the API response includes a warning about large time shift
**And** the frontend displays a warning banner: "Large time shift detected (>8 hours). Consider requesting new route from flight planners."
**And** the adjusted time is successfully applied

### Requirement: Persistence and Data Integrity

The `adjusted_departure_time` field SHALL persist with the mission leg configuration. All satellite configurations, AAR windows, and outage settings SHALL remain intact when departure time is adjusted.

#### Scenario: Adjusted departure time persists on reload

**Given** a mission leg has `adjusted_departure_time` set to "2025-10-27T16:05:00Z"
**When** the user reloads the leg detail page
**Then** the leg still has `adjusted_departure_time` as "2025-10-27T16:05:00Z"
**And** the timeline displays adjusted times
**And** the Timing section shows the adjustment

#### Scenario: Satellite configurations preserved during time adjustment

**Given** a mission leg has:
- X transitions configured at specific coordinates
- Ka outage windows
- AAR windows defined by waypoint names
- Ku outage overrides
**When** the user sets `adjusted_departure_time` to shift departure by 2 hours
**Then** all X transition coordinates remain unchanged
**And** all Ka outage windows remain defined (times adjust with offset)
**And** all AAR windows remain defined by same waypoint names
**And** all Ku outage override times adjust with offset
**And** no configuration data is lost

#### Scenario: Mission package export includes adjusted time

**Given** a mission with 2 legs
**And** leg 1 has `adjusted_departure_time` set
**And** leg 2 has no adjustment
**When** the user exports the mission package as a ZIP file
**Then** leg 1's exports (PPTX, CSV) use adjusted times
**And** leg 2's exports use original KML times
**And** the mission-level exports reflect both legs correctly

