# CLAUDE.md

Guidance for Claude Code when working with this repository.

**Project:** Docker-based Starlink terminal monitoring system with real-time
metrics visualization and simulation mode.

**Tech Stack:** Python 3.13 (FastAPI) + Prometheus + Grafana + Docker Compose;
TypeScript/React frontend; Markdown documentation.

**Key Docs:**

- `docs/design-document.md` – architecture
- `docs/phased-development-plan.md` – development roadmap
- `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` – flight phases & ETA
  modes

## ⚠️ Backend Python Code Changes (CRITICAL)

**REQUIRED sequence for ANY .py file changes:**

```bash
docker compose down && docker compose build --no-cache && \
  docker compose up -d && docker compose ps
curl http://localhost:8000/health  # Verify changes took effect
```

**Why:** `docker compose up` alone serves cached code. Only the sequence above
rebuilds images without layer caching.

**Docker commands:** `up -d`, `down`, `logs -f`, `restart`, `ps`

## Access Points & Configuration

**Service URLs:**

- Grafana: `http://localhost:3000` (admin/admin)
- Prometheus: `http://localhost:9090`
- Backend: `http://localhost:8000/health` or `/docs`

**Environment variables** (`.env`):

- `STARLINK_MODE=simulation` (or `live`)
- `STARLINK_DISH_HOST=192.168.100.1`
- `STARLINK_DISH_PORT=9200`
- `PROMETHEUS_RETENTION=1y` (~2.4 GB)
- `GRAFANA_ADMIN_PASSWORD=admin`

**Module Paths (Refactored - Phase 001-codebase-cleanup):**

- Backend: `backend/starlink-location/` (main service)
- API Layer:
  - Routes: `app/api/routes/` (management, upload, download, stats, eta,
    timing, cache)
  - POIs: `app/api/pois/` (crud, etas, stats, helpers)
  - UI: `app/api/ui/` (routes, templates)
- Mission Layer:
  - Routes: `app/mission/routes/` (missions, legs, waypoints, operations)
  - Timeline: `app/mission/timeline_builder/` (calculator, state,
    validators)
  - Exporter: `app/mission/exporter/` (formatting, excel_utils,
    transport_utils)
  - Package: `app/mission/package/` (mission export/import)
- Services:
  - KML Parser: `app/services/kml/` (parser, geometry, validators)
  - ETA: `app/services/eta/` (core calculations, bearing, distance)
  - Route ETA: `app/services/route_eta/` (route-specific timing)
  - POI Manager: `app/services/poi_manager.py` (consolidated)
  - Flight State: `app/services/flight_state_manager.py` (flight tracking)
- Core: `app/core/metrics/` (Prometheus metrics)
- Config: `monitoring/prometheus/`, `monitoring/grafana/`
- Data: `/data/routes/` (KML files), `/data/sim_routes/` (simulator)

## Operating Modes

**Simulation Mode (default):** Set `STARLINK_MODE=simulation`. Generates
realistic Starlink telemetry (position, speed, latency, throughput,
obstructions). No hardware required.

**Live Mode:** Set `STARLINK_MODE=live`. Connects to real terminal at
`STARLINK_DISH_HOST:STARLINK_DISH_PORT`. If dish unavailable on startup, service
initializes without metrics and auto-reconnects on each cycle. Check
`http://localhost:8000/health` for connection status.

## Core Metrics & APIs

**Prometheus Metrics:** Position (`starlink_dish_latitude_degrees`, longitude,
altitude), Network (latency_ms, throughput_down/up_mbps), Status
(obstruction_percent, speed_knots, heading_degrees), POI/ETA (eta_poi_seconds,
distance_to_poi_meters).

**Flight Status & ETA:**

- Phases: `pre_departure`, `in_flight`, `post_arrival`
- ETA modes auto-switch: `anticipated` (pre-flight) → `estimated` (airborne)
- APIs: `/api/flight-status`, `/api/pois/etas`, `/api/routes/{id}`
- Testing: `/api/flight-status/depart` and `/arrive` endpoints
- See `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` for details

## Storage & Route Management

**Prometheus Storage:** Default 1-year retention (~2.4 GB). Adjust
`PROMETHEUS_RETENTION` in `.env`: `1y` (2.4 GB), `90d` (600 MB), `30d` (200 MB),
`15d` (100 MB).

**Route APIs:**

- Upload KML: `POST /api/routes/upload`
- List: `GET /api/routes`
- Get details: `GET /api/routes/{route_id}`
- Activate: `POST /api/routes/{route_id}/activate`
- Deactivate: `POST /api/routes/deactivate`
- Delete: `DELETE /api/routes/{route_id}`
- Download: `GET /api/routes/{route_id}/download`

**Route Management UI:** `http://localhost:8000/ui/routes`

**Sample Routes:** See `/data/sample_routes/` (simple-circular.kml,
cross-country.kml, route-with-pois.kml)

## KML Format & Route Features

**KML Format:** Coordinate order: `longitude,latitude,altitude`. Longitude: -180
to 180 (negative = West), Latitude: -90 to 90 (negative = South). Supports
LineString (routes) and Point (POIs).

**Route Features:** KML import with auto-discovery, Grafana visualization (dark
orange), simulation following, progress metrics
(`starlink_route_progress_percent`, `starlink_current_waypoint_index`), POI
import from Point placemarks.

**Monitoring:** View on Grafana dashboard (`http://localhost:3000/d/starlink`)
or query Prometheus metrics.

## Code Quality Standards

**Formatting:** Prettier (80 char width, prose wrap always, auto line endings).
Python: Black + ruff. Markdown: markdownlint-cli2.

**Naming:** Status/session files → ALL CAPS (SESSION-NOTES.md). Task files →
kebab-case (poi-management-plan.md). No underscores. See
`.claude/NAMING-CONVENTIONS.md`.

**File Size:** Target 300 lines max per file (FR-004 justification required if
exceeded). Phase 001-codebase-cleanup: 88-92% backend compliance (23-24 of 26),
100% frontend (3/3), 100% documentation refactored into subdirectories.

**Type Safety:** Python (mypy strict), TypeScript (strict mode). All refactored
code fully typed and documented.

## Documentation & Architecture

Refer to:

- `docs/design-document.md` – full architecture (sections 1-7)
- `docs/phased-development-plan.md` – implementation roadmap
- `dev/completed/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` – testing flight modes

**Docker Builds:** Delegate to sub-agents (expensive context).
