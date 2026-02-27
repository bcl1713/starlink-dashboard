## MODIFIED Requirements

### Requirement: Preview API Endpoint

The system SHALL provide a backend API endpoint for calculating timeline
previews without persisting results to disk.

#### Scenario: Preview endpoint accepts configuration

- **WHEN** client sends POST request to
  `/api/v2/missions/{mission_id}/legs/{leg_id}/timeline/preview`
- **THEN** the system SHALL accept a request body containing transport
  configuration and optional adjusted departure time
- **AND** the `x_transitions` array items SHALL each include `id` (string) and
  `target_satellite_id` (string) fields matching the backend `XTransition` model
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

#### Scenario: Frontend preview request matches backend contract

- **WHEN** the frontend constructs a timeline preview request with X-Band transitions
- **THEN** each x_transition item SHALL include the `id` field from the `XBandTransition` state
- **AND** each x_transition item SHALL include the `target_satellite_id` field (not `to_satellite`)
- **AND** the `TimelinePreviewRequest` TypeScript type SHALL define x_transition items with `id: string` and `target_satellite_id: string` fields
