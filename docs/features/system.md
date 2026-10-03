# System Configuration & Simulation

## Configuration & Environment

### Environment Variables

All system configuration via `.env` file.

**Core Settings:**

- `STARLINK_MODE` - Operating mode (simulation/live)
- `STARLINK_DISH_HOST` - Terminal IP (live mode)
- `STARLINK_DISH_PORT` - Terminal gRPC port (live mode)
- `PROMETHEUS_RETENTION` - Metrics retention period
- `GRAFANA_ADMIN_PASSWORD` - Grafana password

**Port Configuration:**

- `STARLINK_LOCATION_PORT` - Backend port (default: 8000)
- `PROMETHEUS_PORT` - Prometheus port (default: 9090)
- `GRAFANA_PORT` - Grafana port (default: 3000)

**See:**
[Environment Variables](../setup/configuration/environment-variables.md)

### Overview settings and diagnostics

The **Configuration** page contains **Overview history window** (5, 15, 30 or 60
minutes, preserving a saved custom duration). The saved window applies to the
aircraft trail and all five network graphs. It does not change the fixed
five-minute rolling-statistics window or polling cadence. Read and save failures
are reported separately; an unsuccessful save can be retried.

**Overview map diagnostics** retains satellite counts, selected planned ID,
status/history availability, ground entry point and configured GEO look angles.
Satellite placement and link geometry are planning analysis, not measured
connectivity. The supported planned-link warning derives from the existing
configured forbidden relative-azimuth rule; it does not establish a connection
or introduce a new alarm. Retained coordinates and geometry can be last known.
Satellite catalog editing remains in Satellite Manager.

### Shared data link visibility

**Overview data links** contains independent **Starshield data link** and
**X-band data link** switches. Both default to `true`. They use
`GET /api/overview-links/settings` and partial
`PUT /api/overview-links/settings` updates with strict boolean fields
`starshield_link_enabled` and `x_band_link_enabled`. A save returns the full pair;
changing one field preserves the other, including concurrent disjoint edits.

Settings persist atomically at `data/settings/overview-links.json`, survive
backend restarts and synchronize viewers through the shared query (five-second
visible polling and focus refresh). They are installation settings, not browser
storage. Before a confirmed read, both switches are disabled and both links are
hidden. Read/save failures retain the last confirmed pair and show error feedback;
saves do not optimistically change visibility.

Starshield visualizes measured aircraft–PoP traffic. X-band activity is a local
illustration; neither switch changes telemetry collection, metric history,
configured selection, warning rules or operational status. See
[Overview data links](overview.md#independent-data-links) for rendering behavior.

### Configuration API

Runtime configuration management via REST API.

**Endpoints:**

- `GET /api/config` - Get current configuration
- `PUT /api/config` - Update configuration
- `POST /api/config/reload` - Reload from file

**Configurable Settings:**

- Operating mode
- Dish connection details
- Metrics collection intervals
- Feature flags
- Logging levels

**See:** [Configuration Endpoints](../api/endpoints/configuration.md)

---

## REST API

### Interactive API Documentation

Auto-generated API documentation with testing interface.

**URL:** <http://localhost:8000/docs>

**Features:**

- Complete endpoint listing
- Request/response schemas
- Try-it-out functionality
- Authentication testing
- Example payloads
- Error code reference

**Alternative:** ReDoc at <http://localhost:8000/redoc>

### API Categories

**Core Endpoints:**

- Health and status
- System metrics
- Configuration

**Feature Endpoints:**

- POI management
- Route management
- ETA calculations
- Flight status
- Mission planning

**See:** [API Reference Index](../api/README.md)

---

## Simulation Mode Features

### Realistic Telemetry Generation

Generate realistic Starlink metrics without hardware.

**Simulated Data:**

- GPS position (follows routes or circular path)
- Network latency (20-80ms with realistic variance)
- Throughput (100-200 Mbps with patterns)
- Signal quality metrics
- Obstruction simulation
- Speed and heading

**Realism Features:**

- Time-of-day variations
- Weather patterns (optional)
- Realistic noise and jitter
- Connection stability simulation

### Route Following

Simulator automatically follows uploaded KML routes.

**Behavior:**

- Reads waypoint coordinates from KML
- Extracts timing metadata (if present)
- Calculates speeds between waypoints
- Interpolates smooth movement
- Updates position at configured interval

**Configuration:**

- Upload KML via `/api/routes/upload`
- Activate route via `/api/routes/{id}/activate`
- Simulation starts following immediately
