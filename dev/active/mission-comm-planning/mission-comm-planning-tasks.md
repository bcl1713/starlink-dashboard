# Mission Communication Planning Tasks

Last Updated: 2025-11-10

Each checkbox is a self-contained work item with concrete steps for a junior
developer. Complete them sequentially.

## Phase 1 – Mission Data Foundations

- [ ] **Define mission schemas**
  - Create `backend/starlink-location/app/mission/models.py` containing Pydantic
    models for `Mission`, `TransportConfig`, `XTransition`, `KaOutage`,
    `AARWindow`, `TimelineAdvisory`.
  - Required fields (see `mission-comm-planning-plan.md:32-54`): route_id,
    transport IDs, transition lat/lon, target satellite/beam ID, optional outage
    windows, AAR waypoint names.
  - Add validation helpers (e.g., lat between -90/90, lon -180/180, timestamps
    ISO8601).
  - Write tests in `backend/starlink-location/tests/test_mission_models.py` that
    load sample JSON and assert both successful parsing and expected validation
    errors.

- [ ] **Mission storage utilities**
  - Create `backend/starlink-location/app/mission/storage.py` with functions
    `save_mission(mission: Mission)`, `load_mission(mission_id)`,
    `list_missions()` using `data/missions/` for persistence.
  - Files should be portable (`<mission_id>.json` plus subfolder for
    attachments); ensure directories are created automatically.
  - Add a simple checksum (e.g., SHA256) stored alongside each mission for
    integrity.
  - Test with `pytest` to confirm missions survive process restarts (write,
    reload, compare models).

- [ ] **CRUD + activation endpoints**
  - Add a FastAPI router (`backend/starlink-location/app/mission/routes.py`)
    exposing:
    - `POST /api/missions` (create)
    - `GET /api/missions` (list)
    - `GET /api/missions/{id}` (details)
    - `PUT /api/missions/{id}` (update/import)
    - `POST /api/missions/{id}/activate`
  - Activation should: store `active_mission_id`, reset `FlightStateManager` to
    `pre_departure`, and enqueue a timeline recompute.
  - Write integration tests in
    `backend/starlink-location/tests/test_mission_routes.py` using FastAPI
    TestClient.

- [ ] **Mission metrics**
  - In `backend/starlink-location/app/metrics.py`, register gauges/counters:
    - `mission_active_info{mission_id,route_id}` (value 1 when active)
    - `mission_phase_state` (0=pre,1=in_flight,2=post)
    - `mission_next_conflict_seconds` (time until next degraded/critical window)
  - Update activation handler to refresh these metrics.
  - Add tests asserting the metrics exist and update when missions change.

- [ ] **Mission planner GUI (MVP)**
  - Scaffold `frontend/mission-planner/` (React + Vite or similar).
  - Features:
    - Upload/select route (call existing route endpoints); display departure
      time extracted from `/api/routes/{id}/timing`.
    - X transition table where user inputs lat/lon + new satellite/beam ID.
      When the form is submitted, the backend should reuse the existing
      `RouteETACalculator.project_poi_to_route` helper (already exercised via
      `POIManager.calculate_poi_projections`) to translate lat/lon to the
      nearest route point/time; the UI just displays the computed timestamp and
      ±15 min buffer.
    - Read-only Ka card showing auto-calculated transitions from backend (call
      `/api/missions/coverage/t2`). Include optional outage scheduler (start
      timestamp + duration) similar to Ku.
    - AAR form with dropdowns containing all KML waypoint names using the
      existing `/api/routes/{route_id}/waypoints` endpoint so we don’t rebuild
      waypoint parsing. Selecting start/end automatically previews the derived
      time window returned from `/api/routes/{route_id}/timing`.
    - Optional Ku outage toggle.
  - Provide `README.md` with setup instructions (`npm install`, `.env` vars for
    API base URL) and an `npm run build` script that outputs static files for
    Grafana embedding.

- [ ] **Import/export workflow**
  - In the GUI, add buttons:
    - `Export JSON` → download mission payload from `GET /api/missions/{id}`.
    - `Import JSON` → upload a file, preview parsed content, then call
      `PUT /api/missions/{id}`.
  - Validate mission IDs to avoid accidental overwrites (e.g., require explicit
    confirmation when IDs differ).
  - Add API tests ensuring exported missions can be re-imported verbatim.

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
