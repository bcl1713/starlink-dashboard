## ADDED Requirements

### Requirement: API returns GPS configuration status
The system SHALL provide a GET endpoint at `/api/v2/gps/config` that returns the current GPS configuration state from the Starlink dish, including whether GPS is enabled, whether GPS is ready, and the number of satellites in view.

#### Scenario: Successful GPS status retrieval
- **WHEN** client sends GET request to `/api/v2/gps/config`
- **THEN** system returns JSON with `enabled` (boolean), `ready` (boolean), and `satellites` (integer) fields

#### Scenario: Dish unavailable
- **WHEN** client sends GET request to `/api/v2/gps/config` and the Starlink dish is unreachable
- **THEN** system returns HTTP 503 with error message indicating dish connectivity issue

### Requirement: API allows GPS configuration update
The system SHALL provide a POST endpoint at `/api/v2/gps/config` that sets whether the Starlink dish uses GPS for position determination.

#### Scenario: Enable GPS successfully
- **WHEN** client sends POST to `/api/v2/gps/config` with `{"enabled": true}`
- **THEN** system enables GPS on the dish and returns updated configuration with `enabled: true`

#### Scenario: Disable GPS successfully
- **WHEN** client sends POST to `/api/v2/gps/config` with `{"enabled": false}`
- **THEN** system disables GPS on the dish and returns updated configuration with `enabled: false`

#### Scenario: Permission denied by dish
- **WHEN** client sends POST to `/api/v2/gps/config` and the dish denies GPS configuration changes
- **THEN** system returns HTTP 403 with error message indicating permission was denied

#### Scenario: Invalid request body
- **WHEN** client sends POST to `/api/v2/gps/config` without `enabled` field or with invalid type
- **THEN** system returns HTTP 422 with validation error details

### Requirement: Frontend displays GPS control card
The system SHALL display a GPS control card component in the dashboard that shows current GPS status and provides a toggle to enable/disable GPS.

#### Scenario: Card displays current GPS state
- **WHEN** user views the GPS control card
- **THEN** card displays GPS enabled/disabled state, GPS readiness indicator, and satellite count

#### Scenario: User enables GPS via toggle
- **WHEN** user clicks toggle to enable GPS while GPS is disabled
- **THEN** system sends POST request, shows loading state, and updates display on success

#### Scenario: User disables GPS via toggle
- **WHEN** user clicks toggle to disable GPS while GPS is enabled
- **THEN** system sends POST request, shows loading state, and updates display on success

### Requirement: Frontend handles GPS control errors gracefully
The system SHALL display appropriate error messages when GPS control operations fail, and SHALL disable the toggle when the dish is unavailable or permission is denied.

#### Scenario: Display error on permission denied
- **WHEN** user attempts to toggle GPS and receives permission denied error
- **THEN** system displays error message explaining GPS control is not permitted on this dish

#### Scenario: Display error on dish unavailable
- **WHEN** user attempts to toggle GPS and the dish is unreachable
- **THEN** system displays error message and disables the toggle until connectivity is restored

#### Scenario: Toggle disabled during request
- **WHEN** a GPS configuration request is in progress
- **THEN** toggle control is disabled and shows loading indicator
