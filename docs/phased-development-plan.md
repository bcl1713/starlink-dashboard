# Phased Development Plan: Mobile Starlink Monitoring Webapp (with Simulation Mode)

**Status:** Phase 0 Complete + Multiple Major Features Delivered

This plan structures **incremental, LLM-assisted development**, ensuring each
phase is implemented, tested, and validated before proceeding. Each phase
produces working code and Docker configurations, building toward a full,
production-ready stack.

**Project Timeline:** Foundation phase complete (2025-10-29), followed by 24
sessions of intensive feature development (2025-10-30 to 2025-11-04)

---

## Phase 1: Project Scaffolding

**Goal:** Establish the foundation for all components.

**Tasks:**

1. Initialize a monorepo structure:

```text
starlink-monitor/
├── backend/
│   └── starlink-location/
├── monitoring/
│   ├── prometheus/
│   └── grafana/
├── docker-compose.yml
└── .env
```

1. Create the base `docker-compose.yml` with stub services:
   - `starlink-location` (placeholder container)
   - `prometheus`
   - `grafana`
2. Add shared Docker network and persistent volumes.
3. Set up `.env` with default values:

   ```bash
   SIMULATION_MODE=true
   PROMETHEUS_RETENTION=15d
   GRAFANA_ADMIN_PASSWORD=admin
   ```

**Deliverables:**

- Working `docker-compose up` with all containers starting (Grafana reachable on
  port 3000).
- Stub `/metrics` endpoint returning “OK”.

---

## Phase 2: Starlink Location Service (Backend Core)

**Goal:** Build the core Python FastAPI service with Prometheus metrics
endpoint.

**Tasks:**

1. Scaffold a FastAPI app in `backend/starlink-location/app.py`.
2. Implement `/health` and `/metrics` endpoints.
3. Add Prometheus client integration:

   ```python
   from prometheus_client import Gauge, generate_latest
   ```

4. Create placeholder gauges for:
   - `starlink_dish_latitude_degrees`
   - `starlink_dish_longitude_degrees`
   - `starlink_dish_altitude_meters`
5. Add Dockerfile for `starlink-location` and rebuild the stack.

**Deliverables:**

- `/metrics` exposes Prometheus-compatible data.
- Prometheus successfully scrapes the service.

---

## Phase 3: Simulation Engine

**Goal:** Add a simulation subsystem to emulate Starlink telemetry.

**Tasks:**

1. Add `simulator.py` module to backend.
2. Implement data generation functions:
   - Circular path coordinate generator
   - Speed, latency, and throughput oscillators
3. Add `SIMULATION_MODE` flag.
4. Create async background loop updating gauges every 3–5 seconds.
5. Validate real-time updates in Prometheus and Grafana.

**Deliverables:**

- Realistic simulated data visible in Prometheus.
- Grafana dashboard begins updating live without a dish.

---

## Phase 4: KML Route Loader & POI System

**Goal:** Add geographic realism and ETA logic.

**Tasks:**

1. Implement `/data/routes/` directory and file watcher.
2. Parse KML → GeoJSON conversion (use `fastkml` or `simplekml`).
3. Serve `/route.geojson` endpoint.
4. Add static POI definitions (`pois.json`).
5. Calculate ETA and distance using Haversine formula.
6. Expose:
   - `starlink_eta_poi_seconds{name="XYZ"}`
   - `starlink_distance_to_poi_meters{name="XYZ"}`

**Deliverables:**

- Route visible in Grafana map.
- ETA values updating in real time.

---

## Phase 5: Grafana Integration and Dashboards

**Goal:** Build the visualization layer.

**Tasks:**

1. Configure Prometheus datasource in Grafana.
2. Install required plugins:
   - `pr0ps-trackmap-panel`
   - (Optional) `grafana-worldmap-panel`
3. Create dashboard with:
   - Map panel (real-time track)
   - Throughput, latency, and outage charts
   - POI/ETA table
   - “Simulation Mode Active” banner
4. Save dashboard JSON to `monitoring/grafana/provisioning/dashboards/`.

**Deliverables:**

- Fully functional Grafana dashboard displaying simulated data.
- Ready for live integration.

---

## Phase 6: Control and API Extensions

**Goal:** Add Starlink control endpoints for live mode.

**Tasks:**

1. Implement gRPC calls using `starlink-client`:
   - `reboot_dish()`
   - `stow_dish(enable=True/False)`
2. Add REST API routes:
   - `POST /api/dish/reboot`
   - `POST /api/dish/stow`
3. Add `/api/sim/*` routes for demo control:
   - Start, stop, reset, set route.
4. Integrate optional Grafana “Control” panel (iframe buttons).

**Deliverables:**

- Functional REST API for control.
- Optional UI for triggering commands in Grafana.

---

## Phase 7: Live Mode Integration

**Goal:** Enable full connection to a real Starlink terminal.

**Tasks:**

1. Detect network presence of `192.168.100.1:9200`.
2. Switch automatically between SIM and LIVE.
3. Poll gRPC metrics:
   - Location
   - Network health
   - Uptime
4. Fall back to simulation if dish unreachable.

**Deliverables:**

- Hybrid mode working.
- Identical Grafana experience for live or simulated operation.

---

## Phase 8: Packaging and Distribution

**Goal:** Make it easy to deploy anywhere.

**Tasks:**

1. Add Makefile with build shortcuts.
2. Add prebuilt dashboard JSON and sample `.env.example`.
3. Include GitHub Actions CI/CD for image building.
4. Write full README with setup, config, and usage.
5. Optional: publish images to GHCR.

**Deliverables:**

- One-command deployment (`docker compose up -d`).
- Offline-ready simulation out of the box.

---

## Phase 9: Optional Enhancements

- Add WebSocket stream for live map updates.
- Integrate weather overlays (OpenWeatherMap tiles).
- Add alert rules for high latency / loss.
- Enable persistent route recording for post-flight playback.
- Support multiple simultaneous Starlink units.

---

## Phase 10: Final QA and Demo

**Goal:** Verify all functionality end-to-end.

**Checklist:**

- Simulation and live mode switching
- Prometheus data retention and integrity
- Grafana panels refresh properly
- ETA and POI calculations correct
- Docker Compose deployment clean and portable

**Deliverables:**

- Versioned release: `v1.0.0`
- Final `README.md` and demo dashboard exports

---

## Summary Timeline

| Phase | Description                     | Est. Duration |
| ----- | ------------------------------- | ------------- |
| 1–2   | Core scaffold & backend metrics | 2 days        |
| 3     | Simulation engine               | 2–3 days      |
| 4     | KML & POI                       | 2 days        |
| 5     | Grafana dashboard               | 2 days        |
| 6     | API & control                   | 1–2 days      |
| 7     | Live integration                | 3 days        |
| 8     | Packaging                       | 1 day         |
| 9–10  | Enhancements + QA               | ongoing       |

---

## COMPLETED BEYOND PHASE 0: Major Features Delivered

### Feature 1: KML Route Import and Management (16 Sessions)

**Status:** COMPLETE and MERGED ✅

Comprehensive system for importing, managing, and visualizing KML flight routes
with full simulation mode support.

**Key Deliverables:**

- Web UI and REST API for KML route upload and management
- File-based route storage with automatic watchdog detection
- Route visualization on Grafana map (dark orange line)
- Progress metrics: `starlink_route_progress_percent`,
  `starlink_current_waypoint_index`
- Completion behavior modes: loop, stop, reverse
- Route-POI integration with cascade deletion
- Simulation mode: position automatically follows active route
- 6 test flight plan KML files with timing metadata

**Test Coverage:** 100+ tests passing

### Feature 2: POI Interactive Management (10 Sessions)

**Status:** COMPLETE and MERGED ✅

Full CRUD system for Points of Interest with real-time ETA calculations and
interactive Grafana visualization.

**Key Deliverables:**

- Interactive POI markers on Grafana map with ETA tooltips
- Full REST API for POI management
- Real-time ETA calculations with bearing and distance
- File locking for concurrent access safety
- Color-coded POI status (on-route, approaching, passed)
- Web-based POI management UI

**Test Coverage:** Full integration testing

### Feature 3: ETA Route Timing from KML (24 Sessions, 5 Phases)

**Status:** COMPLETE - ALL 451 TESTS PASSING ✅

Advanced timing-aware system for parsing flight plans with expected waypoint
arrival times and calculating realistic ETAs.

**Key Deliverables:**

**Phase 1: Data Models** ✅

- Extended route models with timing fields
- Optional arrival times and segment speeds
- RouteTimingProfile for aggregate timing metadata
- 28 unit tests for model validation

**Phase 2: KML Parser Enhancements** ✅

- Timestamp extraction from KML descriptions:
  `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
- Haversine distance calculations for accuracy
- Segment speed calculations from timing data
- Route timing profile population
- 45+ unit and integration tests

**Phase 3: API Integration** ✅

- ETA calculation endpoints for waypoints and locations
- Route progress metrics endpoint
- Timing profile exposure in API responses
- 12 integration tests for endpoints

**Phase 4: Grafana Dashboard & Caching** ✅

- 4 new Grafana dashboard panels for timing visualization
- ETA caching system (5-second TTL)
- ETA accuracy tracking and historical metrics
- Live mode support for real-time position feeds

**Phase 5: Simulator Timing Integration** ✅

- Simulator respects route timing speeds
- Realistic movement matching expected flight profile
- Speed override logic for timed routes
- Backward compatibility with untimed routes
- Critical bug fix: Route timing speeds take precedence over config defaults

**Test Coverage:** 451 tests passing (100%) **Key Metrics Added:**

- `starlink_route_timing_has_data`
- `starlink_route_timing_total_duration_seconds`
- `starlink_route_timing_departure_unix`
- `starlink_route_timing_arrival_unix`
- `starlink_eta_to_waypoint_seconds`
- `starlink_distance_to_waypoint_meters`
- `starlink_segment_speed_knots`

---

**End Goal:** A robust, portable Starlink monitoring system that can run fully
simulated in any environment, then transition seamlessly to live data when
connected to a terminal.

**Current Achievement:** Foundation complete with three major features fully
implemented, tested (451 tests), and integrated. System ready for production
deployment or continuation with additional enhancements.
