# Mission Communication Planning Context

Last Updated: 2025-11-12 (Auto HCX/X-Band POI sync + IDL fixes)

## Purpose

Enable pre-flight mission planning that predicts communication degradation
across three onboard transports by analyzing timed flight routes, satellite
geometries, and operational constraints (AAR, takeoff/landing buffers,
transition points).

## Key Components & Files

### Completed (Phase 1 + Phase 1 Continuation)
- `backend/starlink-location/app/mission/models.py` – Pydantic models for Mission, TransportConfig, XTransition, KaOutage, AARWindow, KuOutageOverride, TimelineSegment, TimelineAdvisory, MissionTimeline
- `backend/starlink-location/app/mission/storage.py` – Portable mission persistence (JSON + SHA256 checksums)
- `backend/starlink-location/app/mission/routes.py` – CRUD endpoints (POST/GET/PUT/DELETE/activate) + integration with FastAPI
- `backend/starlink-location/tests/unit/test_mission_*.py` – 87 passing unit tests (75 models/storage + 12 metrics)
- `backend/starlink-location/tests/integration/test_mission_routes.py` – 33 integration tests for CRUD operations
- `backend/starlink-location/app/core/metrics.py` – Prometheus mission metrics (mission_active_info, mission_phase_state, mission_next_conflict_seconds, mission_timeline_generated_timestamp)
- `backend/starlink-location/tests/unit/test_mission_metrics.py` – 12 unit tests for metrics
- `data/missions/` – Mission storage directory (auto-created)
- `dev/active/mission-comm-planning/PHASE-1-COMPLETION.md` – Detailed Phase 1 report

### Completed (Phase 1 Continuation)
- `backend/starlink-location/app/api/ui.py` – Mission Planner GUI endpoint `/ui/mission-planner` (lines 1775-2964, 1,190 lines) with inline route upload, mission drafts, dirty-state tracking, activation controls, satellite POI modal, and automatic mission POI sync.
- `backend/starlink-location/app/models/poi.py`, `app/services/poi_manager.py`, `app/api/pois.py` – Mission-scoped POI support (new `mission_id`, filtering, cleanup utilities).
- `backend/starlink-location/app/mission/routes.py` + `main.py` – Mission activation now auto-activates the associated route and injects the POI manager for mission POI cleanup on delete.

### Completed (Phase 2 + Phase 3 Core)
- `backend/starlink-location/app/satellites/` – Satellite catalog, KMZ ingestion, look-angle geometry, coverage sampler, and rule engine (Phase 2) with 75 dedicated unit tests.
- `backend/starlink-location/app/mission/state.py` – Transport availability state machine generating contiguous intervals for X/Ka/Ku along with pytest coverage in `tests/unit/test_mission_state.py`.
- `backend/starlink-location/app/mission/timeline.py` – Timeline segment builder and `MissionTimeline` assembler plus `tests/unit/test_mission_timeline.py`.
- `backend/starlink-location/app/mission/timeline_service.py` – End-to-end timeline computation (POI projection, Ka coverage sampling, swap/gap POI generation, Prometheus summary) invoked during mission activation.
- `backend/starlink-location/app/mission/routes.py` – Activation writes cached timelines, updates new metrics, and exposes `/api/missions/{id|active}/timeline`; mission storage now persists `*.timeline.json`.
- Test fixtures now isolate mission storage under `/tmp/test_data/missions`, eliminating leftover JSON files that previously broke first-run integration tests.

### Completed (Latest Session Enhancements)
- `backend/starlink-location/app/mission/timeline_service.py` now performs automatic HCX coverage and X/AAR POI synchronization whenever a mission timeline is recomputed (including the silent recomputes triggered immediately after mission saves). Mission-generated POIs share the `mission-event` category and use concise multi-line labels (`HCX\nExit POR`, `X-Band\nX-Band-7→X-Band-6`, `AAR\nStart/End`).
- Ka coverage gap detection became International Date Line aware, preventing false POR outages when polygons wrap at ±180°.
- Mission planner save workflow (`app/api/ui.py`) now triggers a backend recompute + POI reload, so planners see updated HCX/X-Band markers without clicking "Recompute Timeline".
- `/api/pois` filtering prefers the latest (or active) mission per route, hiding stale mission-event POIs from earlier drafts.

### Phase 2: Term Replacements (WGS → X-Band)
- Documentation terminology standardized: `WGS-7→WGS-6` → `X-Band-7→X-Band-6` in mission-comm-planning-context.md, ensuring consistent satellite band naming across all dev documentation.

### In Progress / Planned
- Grafana mission timeline panels + alert rules (Phase 4) still pending now that exporters/APIs/POIs are aligned.
- Document the new POI lifecycle, IDL handling, and save-time recompute behavior in `docs/MISSION-PLANNING-GUIDE.md` + monitoring README once Grafana work lands.

### Foundation Systems
- `backend/starlink-location/` – FastAPI service hosting mission APIs, simulation, metrics exporters
- `data/routes/` + `/data/sim_routes/` – Input KML files with timing metadata already supported
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` – Primary visualization to extend
- `docs/ROUTE-TIMING-GUIDE.md`, `docs/METRICS.md`, `docs/ROUTE-API-SUMMARY.md` – Foundational APIs
- `dev/active/eta-route-timing/` – Previous work that established the timing engine we depend on

### Current Session Highlights (2025-11-12)
- Mission saves auto-trigger timeline recompute + POI refresh, keeping HCX/X-Band/AAR markers in sync without manual intervention.
- Ka coverage samplers ignore IDL-induced polygon splits, eliminating false POR gaps and keeping coverage continuous through longitude wrap.
- Mission-event POIs across multiple missions on the same route are now de-duped at recompute time and hidden from `/api/pois` results unless they belong to the latest (or active) mission.
- POI titles were shortened and formatted with explicit `\n`, and POI IDs are slugified so newline titles produce stable identifiers for projection caching.

**Outstanding work:** Grafana overlays/panels and alerts (Phase 4), documentation updates, exporter UX polish, HCX transition visualization inside Grafana, and scenario/perf hardening (Phase 5); see STATUS for details.

## Data Inputs & Artifacts

- Timed flight path KML with waypoint timestamps (already handled).
- Satellite definitions provided as POIs (lon/lat) or coverage polygons/KML
  overlays.
- Mission planner-specified POIs for satellite transitions and air refueling
  tracks; POIs off the route are projected to the nearest route point for timing
  while remaining at their actual coordinates for visualization.
- Rules for azimuth exclusion ranges (normal ops: 135°–225°, AAR: 315°–45°) and
  mandatory ±15 minute runway buffers plus ±15 minute degrade windows around
  each X/Ka transition.
- Transport catalog:
  - **X:** Fixed geostationary satellites; planner supplies which satellite
    (e.g., X-1, X-2) is active per route segment plus transition POIs. Assumed
    coverage when assigned satellite is active. Only transport affected by
    azimuth constraints; operators must be instructed to disable during conflict
    windows and timeline must mark X unavailable.
  - **Ka:** Three geostationary satellites with global-ish coverage limited by
    latitude. Need ability to compute optimal transition points (midpoint of
    overlap) or degrade timeline when out of coverage. Accept either KML
    overlays or orbital longitude inputs.
  - **Ku:** Always-on LEO constellation; treated as nominal unless manual
    override flags failure.

## Operational Constraints

- Aircraft carries 3 transports; target timeline must classify degradation when
  1 transport unusable and critical when 2 transports unusable.
- Air refueling windows invert azimuth exclusions (X blocked when azimuth
  within 315°–45°) and count as automatic comm blackouts.
- Transition POIs and AAR POIs off the route must be projected to the
  time-aligned route point to keep ETA math accurate while preserving original
  coordinates for Grafana overlays.
- X requires manual disable advisories during azimuth conflicts; exported
  timelines must highlight those windows for operators and customers.
- Ku is expected to be up but can fail—timeline must allow manual overrides or
  telemetry inputs to mark additional outages.

## Integration Points

- Prometheus metrics > Grafana alerts to warn about upcoming degraded intervals.
- `/api/missions/*` endpoints for mission CRUD, timeline exports, and Grafana
  data sources.
- Potential ingestion scripts for satellite catalogs (KML overlays or static
  JSON) stored under `data/satellites/` (new directory to create).

## Decisions & Clarifications

1. **Mission storage:** Use portable flat files so planning can run on one
   instance and be copied to another for live execution.
2. **Ka coverage:** Ship the provided HCX KMZ (PORB/PORA/IOR/AOR) with the app
   as the default footprint set (`app/satellites/assets/HCX.kmz` auto-converts
   into `/data/sat_coverage/hcx.geojson` at runtime). When alternative
   satellites are needed, fall back to math-based coverage estimates unless
   planners supply another KMZ.
3. **Planner workflow:** Provide a mission-planning GUI (Grafana panel or
   standalone web UI) backed by the same APIs used for routes/POIs so planners
   rarely touch raw JSON.
4. **Airports:** Departure and arrival POIs already exist and are properly
   labeled inside the KML—no extra generation needed.
5. **Schedule volatility:** Plans rarely change but departure times can slip.
   Customer deliverables must show timestamps in UTC (Zulu), Eastern (DST-aware
   for the mission date), and relative T+HH:MM. Live dashboards should
   automatically align to actual time/position vs. the plan.
6. **Mission-scoped POIs (new 2025-11-11):** X-band transitions and AAR window endpoints are persisted as mission-specific POIs (tagged with both `mission_id` and `route_id`). Mission delete cleans them up, and subsequent saves re-generate them to keep revisions self-contained.
7. **Mission activation (new 2025-11-11):** Activating a mission also activates its associated route through `RouteManager`, guaranteeing POI projections and Grafana panels reflect the correct geometry without manual route toggles.

## Open Questions

- None at this time.
