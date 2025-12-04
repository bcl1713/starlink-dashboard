# Starlink Dashboard - Features Overview

**Related:** [Main README](./README.md) | [Setup Guide](./docs/SETUP-GUIDE.md)

This document provides a comprehensive overview of all features available in the
Starlink Dashboard system.

---

## Core Monitoring Features

### Real-Time Position Tracking

Track Starlink terminal position in real-time with historical trail
visualization.

**Capabilities:**

- Live GPS coordinates (latitude, longitude, altitude)
- Interactive map display in Grafana
- Historical position trail
- Speed and heading indicators
- Position accuracy metrics

**Available In:** Simulation and Live modes

**See:** [Grafana Dashboards](#grafana-dashboards)

### Network Performance Monitoring

Comprehensive network metrics for latency, throughput, and connectivity.

**Metrics Tracked:**

- Latency (ping time in milliseconds)
- Download throughput (Mbps)
- Upload throughput (Mbps)
- Packet loss percentage
- Signal quality indicators
- Obstruction detection

**Available In:** Simulation and Live modes

**See:** [Metrics Documentation](./docs/METRICS.md)

### Historical Data Retention

Store and query up to 1 year of metrics data (configurable).

**Features:**

- Configurable retention period (15d, 30d, 90d, 1y)
- Time-series database (Prometheus)
- Historical trend analysis
- Data export capabilities
- Automatic data cleanup

**Configuration:** `PROMETHEUS_RETENTION` in `.env`

**Storage Requirements:**

- 1 year: ~2.4 GB
- 90 days: ~600 MB
- 30 days: ~200 MB
- 15 days: ~100 MB

**See:** [CLAUDE.md - Storage](./CLAUDE.md#storage--route-management)

---

## Grafana Dashboards

### Starlink Overview Dashboard

Main monitoring dashboard with comprehensive system view.

**URL:** <http://localhost:3000/d/starlink-overview>

**Panels:**

- Live position map with route overlay
- POI ETA table with countdown timers
- Network latency gauge
- Throughput graphs (download/upload)
- Signal quality indicators
- Obstruction percentage

**Use Cases:**

- Real-time flight monitoring
- Quick system health check
- Mission planning overview

### Network Metrics Dashboard

Detailed network performance analysis.

**URL:** <http://localhost:3000/d/starlink-network>

**Panels:**

- Latency trend analysis
- Throughput breakdown by time
- Packet loss visualization
- Signal quality over time
- Connection stability metrics
- Historical comparisons

**Use Cases:**

- Network troubleshooting
- Performance optimization
- SLA monitoring

### Position & Movement Dashboard

Focused location and movement tracking.

**URL:** <http://localhost:3000/d/starlink-position>

**Panels:**

- Interactive map with full history
- Altitude profile chart
- Speed trend graph
- Heading compass
- Distance traveled metrics
- Waypoint progress

**Use Cases:**

- Route tracking
- Movement analysis
- Position verification

**Configuration Guide:** See
[Grafana Setup Documentation](./docs/grafana-setup.md)

---

## Route Management Features

### KML Route Import

Upload and manage flight routes in KML format.

**Capabilities:**

- KML file upload via API
- Automatic waypoint extraction
- Route visualization on map
- Timing metadata parsing
- Multiple route storage
- Route activation/deactivation

**Supported KML Features:**

- LineString (routes)
- Point placemarks (POIs)
- Timing information in waypoints
- Description fields
- Extended data

**APIs:**

- `POST /api/routes/upload` - Upload KML file
- `GET /api/routes` - List all routes
- `GET /api/routes/{id}` - Get route details
- `POST /api/routes/{id}/activate` - Activate route
- `DELETE /api/routes/{id}` - Delete route

**See:** [Route API Documentation](./docs/route-api-endpoints.md)

### Route Visualization

Display active routes on Grafana maps.

**Features:**

- Dark orange route line on map
- Waypoint markers
- POI indicators
- Progress tracking
- Distance remaining
- Current waypoint highlight

**Metrics:**

- `starlink_route_progress_percent` - Overall progress
- `starlink_current_waypoint_index` - Current waypoint
- `starlink_distance_to_waypoint_meters` - Distance remaining

### Route Following (Simulation Mode)

Simulator follows uploaded KML routes with realistic movement.

**Features:**

- Follows route waypoints in order
- Respects timing metadata for speed
- Interpolates between waypoints
- Handles altitude changes
- Loops or stops at end (configurable)

**Configuration:** Automatically enabled when route is activated in simulation
mode

**See:** [Route Timing Guide](./docs/ROUTE-TIMING-GUIDE.md)

---

## Point of Interest (POI) Features

### POI Management

Create, update, and manage points of interest along routes.

**Capabilities:**

- Create POIs with lat/lon coordinates
- Name and describe POIs
- Edit existing POIs
- Delete POIs
- List all POIs with filtering
- POI statistics

**APIs:**

- `POST /api/pois` - Create POI
- `GET /api/pois` - List all POIs
- `GET /api/pois/{id}` - Get POI details
- `PUT /api/pois/{id}` - Update POI
- `DELETE /api/pois/{id}` - Delete POI
- `GET /api/pois/stats` - POI statistics

**See:** [POI API Documentation](./docs/api/poi-endpoints.md)

### Real-Time ETA Calculations

Calculate estimated time of arrival to all POIs.

**Features:**

- Real-time distance calculation
- ETA based on current speed and heading
- ETA mode switching (anticipated vs estimated)
- Multiple POI tracking
- Prometheus metrics export
- Grafana table visualization

**ETA Modes:**

- **Anticipated:** Pre-departure estimates (uses planned route timing)
- **Estimated:** In-flight estimates (uses actual speed)

**Metrics:**

- `starlink_eta_poi_seconds` - Time to POI
- `starlink_distance_to_poi_meters` - Distance to POI
- `starlink_bearing_to_poi_degrees` - Direction to POI

**APIs:**

- `GET /api/pois/etas` - Get all POI ETAs
- `GET /api/pois/{id}/eta` - Get specific POI ETA

**See:** [ETA Endpoints Documentation](./docs/api/eta-endpoints.md)

### POI Visualization

Display POIs on Grafana maps with ETA information.

**Features:**

- POI markers on map
- ETA countdown timers in table
- Distance remaining
- Status indicators (approaching, passed, etc.)
- Color coding by proximity
- Alert rules for approaching POIs

---

## Flight Status & Timing

### Flight Phase Tracking

Track flight phases with automatic transitions.

**Phases:**

- `pre_departure` - Before takeoff
- `in_flight` - Airborne
- `post_arrival` - After landing

**Features:**

- Automatic phase detection (simulation mode)
- Manual phase control (testing endpoints)
- Phase-based ETA mode switching
- Grafana phase indicators
- Prometheus metrics

**APIs:**

- `GET /api/flight-status` - Get current phase
- `POST /api/flight-status/depart` - Trigger departure (testing)
- `POST /api/flight-status/arrive` - Trigger arrival (testing)

**See:**
[Flight Status Guide](./dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md)

### Automatic ETA Mode Switching

ETA calculations adapt based on flight phase.

**Behavior:**

- **Pre-departure:** Uses anticipated mode (planned speeds from KML)
- **In-flight:** Switches to estimated mode (actual GPS speed)
- **Post-arrival:** ETAs frozen or cleared

**Configuration:** Automatic based on flight phase (no manual config needed)

**See:** [Route Timing Guide](./docs/ROUTE-TIMING-GUIDE.md)

---

## Mission Communication Planning

Pre-flight communication degradation prediction for satellite transports.

### Mission Planning Interface

Create and manage missions with transport configurations.

**Features:**

- Define mission routes with waypoints
- Configure satellite transports (X-Band, Ka, Ku/StarShield)
- Set timing windows and operational constraints
- Specify azimuth angle thresholds for degradation
- Mission timeline visualization

**Transports Supported:**

- X-Band (primary command & control)
- Ka-Band (high-bandwidth data)
- Ku-Band/StarShield (Starlink connectivity)

**See:** [Mission Planning Guide](./docs/MISSION-PLANNING-GUIDE.md)

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

**See:** [Mission Communication SOP](./docs/MISSION-COMM-SOP.md)

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
[Monitoring Setup - Mission](./monitoring/README.md#mission-communication-planning)

---

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

**See:** [CLAUDE.md - Configuration](./CLAUDE.md#configuration)

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

**See:** [Configuration Endpoints](./docs/api/configuration-endpoints.md)

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

**See:** [API Reference Index](./docs/API-REFERENCE-INDEX.md)

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

---

## Related Documentation

- [Main README](./README.md) - Quick start and overview
- [Setup Guide](./docs/SETUP-GUIDE.md) - Installation instructions
- [API Reference](./docs/API-REFERENCE-INDEX.md) - Complete API docs
- [Grafana Setup](./docs/grafana-setup.md) - Dashboard configuration
- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues
