# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Quick Reference

**Project:** Docker-based Starlink terminal monitoring system with real-time
metrics visualization and full simulation mode for offline development.

**Tech Stack:** Python (FastAPI) + Prometheus + Grafana + Docker Compose

**Documentation:**

- `docs/design-document.md` – architecture overview
- `docs/phased-development-plan.md` – implementation roadmap
- `docs/ROUTE-TIMING-GUIDE.md` – route timing feature + ETA modes
- `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` – flight phase
  manager, overrides, dashboards

## Development Commands

### Docker Compose

```bash
docker compose up -d           # Start all services
docker compose down            # Stop all services
docker compose logs -f         # Stream logs
docker compose restart         # Restart services
docker compose build           # Build images (use --no-cache to force rebuild)
```

### ⚠️ CRITICAL: Backend Python Code Changes Workflow

**YOU MUST FOLLOW THIS EXACT SEQUENCE EVERY TIME YOU MODIFY ANY .py FILE IN
backend/**

**FAILURE TO DO THIS WILL RESULT IN RUNNING OLD CODE AND WASTING HOURS
DEBUGGING**

```bash
# 1. Make your code changes (edit *.py files)

# 2. IMMEDIATELY RUN THIS (no exceptions, no shortcuts):
docker compose down && docker compose build --no-cache && docker compose up -d

# 3. WAIT for services to be healthy (check with):
docker compose ps    # All containers should show "healthy"

# 4. VERIFY your changes took effect:
curl <http://localhost:8000/health>
curl <http://localhost:8000/docs>

# 5. ONLY AFTER VERIFICATION, commit changes:
git add .
git commit -m "Your message"
```

**WHY THIS IS NON-NEGOTIABLE:**

- ❌ `docker compose up` alone WILL NOT WORK - it serves cached code
- ❌ `docker compose restart` WILL NOT WORK - containers are still using old
  images
- ❌ `docker compose build` (without `--no-cache`) WILL NOT WORK - layers are
  cached
- ✅ ONLY THIS WORKS:
  `docker compose down && docker compose build --no-cache && docker compose up -d`

**WHAT HAPPENS IF YOU SKIP THIS:**

- Backend runs old Python code while you see your edits in files
- Tests fail mysteriously (old code vs new tests)
- Changes appear to have no effect
- Hours wasted debugging code that isn't even running
- **YOU WILL GET CONFUSED AND FRUSTRATED**

**THIS IS NOT OPTIONAL. THIS IS REQUIRED EVERY SINGLE TIME.**

### Access Points

- **Grafana:** <<http://localhost:3000>> (default: admin/admin)
- **Prometheus:** <<http://localhost:9090>>
- **Backend health:** <<http://localhost:8000/health>>
- **Prometheus metrics:** <<http://localhost:8000/metrics>>

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
PROMETHEUS_RETENTION=1y           # Metrics retention period (1 year, ~2.4 GB storage)
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

**Connection Behavior:** If the system fails to connect to the dish on startup,
it initializes successfully but begins serving without metrics. The service
remains in live mode and attempts to reconnect on each update cycle. This allows
the system to continue running and be ready when the dish becomes available.
Check the `/health` endpoint to see current connection status.

**Testing Connection:**

```bash
# Once running, check health endpoint to see actual mode and connection status
curl <http://localhost:8000/health>

# Example response (connected):
# {
#   "status": "ok",
#   "mode": "live",
#   "message": "Live mode: connected to dish",
#   "dish_connected": true,
#   ...
# }

# Example response (disconnected but waiting):
# {
#   "status": "ok",
#   "mode": "live",
#   "message": "Live mode: waiting for dish connection",
#   "dish_connected": false,
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
- POI/ETA:
  `starlink_eta_poi_seconds{name="...",eta_type="anticipated|estimated"}`,
  `starlink_distance_to_poi_meters{...,eta_type="..."}`

### Flight Status & ETA Modes

- Flight phases: `pre_departure`, `in_flight`, `post_arrival`
- ETA modes auto-switch between `anticipated` (planned timeline pre-departure)
  and `estimated` (live performance once airborne)
- Relevant APIs:
  - `/api/flight-status` – snapshot with phase, mode, countdown, route context
  - `/api/pois/etas` – returns `eta_type`, `flight_phase`, `is_pre_departure`
    per POI
  - `/api/routes` & `/api/routes/{id}` – include `flight_phase`, `eta_mode`,
    `has_timing_data`
- Prometheus: `starlink_flight_phase`, `starlink_eta_mode`,
  `starlink_time_until_departure_seconds`
- For manual testing use `/api/flight-status/depart` and
  `/api/flight-status/arrive`; see
  `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` for full workflow and
  troubleshooting.

## Storage Requirements

With the default 1-year retention period, Prometheus will store approximately
**2.4 GB** of telemetry data.

**Storage Calculation:**

- **Number of unique metrics:** 45 (collected from live backend)
- **Scrape interval:** 1 second
- **Retention period:** 1 year (31,536,000 seconds)
- **Estimated size per sample:** ~1.5 bytes (with compression)
- **Compression overhead:** ~1.2x

**Formula:**

```text
Storage_GB = (45 metrics × 31,536,000 seconds × 1.5 bytes × 1.2 overhead) / 1,073,741,824
Storage_GB ≈ 2.4 GB
```

**To adjust retention**, modify `PROMETHEUS_RETENTION` in `.env`:

- `1y` - 1 year (~2.4 GB) - default for long-term analysis
- `90d` - 90 days (~600 MB)
- `30d` - 30 days (~200 MB)
- `15d` - 15 days (~100 MB)

## Route Management

### Quick Start

**Access Route Management UI:**

```bash
# Web UI for managing routes
<http://localhost:8000/ui/routes>

# API documentation and testing
<http://localhost:8000/docs>
```

### Common Operations

**Upload a KML route:**

```bash
curl -X POST \
  -F "file=@myroute.kml" \
  <http://localhost:8000/api/routes/upload>
```

**List all routes:**

```bash
curl <http://localhost:8000/api/routes>
```

**Get route details:**

```bash
curl <http://localhost:8000/api/routes/{route_id}>
```

**Activate a route (simulation will follow it):**

```bash
curl -X POST <http://localhost:8000/api/routes/{route_id}/activate>
```

**Deactivate all routes:**

```bash
curl -X POST <http://localhost:8000/api/routes/deactivate>
```

**Delete a route:**

```bash
curl -X DELETE <http://localhost:8000/api/routes/{route_id}>
```

**Download original KML file:**

```bash
curl -O <http://localhost:8000/api/routes/{route_id}/download>
```

### Route Features

- **KML Import:** Upload KML files with LineString and/or Point geometries
- **Route Visualization:** Active route displays on Grafana map in dark orange
- **Simulation Following:** In simulation mode, position automatically follows
  active route
- **Progress Metrics:** Track progress along route via Prometheus metrics
  - `starlink_route_progress_percent` - Progress from 0-100%
  - `starlink_current_waypoint_index` - Current waypoint number
- **POI Integration:** Embedded Point placemarks can be imported as POIs
- **Route Switching:** Only one route active at a time; activating new route
  deactivates previous

### Sample Routes

Example KML files for testing are available in `/data/sample_routes/`:

- `simple-circular.kml` - Small route (14 waypoints, ~50 km)
- `cross-country.kml` - Large route (100+ waypoints, ~3944 km)
- `route-with-pois.kml` - Route with embedded waypoints (24 points + 5 POIs)
- `invalid-malformed.kml` - Intentionally malformed (for error handling testing)

See `/data/sample_routes/README.md` for detailed descriptions.

### KML File Format

**Minimum required structure:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="<http://www.opengis.net/kml/2.2">>
  <Document>
    <Placemark>
      <LineString>
        <coordinates>
          longitude,latitude,altitude
          longitude,latitude,altitude
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

**Coordinate format:**

- Longitude: -180 to 180 (negative = West)
- Latitude: -90 to 90 (negative = South)
- Altitude: Meters above sea level

**Optional features:**

- Multiple Placemarks (multiple route segments)
- Point geometry for waypoints (will be imported as POIs)
- Route names and descriptions in `name` and `<description>` tags

### Route Storage

Routes are stored as KML files in `/data/routes/` directory and watched for
changes:

- Uploading via API saves to this directory
- Routes manually placed here are auto-discovered
- Deleting via API removes the KML file
- File changes detected automatically (watchdog)

### Monitoring Route Following

**In Grafana:**

1. Open <<http://localhost:3000/d/starlink/fullscreen-overview>>
2. Activate a route
3. Route appears as dark orange line on map
4. With simulation mode active, position follows the route

**Via Prometheus:**

```bash
# Check route progress
curl '<http://localhost:9090/api/v1/query?query=starlink_route_progress_percent'>

# Check waypoint index
curl '<http://localhost:9090/api/v1/query?query=starlink_current_waypoint_index'>
```

### Troubleshooting

**Route won't upload:**

- Verify file is valid KML (must have `.kml` extension)
- Check file contains LineString or Point geometries
- Ensure XML syntax is correct

**Route not showing on map:**

- Activate route via UI or API
- Verify Grafana dashboard is loaded
- Check browser console for errors

**Position not following route:**

- Verify `STARLINK_MODE=simulation` in `.env`
- Check route is activated
- Monitor logs: `docker logs -f starlink-location | grep route`

**POIs not importing:**

- Route must have Point placemarks to import
- Use `import_pois=true` flag if available
- Check backend logs for parsing errors

---

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

## File Naming Conventions

When creating documentation or task management files, follow these naming
standards:

- **Status/session files:** ALL CAPS with hyphens (SESSION-NOTES.md)
- **Task planning files:** kebab-case (poi-management-plan.md,
  feature-context.md)
- **Never use underscores** for multi-word filenames (use hyphens instead)

See `.claude/NAMING-CONVENTIONS.md` for complete guidelines.

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

## Active Technologies

- Python 3.13 (backend), TypeScript/React (frontend), Markdown (docs) + FastAPI
  (backend), React/Vite (frontend), Black, Prettier, ESLint, markdownlint-cli2
  (001-codebase-cleanup)
- N/A (refactoring existing code, no new data storage) (001-codebase-cleanup)

## Recent Changes

- 001-codebase-cleanup: Added Python 3.13 (backend), TypeScript/React
  (frontend), Markdown (docs) + FastAPI (backend), React/Vite (frontend), Black,
  Prettier, ESLint, markdownlint-cli2
- docker builds should always be delegated to a sub agent. they use a huge
  amount of context
