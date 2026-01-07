# Mission Communication Planning

Pre-flight communication degradation prediction for satellite transports.

## Mission Planning Features

### Mission Planning Interface

Create and manage missions with transport configurations.

**Features:**

- Define mission routes with waypoints
- Configure satellite transports (X-Band, Ka, Ku/StarShield)
- Set timing windows and operational constraints
  - All times use 24-hour format (HH:mm) for aviation/maritime consistency
  - Times are entered and displayed in UTC timezone
- Specify azimuth angle thresholds for degradation
- Mission timeline visualization

**Transports Supported:**

- X-Band (primary command & control)
- Ka-Band (high-bandwidth data)
- Ku-Band/StarShield (Starlink connectivity)

**See:** [Mission Planning Guide](../missions/mission-planning-guide.md)

### Satellite Geometry Engine

Analyzes 3D satellite positions and communication viability.

**Capabilities:**

- Real-time azimuth angle calculation
- Elevation constraint checking
- Multi-satellite tracking
- Degradation window prediction
- Communication status (nominal/degraded/lost)

**Output:**

- Timeline of degradation windows by flight phase
- Affected transports per window
- Duration and severity estimates
- Crew briefing summaries

### Multi-Format Exports

Generate mission briefing documents in multiple formats.

**Export Formats:**

- **PDF:** Crew briefing with charts and timelines
- **CSV:** Log format for post-flight analysis
- **XLSX:** Excel format with multiple sheets

**Contents:**

- Mission summary and timing
- Transport configuration
- Degradation window details
- Satellite geometry data
- Recommendations and notes

**APIs:**

- `POST /api/missions/{id}/export/pdf`
- `POST /api/missions/{id}/export/csv`
- `POST /api/missions/{id}/export/xlsx`

**See:** [Mission Communication SOP](../missions/mission-comm-sop.md)

### Grafana Mission Visualization

Real-time mission timeline and alert integration.

**Features:**

- Mission timeline panel
- Degradation window overlays
- Satellite coverage indicators
- Alert rules for approaching windows
- Transport status gauges

**Dashboards:**

- Mission Overview (timeline and status)
- Transport Status (per-transport details)
- Satellite Geometry (azimuth/elevation charts)

**See:**
[Monitoring Setup - Mission](../../monitoring/README.md#mission-communication-planning)
