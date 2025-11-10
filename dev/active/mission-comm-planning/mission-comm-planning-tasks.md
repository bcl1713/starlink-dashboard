# Mission Communication Planning Tasks

Last Updated: 2025-11-10

Each checkbox is a self-contained work item with concrete steps for a junior
developer. Complete them sequentially.

## Phase 1 – Mission Data Foundations

- [x] **Define mission schemas** ✅ COMPLETE
  - Created `backend/starlink-location/app/mission/models.py` (551 lines)
  - Pydantic models: Mission, TransportConfig, XTransition, KaOutage, AARWindow, KuOutageOverride, TimelineSegment, TimelineAdvisory, MissionTimeline
  - All required fields with validation: coordinates (-90/90 lat, -180/180 lon), durations (>0), ISO8601 timestamps
  - 25 unit tests covering all models and enumerations
  - See `PHASE-1-COMPLETION.md` for detailed model documentation

- [x] **Mission storage utilities** ✅ COMPLETE
  - Created `backend/starlink-location/app/mission/storage.py` (243 lines)
  - Functions: save_mission, load_mission, list_missions, delete_mission, mission_exists
  - Portable flat-file design: `data/missions/{mission_id}.json` + `.sha256` checksums
  - SHA256 checksum validation for data integrity
  - 17 unit tests proving roundtrip serialization and restart resilience
  - Automatic directory creation on first save

- [x] **CRUD + activation endpoints** ✅ COMPLETE
  - Add FastAPI router (`backend/starlink-location/app/mission/routes.py`)
    with endpoints:
    - `POST /api/missions` (create) – Return created mission with 201
    - `GET /api/missions` (list) – Return paginated list with filtering
    - `GET /api/missions/{id}` (read) – Return full mission object
    - `PUT /api/missions/{id}` (update) – Merge changes, update timestamp
    - `DELETE /api/missions/{id}` (delete) – Remove mission files
    - `POST /api/missions/{id}/activate` (activate) – Set active_mission_id, trigger timeline recompute
    - `GET /api/missions/active` (get active) – Return currently active mission
  - Activation logic:
    - Store global `active_mission_id` in app state (or config)
    - Signal flight state manager to reset to `pre_departure` (integration point)
    - Enqueue or immediately trigger timeline recomputation (Phase 3)
    - Return activation confirmation with timestamp
  - Error handling: 404 if mission not found, 409 if already active, 422 if invalid
  - Write integration tests in `backend/starlink-location/tests/integration/test_mission_routes.py`
    using FastAPI TestClient
  - Key: Reuse Mission model from storage layer; avoid duplication

- [x] **Mission metrics** ✅ COMPLETE
  - Registered 4 Prometheus gauges in `backend/starlink-location/app/core/metrics.py`:
    - `mission_active_info{mission_id,route_id}` – Value=1 when mission is active, 0 when not
    - `mission_phase_state{mission_id}` – 0=pre_departure, 1=in_flight, 2=post_arrival
    - `mission_next_conflict_seconds{mission_id}` – Seconds until next degraded/critical window (-1 if none)
    - `mission_timeline_generated_timestamp{mission_id}` – Unix timestamp of last timeline recompute
  - Implemented helper functions: update_mission_active_metric(), clear_mission_metrics(), update_mission_phase_metric(), update_mission_timeline_timestamp()
  - Integrated into activation endpoint: calls update_mission_active_metric() on activate, clear_mission_metrics() on deactivate
  - Integrated into delete endpoint: clears metrics when mission is deleted
  - Added 12 unit tests in `tests/unit/test_mission_metrics.py` verifying metric registration and updates
  - Metrics verified appearing in `/metrics` endpoint with proper HELP and TYPE lines
  - Phase 3 integration point ready: timeline recompute can call update_mission_timeline_timestamp() and update_mission_phase_metric()

- [x] **Mission planner GUI (MVP)** ✅ COMPLETE
  - Implemented at `backend/starlink-location/app/api/ui.py` endpoint: `/ui/mission-planner`
  - **Design Approach**: Server-side HTML/CSS/JS (consistent with existing POI/Routes UIs)
  - **Features Implemented**:
    - Mission setup section: create/select/edit/delete missions
    - Route selection dropdown (calls `/api/routes`)
    - X transition form: latitude, longitude, target satellite, optional beam ID
    - X transition table with add/remove functionality
    - Ka transport tab: read-only default satellites (T2-1, T2-2, T2-3), manual outage scheduler
    - Ku transport tab: LEO overrides with duration and optional reason
    - AAR form: waypoint dropdowns dynamically populated from selected route via `/api/routes/{id}`
    - AAR segments table with add/remove functionality
    - Export/Import buttons for JSON file download/upload
  - **Real-time Features**:
    - 5-second refresh interval for mission list
    - Auto-loads routes and populates form dropdowns
    - Full CRUD integration with backend API
    - Responsive design with mobile support
  - **Testing**: All 608 tests passing, zero regressions
  - **UI/UX**: Professional gradient header, color-coded badges (X=red, Ka=green, Ku=cyan), smooth transitions
  - **Access**: http://localhost:8000/ui/mission-planner

- [x] **Import/export workflow** ✅ COMPLETE
  - Export JSON button: downloads current mission as JSON file
  - Import JSON button: file upload with automatic form population
  - Seamless roundtrip: export→edit external→import works perfectly
  - Integrated into mission save flow: form tracks all transport configurations
  - No accidental overwrites: import preserves mission ID from file

## Phase 2 – Satellite Geometry & Constraint Engine

- [ ] **Satellite catalog + HCX KMZ ingestion**
  - Place the provided `HCX.kmz` under `data/sat_coverage/` and load it at
    startup.
  - Convert KMZ polygons (PORB/PORA/IOR/AOR) to GeoJSON
    (`data/sat_coverage/hcx.geojson`); store metadata (satellite name,
    longitudinal center, color) in
    `backend/starlink-location/app/satellites/catalog.py`.
  - Support additional satellite definitions via `data/satellites/catalog.yaml`
    (for future expansion).

- [ ] **Azimuth/elevation utilities**
  - Implement `backend/starlink-location/app/satellites/geometry.py` with
    helpers:
    - `ecef_from_geodetic(lat, lon, alt)`
    - `look_angles(aircraft_lat, aircraft_lon, aircraft_alt, sat_lon)`
  - Use `pyproj` if available; fallback to manual formulas.
  - Add tests comparing outputs to known values (hard-code cases from online
    calculators).

- [ ] **Transition projection + buffers**
  - Expose a backend helper (or reuse an existing API route) that wraps
    `RouteETACalculator.project_poi_to_route` so new X transition lat/lon pairs
    can be projected without duplicating math (this is the same logic already
    used by `POIManager.calculate_poi_projections`).
  - Automatically create POIs in `/data/generated/pois/` for both the actual
    coordinates (for map display) and the projected route point (for timing
    math).
  - Generate ±15 min degrade windows for each X/Ka transition and tag them with
    reason codes.

- [ ] **Coverage sampler for Ka**
  - Build `backend/starlink-location/app/satellites/coverage.py` that:
    1. Samples the route every 60 s.
    2. Runs point-in-polygon against the GeoJSON footprints.
    3. Detects entry/exit times and produces crossover events.
    4. Falls back to elevation math when the aircraft isn’t inside any polygon.
  - Store computed events in `data/missions/<id>/t2-transitions.json` for reuse.

- [ ] **Rule evaluation + advisories**
  - Combine azimuth checks, coverage events, takeoff/landing buffers, and AAR
    windows into a single list of `MissionEvent` objects (timestamp, event_type,
    transport, metadata).
  - Produce operator advisories (e.g., “Disable X from 01:25Z to 02:10Z due to
    transition to X-2”).
  - Expose the advisories via `/api/missions/{id}` so exports and dashboards can
    reuse them.

## Phase 3 – Communication Timeline Engine

- [ ] **Transport availability state machine**
  - Implement logic in `backend/starlink-location/app/mission/state.py` that
    takes `MissionEvent` list and outputs contiguous intervals per transport
    (available/degraded/offline).
  - Unit tests should simulate overlapping events (e.g., X transition
    overlapping AAR) to ensure precedence rules behave as expected.

- [ ] **Timeline segmentation**
  - Build `backend/starlink-location/app/mission/timeline.py` to merge
    per-transport intervals into mission-wide segments labeled `nominal`,
    `degraded`, `critical`.
  - Include reasons (array) and impacted transports.
  - Write tests using Leg 6 Rev 6 sample events (manually crafted) to confirm
    segmentation.

- [ ] **Metrics + REST endpoints**
  - Expose `GET /api/missions/{id}/timeline` (returns JSON array) and
    `GET /api/missions/active/timeline`.
  - In `/metrics`, publish gauges: `mission_comm_state{transport=…}`,
    `mission_degraded_seconds`, `mission_critical_seconds` (latter counters
    accumulate since activation).
  - Validate via tests that metrics change when new timeline data is computed.

- [ ] **Export generators (CSV/XLSX/PDF)**
  - Create `backend/starlink-location/app/mission/exporter.py`:
    - Convert timeline segments to pandas DataFrame → export to CSV and XLSX.
    - Use `WeasyPrint` or `ReportLab` to render the PDF mock (cover page, table,
      map placeholder).
    - Format timestamps as UTC, Eastern (DST aware via `pytz`/`zoneinfo`), and
      T+HH:MM.
  - Add API endpoint `POST /api/missions/{id}/export?format=csv|xlsx|pdf`
    returning file downloads.
  - Integration tests should generate each format and verify headers/content.

## Phase 4 – Visualization & Outputs

- [ ] **Grafana map overlays**
  - Update `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
    to include:
    - Satellite POI layer hitting `/api/missions/active/satellites`.
    - Coverage overlay layer referencing the GeoJSON served from
      `/data/sat_coverage/hcx.geojson` (via backend proxy if needed).
    - AAR start/end markers and transition POIs from mission data.
  - Document required Grafana plugins or permissions in `monitoring/README.md`.

- [ ] **Mission timeline panel & alerts**
  - Add a state timeline panel (e.g., Grafana “State Timeline” viz) pointed at
    `/api/missions/active/timeline`.
  - Configure Prometheus alert rules under
    `monitoring/prometheus/rules/mission-alerts.yml` to notify when a
    degraded/critical window is <15 minutes away.
  - Verify with `promtool test rules` and Grafana alert test mode.

- [ ] **UX validation + documentation**
  - Run a dry-run with planners using Leg 6 Rev 6 data; capture notes in
    `dev/active/mission-comm-planning/SESSION-NOTES.md`.
  - Update `docs/MISSION-PLANNING-GUIDE.md` with screenshots of the GUI and
    sample PDFs/CSVs.

## Phase 5 – Hardening & Ops Readiness

- [ ] **Scenario regression tests**
  - Add pytest cases covering:
    1. Mission with two X transitions and one AAR.
    2. Mission with back-to-back Ka coverage gaps.
    3. Mission with manual Ku outage and delayed departure.
  - Tests should assert timeline status counts, advisories, and export content
    hashes.

- [ ] **Performance benchmarking**
  - Script `tools/benchmark_mission_timeline.py` should load 10 missions
    concurrently and measure timeline recompute time (<1s target) and memory
    usage.
  - Record results in `docs/PERFORMANCE-NOTES.md` with hardware specs.

- [ ] **Operational handoff**
  - Create `docs/MISSION-COMM-SOP.md` describing planner workflow, export
    delivery, live monitoring, and incident response.
  - Update root `README.md` and `docs/INDEX.md` to link to all new mission
    planning docs + GUI instructions.
