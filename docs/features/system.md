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

**See:** [CLAUDE.md - Configuration](../../CLAUDE.md#configuration)

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
