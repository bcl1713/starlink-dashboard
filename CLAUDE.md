# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Quick Reference

**Project:** Docker-based Starlink terminal monitoring system with real-time
metrics visualization and full simulation mode for offline development.

**Tech Stack:** Python (FastAPI) + Prometheus + Grafana + Docker Compose

**Documentation:** See `docs/design-document.md` for architecture and
`docs/phased-development-plan.md` for implementation phases.

## Development Commands

### Docker Compose

```bash
docker compose up -d           # Start all services
docker compose down            # Stop all services
docker compose logs -f         # Stream logs
docker compose restart         # Restart services
docker compose build           # Build images (use --no-cache to force rebuild)
```

### Access Points

- **Grafana:** <http://localhost:3000> (default: admin/admin)
- **Prometheus:** <http://localhost:9090>
- **Backend health:** <http://localhost:8000/health>
- **Prometheus metrics:** <http://localhost:8000/metrics>

## Configuration

Environment variables in `.env`:

```bash
# Operating mode: Two approaches (STARLINK_MODE is recommended)
# Approach 1: STARLINK_MODE (explicit, recommended)
STARLINK_MODE=simulation          # or 'live' for real Starlink terminal

# Approach 2: SIMULATION_MODE (backward compatible)
# SIMULATION_MODE=true             # Equivalent to STARLINK_MODE=simulation
# SIMULATION_MODE=false            # Equivalent to STARLINK_MODE=live
# (If both are set, STARLINK_MODE takes precedence)

# Starlink dish network configuration (for live mode)
STARLINK_DISH_HOST=192.168.100.1  # IP address of Starlink dish
STARLINK_DISH_PORT=9200           # gRPC port for Starlink communication

# Other settings
PROMETHEUS_RETENTION=15d          # Metrics retention period
GRAFANA_ADMIN_PASSWORD=admin      # Grafana admin password (change in production!)
```

## Key Implementation Paths

**Backend service location:** `backend/starlink-location/`

**Required Docker configs:** `monitoring/prometheus/` and `monitoring/grafana/`

**Data volumes:** `/data/routes/` for KML files, `/data/sim_routes/` for
simulator routes

## Operating Modes

### Simulation Mode (Default)

Default mode for development. Generates realistic Starlink telemetry (position,
speed, latency, throughput, obstructions).

- Set `STARLINK_MODE=simulation` in `.env`
- No hardware required
- Useful for UI development and testing
- Refer to `docs/design-document.md` section 3 for detailed behavior

### Live Mode

Connect to a real Starlink terminal to get actual telemetry data.

**Requirements:**

- Starlink terminal on local network at `192.168.100.1` (default) or configured
  IP
- Network access from Docker container to terminal
- Set `STARLINK_MODE=live` in `.env`

**Configuration:**

```bash
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1  # Your terminal's IP address
STARLINK_DISH_PORT=9200           # Standard gRPC port
```

**Docker Networking:**

- **Bridge mode (default, cross-platform):** Uses `extra_hosts` to route
  dish.starlink hostname
- **Host mode (Linux only):** Uncomment `network_mode: host` in
  docker-compose.yml for direct access

**Automatic Fallback:** If the system fails to connect to the dish on startup,
it automatically falls back to simulation mode. This allows the system to
continue running even if hardware is temporarily unavailable. Check logs for
fallback status.

**Testing Connection:**

```bash
# Once running, check health endpoint to see actual mode
curl http://localhost:8000/health

# Should show:
# {
#   "mode": "live",
#   "mode_description": "Real Starlink terminal data",
#   ...
# }
```

## Core Metrics

The backend exposes Prometheus metrics including:

- Position: `starlink_dish_latitude_degrees`, `starlink_dish_longitude_degrees`,
  `starlink_dish_altitude_meters`
- Network: `starlink_network_latency_ms`,
  `starlink_network_throughput_down_mbps`, `starlink_network_throughput_up_mbps`
- Status: `starlink_dish_obstruction_percent`, `starlink_dish_speed_knots`,
  `starlink_dish_heading_degrees`
- POI/ETA: `starlink_eta_poi_seconds{name="..."}`,
  `starlink_distance_to_poi_meters{name="..."}`

## Dashboard Features

### Position History Route (Fullscreen Overview)

The Fullscreen Overview dashboard's map panel displays both current position and
historical route.

**Features:**

- Route shows position history over the selected dashboard time range
- Uses 1-second sampling intervals matching other overview panels
- Simple blue route line (future: metric-based coloring)
- Current position marker (green plane) displays on top of route
- Data gaps interpolated with straight lines

**Implementation:**

- Configured in
  `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
- Uses Grafana Geomap Route layer
- Queries Prometheus for historical lat/lon time series (queries E & F)

**Known Limitations:**

- No interactive tooltips in initial version (planned future enhancement)
- Single solid color (no gradient or metric-based coloring yet)
- All points connected as continuous route (no segment breaks)

## Code Formatting

Use Prettier with settings in `.prettierrc` (print width: 80, prose wrap:
always, auto line endings).

## Project Status

Currently in **Phase 0** (planning/documentation complete). Follow the phased
development plan in `docs/phased-development-plan.md` for implementation order.

## Architecture Overview

Refer to section 2 in `docs/design-document.md` for the full system architecture
diagram and component descriptions.

## Testing

To be implemented during development phases. Use pytest for Python backend tests
once available.

## Additional Context

- **Live mode:** Requires network access to Starlink dish at
  `192.168.100.1:9200` (see section 7 of design document)
- **KML/POI system:** Detailed in section 5 of design document
- **API endpoints:** Section 4 of design document lists all backend endpoints
- **Grafana integration:** See Phase 5 of development plan for dashboard
  requirements
