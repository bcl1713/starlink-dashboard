# Mission Communication Planning Tasks

Last Updated: 2025-11-11

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
    - Ka transport tab: read-only default satellites (AOR, POR, IOR), manual outage scheduler
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

- [x] **Satellite catalog + HCX KMZ ingestion** ✅ COMPLETE
  - Default catalog now ships with HCX coverage (`app/satellites/assets/HCX.kmz`) which auto-converts into `/data/sat_coverage/hcx.geojson` at runtime; custom catalogs load from `/data/satellites/catalog.yaml`.

- [x] **Azimuth/elevation utilities** ✅ COMPLETE
  - `app/satellites/geometry.py` implements ECEF helpers + `look_angles` with unit coverage.

- [x] **Transition projection + buffers** ✅ COMPLETE
  - Route projections reuse `RouteETACalculator`; mission save emits ±15 minute degrade windows.

- [x] **Coverage sampler for Ka** ✅ COMPLETE
  - `app/satellites/coverage.py` samples once per minute and emits swap/gap events persisted via timeline service.

- [x] **Rule evaluation + advisories** ✅ COMPLETE
  - `app/satellites/rules.py` produces unified `MissionEvent` streams (X/Ka/Ku) consumed by `timeline_service`.

## Phase 3 – Communication Timeline Engine

- [x] **Transport availability state machine** ✅ COMPLETE (2025-11-11)
  - Added `backend/starlink-location/app/mission/state.py` with helpers to turn `MissionEvent` sequences into contiguous intervals per transport (tracks degraded/offline reasons, clamps bounds, handles overlapping events).
  - Unit coverage in `backend/starlink-location/tests/unit/test_mission_state.py` exercises X transitions, landing buffers, Ka coverage/outage precedence, pre-mission events, and ensures intervals close correctly.
  - 2025-11-13 refresh: Route sampling now drives Ka overlap-based transitions and real-time X-band azimuth checks (forward + aft cones), so degradations only trigger when geometry demands it.

- [x] **Timeline segmentation** ✅ COMPLETE (2025-11-11)
  - Implemented `backend/starlink-location/app/mission/timeline.py` to merge transport intervals into ordered `TimelineSegment`s plus `MissionTimeline` assembly helpers.
  - Added `tests/unit/test_mission_timeline.py` validating nominal/degraded/critical slicing, impacted transport metadata, and boundary clamping.

- [x] **Metrics + REST endpoints** ✅ COMPLETE (2025-11-12)
  - Added `backend/starlink-location/app/mission/timeline_service.py` to project X transitions and Ka coverage events onto the route, persist cached `MissionTimeline` JSON, and emit swap/gap POIs.
  - Mission activation now computes/stores the timeline, updates Prometheus gauges (`mission_comm_state`, `mission_degraded_seconds`, `mission_critical_seconds`, `mission_next_conflict_seconds`, `mission_timeline_generated_timestamp`), and exposes `GET /api/missions/{id}/timeline` plus `/api/missions/active/timeline`.
  - Integration tests stub the timeline builder to validate activation, endpoints, and metrics without heavy geometry dependencies; all suites run inside Docker after rebuilding/restarting the container.

- [x] **Export generators (CSV/XLSX/PDF)** ✅ COMPLETE (2025-11-12)
  - Added `backend/starlink-location/app/mission/exporter.py` with CSV, XLSX (multi-sheet), and PDF renderers built on pandas/openpyxl/reportlab plus timezone-aware formatting for UTC, Eastern, and T+ offsets.
  - Introduced `TimelineExportFormat` + `generate_timeline_export()` wrapper returning media metadata and byte payloads for API use.
  - Added `POST /api/missions/{id}/export?format=csv|xlsx|pdf` producing streamed downloads with correct MIME types + attachment filenames.
  - Mission Planner UI now exposes “Recompute Timeline” + inline export controls that call the recompute/export APIs, and integration/unit tests validate every format.

- [ ] **HCX/Ka transition surfacing**
  - Generate human-readable Ka swap entries (derived from coverage overlaps) and expose them via exporter + Grafana data sources.
  - Acceptance: Timeline/export rows list upcoming HCX transitions with timestamps/satellite IDs, and the mission planner GUI presents the same data so operators can brief Ka handoffs alongside X-band transitions.

## Phase 4 – Visualization & Outputs

- [ ] **Grafana map overlays**
  - Update `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` to include:
    - Satellite POI layer hitting `/api/missions/active/satellites`.
    - Coverage overlay layer referencing the GeoJSON served from `/data/sat_coverage/hcx.geojson` (via backend proxy if needed).
    - AAR start/end markers and transition POIs from mission data.
  - Document required Grafana plugins or permissions in `monitoring/README.md`.

- [ ] **Mission timeline panel & alerts**
  - Add a state timeline panel (e.g., Grafana “State Timeline” viz) pointed at `/api/missions/active/timeline`.
  - Mirror the export styling rules: single-transport degradations render with light yellow backgrounds, multi-transport degradations with light red backgrounds, and pure `X-Ku Conflict` windows remain warning-only. Panel legend labels must read `X-Band`, `HCX`, and `StarShield`.
  - Configure Prometheus alert rules under `monitoring/prometheus/rules/mission-alerts.yml` to notify when a degraded/critical window is <15 minutes away.
  - Verify with `promtool test rules` and Grafana alert test mode.

- [ ] **UX validation + documentation**
  - Run a dry-run with planners using Leg 6 Rev 6 data; capture notes in `dev/active/mission-comm-planning/SESSION-NOTES.md`.
  - Update `docs/MISSION-PLANNING-GUIDE.md` with screenshots of the GUI and sample PDFs/CSVs.

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
- [x] **Mission planner UX hardening** ✅ COMPLETE (2025-11-11)
  - Added mission draft dirty-state tracking, “New Mission” CTA, and confirmation prompts before discarding edits.
  - Inline KML upload now reuses `/api/routes/upload`, reloads waypoints automatically, and mission save/export reconciles with server timestamps.
  - Activation button calls `/api/missions/{id}/activate` and UI status badge reflects Draft / Unsaved / Active states.

- [x] **Mission-scoped POIs** ✅ COMPLETE (2025-11-11)
  - `POI` models/storage/API now support `mission_id`.
  - Mission save regenerates mission POIs (X transitions + AAR endpoints) scoped to the active route/mission pair; mission delete purges them automatically.
  - Prevents global POI pollution while allowing multiple revisions of the same base route.

- [x] **Mission activation auto-syncs route** ✅ COMPLETE (2025-11-11)
  - `mission_routes.activate_mission` now activates the associated KML route through `RouteManager`.
  - Ensures POI projections, timelines, and Grafana panels stay aligned without a manual route toggle.

- [ ] **Fix mission/POI regression tests** ⏳ NEXT
  - Re-run full unit + integration suite after the POI schema/UI changes.
  - Update failing tests (expected POI fields, route activation side effects, etc.).
  - Blocker for merging current branch.
