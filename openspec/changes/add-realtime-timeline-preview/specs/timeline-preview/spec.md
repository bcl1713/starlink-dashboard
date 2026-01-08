# Timeline Preview Specification

## ADDED Requirements

### Requirement: Real-Time Timeline Calculation

The system SHALL calculate mission leg timelines in real-time as users modify
configuration parameters, without requiring explicit save operations.

#### Scenario: Configuration change triggers preview

- **WHEN** user modifies satellite transitions, outages, or AAR segments in the
  leg configuration UI
- **THEN** the system SHALL debounce the change for 500ms and trigger a timeline
  preview calculation
- **AND** display a loading indicator during calculation
- **AND** update the preview timeline within 1 second of the last input change

#### Scenario: Rapid changes are debounced

- **WHEN** user makes multiple rapid configuration changes within 500ms
- **THEN** the system SHALL cancel any in-flight preview requests
- **AND** only trigger one preview calculation 500ms after the last change

#### Scenario: Timing adjustment triggers preview

- **WHEN** user adjusts the leg departure time
- **THEN** the system SHALL recalculate the preview timeline with the new timing
  offset
- **AND** update all time-dependent calculations (satellite positions, coverage
  windows)

### Requirement: Preview API Endpoint

The system SHALL provide a backend API endpoint for calculating timeline
previews without persisting results to disk.

#### Scenario: Preview endpoint accepts configuration

- **WHEN** client sends POST request to
  `/api/v2/missions/{mission_id}/legs/{leg_id}/timeline/preview`
- **THEN** the system SHALL accept a request body containing transport
  configuration and optional adjusted departure time
- **AND** validate the configuration structure
- **AND** return HTTP 400 if configuration is invalid

#### Scenario: Preview calculation succeeds

- **WHEN** preview endpoint receives valid configuration
- **THEN** the system SHALL calculate the complete timeline using existing
  timeline calculation infrastructure
- **AND** return timeline segments with status, transport states, and reasons
- **AND** include route samples with lat/lon coordinates for map visualization
- **AND** respond within 500ms for routes with up to 300 waypoints (p95)

#### Scenario: Preview does not persist to disk

- **WHEN** preview endpoint calculates a timeline
- **THEN** the system SHALL NOT write timeline data to disk
- **AND** SHALL NOT modify mission leg files
- **AND** return ephemeral timeline data in response only

#### Scenario: Preview calculation fails gracefully

- **WHEN** preview calculation encounters an error (missing route, invalid
  satellite ID, etc.)
- **THEN** the system SHALL return HTTP 500 with error details
- **AND** log the error for debugging
- **AND** NOT corrupt any existing saved timeline data

### Requirement: Color-Coded Route Visualization

The system SHALL display mission route segments color-coded by communication
status during the planning phase.

#### Scenario: Nominal segments shown in green

- **WHEN** preview timeline indicates all transports (X-Band, CommKa, StarShield)
  are available for a segment
- **THEN** the system SHALL render that route segment in green (#2ecc71) on the
  map

#### Scenario: Degraded segments shown in yellow

- **WHEN** preview timeline indicates one transport is impacted or segment is in
  AAR window
- **THEN** the system SHALL render that route segment in yellow (#f1c40f) on the
  map

#### Scenario: Critical segments shown in red

- **WHEN** preview timeline indicates two or more transports are impacted
- **THEN** the system SHALL render that route segment in red (#e74c3c) on the map

#### Scenario: Map segments update in real-time

- **WHEN** preview timeline updates due to configuration changes
- **THEN** the system SHALL re-render route segment colors within 200ms
- **AND** maintain map position and zoom level
- **AND** keep existing markers and route line visible

#### Scenario: Temporal-to-spatial mapping

- **WHEN** mapping timeline segments to route coordinates
- **THEN** the system SHALL use route samples included in preview response
- **AND** filter samples by segment timestamp range
- **AND** render polylines connecting sample coordinates with segment color

### Requirement: Timeline Table Preview

The system SHALL display a detailed timeline table showing segment information
during the planning phase.

#### Scenario: Timeline table displays segment details

- **WHEN** preview timeline is available
- **THEN** the system SHALL display a table with columns: Segment #, Status,
  Start Time, End Time, Duration, X-Band State, CommKa State, StarShield State,
  Reasons
- **AND** color-code the status column with badges (green/yellow/red)
- **AND** format times in 24-hour UTC format

#### Scenario: Timeline table is collapsible

- **WHEN** user views timeline preview section
- **THEN** the system SHALL provide expand/collapse controls
- **AND** remember collapse state during session
- **AND** show segment count in section header (e.g., "Timeline Preview (143
  segments)")

#### Scenario: Large timelines are virtualized

- **WHEN** timeline contains more than 200 segments
- **THEN** the system SHALL virtualize the table rendering
- **AND** only render visible rows to maintain performance
- **AND** provide smooth scrolling through all segments

#### Scenario: Transport states are clearly indicated

- **WHEN** displaying transport states in timeline table
- **THEN** the system SHALL show AVAILABLE/DEGRADED/OFFLINE for each transport
- **AND** highlight degraded/offline states with appropriate colors
- **AND** display reasons for degradation in the Reasons column

### Requirement: Unsaved State Management

The system SHALL clearly distinguish between saved timeline data and preview
timeline data to prevent accidental data loss.

#### Scenario: Unsaved indicator when preview differs

- **WHEN** preview timeline differs from saved timeline
- **THEN** the system SHALL display an "Unsaved" badge in the timeline preview
  section
- **AND** enable the "Save Changes" button
- **AND** maintain preview state separately from saved state

#### Scenario: Save persists preview configuration

- **WHEN** user clicks "Save Changes" button with unsaved preview
- **THEN** the system SHALL persist the configuration to disk via PUT
  `/api/v2/missions/{id}/legs/{id}`
- **AND** regenerate and save the timeline to disk
- **AND** remove the "Unsaved" badge
- **AND** update saved state to match preview state

#### Scenario: Cancel discards preview changes

- **WHEN** user navigates away or clicks "Cancel" with unsaved preview
- **THEN** the system SHALL prompt for confirmation
- **AND** discard preview timeline if user confirms
- **AND** revert configuration to last saved state

#### Scenario: Preview state survives form edits

- **WHEN** user continues editing configuration after preview loads
- **THEN** the system SHALL maintain the previous preview until new preview
  completes
- **AND** show "Calculating..." indicator during new calculation
- **AND** update to new preview when calculation finishes

### Requirement: Performance Optimization

The system SHALL optimize preview calculations and UI rendering to maintain
responsive user experience.

#### Scenario: Request cancellation on rapid changes

- **WHEN** user makes new configuration change before previous preview completes
- **THEN** the system SHALL cancel the in-flight HTTP request
- **AND** immediately start new debounce timer
- **AND** prevent stale preview results from displaying

#### Scenario: Response caching for identical configs

- **WHEN** user makes configuration change then reverts to previous state
- **THEN** the system MAY use cached preview result if available
- **AND** avoid redundant backend calculation
- **AND** display cached result immediately

#### Scenario: Progressive rendering for complex routes

- **WHEN** route contains more than 300 waypoints
- **THEN** the system SHALL show summary statistics immediately
- **AND** progressively render timeline table rows
- **AND** maintain UI responsiveness during rendering

### Requirement: Preview Data Accuracy

The system SHALL ensure preview timeline calculations match saved timeline
calculations to maintain trust in preview results.

#### Scenario: Preview uses same calculation engine

- **WHEN** calculating preview timeline
- **THEN** the system SHALL use the same `build_mission_timeline()` function as
  saved timelines
- **AND** apply identical route sampling (60-second intervals)
- **AND** use identical coverage analysis algorithms
- **AND** apply identical azimuth constraint evaluations

#### Scenario: Preview includes route samples

- **WHEN** preview endpoint returns timeline
- **THEN** the system SHALL include route samples array with lat/lon/timestamp
  data
- **AND** include ka_coverage_set for each sample
- **AND** match sample timestamps to timeline segment boundaries

#### Scenario: Preview respects adjusted departure time

- **WHEN** leg has adjusted departure time set
- **THEN** the system SHALL apply the time offset to all timeline calculations
- **AND** use adjusted time for satellite position calculations
- **AND** reflect adjusted timing in all segment timestamps

### Requirement: Error Handling and Feedback

The system SHALL provide clear feedback when preview calculations fail or
encounter issues.

#### Scenario: Network error during preview

- **WHEN** preview API request fails due to network error
- **THEN** the system SHALL display an error message to user
- **AND** preserve the previous preview timeline if available
- **AND** allow user to retry the preview calculation

#### Scenario: Invalid configuration detected

- **WHEN** user enters invalid satellite ID or waypoint name
- **THEN** the system SHALL validate input before sending preview request
- **AND** display validation error inline with input field
- **AND** prevent preview calculation until validation passes

#### Scenario: Route not found error

- **WHEN** preview endpoint cannot find referenced route file
- **THEN** the system SHALL return HTTP 404 with error message
- **AND** display clear error to user indicating route is missing
- **AND** suggest uploading route or checking leg configuration

#### Scenario: Calculation timeout

- **WHEN** preview calculation exceeds 10 seconds (e.g., extremely complex route)
- **THEN** the system SHALL timeout the request
- **AND** display timeout message to user
- **AND** suggest simplifying configuration or contacting support
