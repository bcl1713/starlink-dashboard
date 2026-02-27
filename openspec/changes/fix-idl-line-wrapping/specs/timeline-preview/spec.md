## MODIFIED Requirements

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

#### Scenario: IDL-crossing route renders without wrapping

- **WHEN** route crosses the International Date Line (longitude ±180°)
- **AND** preview timeline is rendered as color-coded segments
- **THEN** the system SHALL normalize sample coordinates to the same coordinate space used by the base route layer
- **AND** color-coded polylines SHALL take the short path across the IDL
- **AND** color-coded polylines SHALL NOT wrap around the globe through 0° longitude
- **AND** color-coded segments SHALL align visually with the base blue route line
