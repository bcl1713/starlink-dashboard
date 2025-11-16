# Mission Communication Planning Feature Plan

Last Updated: 2025-11-10

## Executive Summary

Create a mission-planning workflow that merges planned flight routes, satellite
resources, and operational constraints into a single analytics pipeline. The
feature will ingest timed KML flight routes, satellite POIs or footprint
overlays, air-refueling windows, and planned transport transitions, then compute
azimuth-based interference risks and mission-wide communication timelines.
Transport-specific handling is required: **X** uses fixed geostationary
satellites with planner-provided transition POIs and is subject to azimuth
exclusions, **Ka** uses three geostationary satellites with global-ish coverage
that can rely on either provided KMZ polygons or pure math, and **Ku** is an
always-on LEO link. Deliverables include backend data models and APIs in
`backend/starlink-location`, Prometheus metrics for risk states, Grafana
overlays for satellite POIs/coverage, and customer-friendly timeline exports
showing degradation levels per transport with timestamps in Zulu, Eastern, and
relative T+ formats.

## Current State Analysis

- **Routing & Timing:** Route upload, KML-to-GeoJSON conversion, and timing
  extraction already exist (`docs/ROUTE-TIMING-GUIDE.md`). Active route progress
  and POI ETA metrics feed Grafana maps/POI tables.
- **POI System:** Static POIs are supported with ETA/distance metrics, but they
  do not encode satellite properties, azimuth tolerances, or lifecycle states
  (takeoff/landing, refueling, transport transitions), nor do they project
  off-route POIs onto the route timeline while keeping their real-world
  coordinates for map display.
- **Visualization:** Grafana dashboards show aircraft track, POIs, and metrics
  but lack layers for satellite footprints or timeline panels for comm
  readiness.
- **Operational Constraints:** Azimuth dead-zones (135°–225° during normal ops,
  315°–45° during AAR) and multi-transport coordination are not modeled. No
  mechanism marks takeoff/landing buffers or air-refueling blackout rules, and
  azimuth constraints are not scoped to X only.
- **Outputs:** There is no persisted mission plan entity, scenario simulator, or
  customer-facing timeline export.

## Proposed Future State

- Mission plan objects persist uploaded route IDs, transport inventories (three
  onboard links), initial satellite assignments, planned transition POIs, and
  AAR segments. When POIs (transition or AAR) are off the uploaded route, they
  are projected to the nearest point on the timed path for sequencing but still
  rendered at their actual coordinates. Mission files remain portable (flat
  YAML/JSON plus assets) so planners can prepare missions on a separate staging
  instance and copy them to the live stack. Every X/Ka transition automatically
  injects ±15-minute degrade buffers on either side so customers see the handoff
  risk window.
- A dedicated mission-planning GUI (backed by the API) lets planners select the
  starting X satellite, enter latitude/longitude for each transition POI (even
  when staying on the same satellite/beam), and capture the new satellite/beam
  ID. The app projects those coordinates onto the route to compute timing,
  generates the POIs automatically, and enforces the ±15-minute buffer. Ka
  transitions are auto-calculated from coverage footprints (planner can only
  schedule optional outages similar to Ku). AAR begin/end selections use
  dropdowns populated from the uploaded route waypoints so no free-text entry is
  required.
- Satellite resources support both orbital POIs (lon/lat @ geostationary
  altitude) and coverage polygons (KML overlays). The provided HCX KMZ
  (PORB/PORA/IOR/AOR polygons) ships with the app as the authoritative dataset
  for Ka footprints; math-based coverage remains an optional fallback when
  planners swap satellites. The system computes azimuth/elevation from aircraft
  to each satellite along the timed route and evaluates risk windows vs.
  configurable forbidden cones, with **X** exclusively subject to azimuth
  blocks (normal: 135°–225°, AAR: 315°–45°).
- A communication state engine fuses per-transport availability, azimuth
  conflicts, AAR and runway buffers, and transport dependencies to emit timeline
  slices (with `status = nominal|degraded|critical` and justification metadata).
  X segments become unavailable when their planned satellite's azimuth violates
  the relevant cone, while Ka segments degrade or switch based on coverage
  math/overlays and Ku remains nominal unless a manual override marks a failure.
  Timeline outputs respect schedule adjustments (e.g., departure slips) by
  recomputing T+ offsets and live dashboards always show current status relative
  to the mission clock.
- Grafana gains additional map layers (satellite POIs, coverage overlays, AAR
  markers) plus a mission timeline panel sourced from a new
  `/api/missions/{id}/timeline` endpoint, exposed through API clients consistent
  with existing route/POI tooling. The mission GUI provides a "Compute timeline"
  action that triggers backend evaluation so planners can iterate until outputs
  look correct.
- Prometheus publishes metrics like
  `mission_comm_state{transport="satcom",status="degraded"}` and
  `mission_satellite_azimuth_conflict{satellite="SAT-A",degree=180}` for
  alerting, including explicit transport IDs (X/Ka/Ku) so operators know which
  link to disable or expect to lose, and exposing T+ countdowns to upcoming
  conflict windows.
- Customer exports and dashboards display every timestamp in parallel Zulu,
  Eastern (DST-aware), and T+HH:MM formats so planners and customers can align
  on timing regardless of timezone shifts or departure slips; exports include
  server-rendered PDF briefs plus Excel-compatible (CSV/XLSX) files that
  customers can ingest directly.

## Implementation Phases

1. **Mission Data Foundations** – Data model, storage, validation APIs, and
   mission lifecycle hooks.
2. **Satellite Geometry & Constraint Engine** – Satellite catalogs,
   azimuth/elevation calculations, forbidden-cone detection, and
   refueling/takeoff/landing buffers.
3. **Communication Timeline Engine** – Transport availability modeling,
   outage/transition logic, and timeline segmentation with Prometheus exposure.
4. **Visualization & Customer Outputs** – Grafana overlays/timeline panels,
   downloadable timeline reports, and simulation tooling/testing.
5. **Hardening & Ops Readiness** – Alerting, documentation, performance
   validation, and handoff materials.

## Detailed Tasks

### Phase 1 – Mission Data Foundations

1. **Define mission planning schemas** (Effort: M; Depends on: none)
   - Acceptance: JSON schema or Pydantic models capture mission metadata
     (route_id, transports, satellite assignments, AAR segments, runway events)
     and pass unit tests.
2. **Implement mission CRUD endpoints** (Effort: M; Depends on: Task 1)
   - Acceptance: `/api/missions` supports create/read/update/activate;
     validation prevents inconsistent timelines; mission activation ties to
     active route and resets flight state when needed.
3. **Persist mission artifacts** (Effort: S; Depends on: Task 2)
   - Acceptance: Missions store as portable flat files (JSON/YAML + asset refs)
     with optional lightweight index; planners can copy files between instances;
     restart resilience proven via integration test.
4. **Expose mission context metrics** (Effort: S; Depends on: Task 3)
   - Acceptance: Gauges for mission identifiers (e.g., `mission_active`,
     `mission_phase`) appear in `/metrics` and Grafana variables.
5. **Mission planner GUI** (Effort: M; Depends on: Tasks 1–3)
   - Acceptance: Web UI (Grafana panel or standalone page) lets planners select
     initial X/Ka satellites, enter lat/lon for each X transition (including
     same-sat beam handoffs) and target satellite IDs, and the app auto-projects
     those points onto the timed route to compute transition times + POIs. Ka
     panels show read-only auto-calculated transitions plus optional outage
     scheduling, and AAR begin/end pickers are dropdowns populated from route
     waypoints; planners can also flag rare Ku downtime windows.
6. **Mission import/export tooling** (Effort: S; Depends on: Task 5)
   - Acceptance: GUI supports exporting mission JSON bundles and importing
     existing plans (with schema validation) so planners can hand off work
     across instances without manually editing files.

### Phase 2 – Satellite Geometry & Constraint Engine

1. **Build satellite catalog + POI ingestion** (Effort: M; Depends on: Phase 1)
   - Acceptance: CLI/importer ingests satellite definitions (longitude, slot,
     transport ownership, coverage KML/POIs) into standardized store accessible
     to backend. Includes planner-provided X transition POIs (with off-route
     projection metadata) and the built-in HCX KMZ for Ka (converted to GeoJSON
     on ingest) with optional math fallback when planners provide alternative
     satellites.
2. **Implement azimuth/elevation calculator** (Effort: L; Depends on: Task 1)
   - Acceptance: Library computes az/elev from aircraft position/altitude to
     geostationary satellite; unit tests cover edge cases (polar routes, low
     elevation thresholds); performance meets <5 ms per calculation.
     Calculations tag transport (X/Ka) and satellite IDs for downstream rule
     engines.
3. **Encode forbidden-cone rules & buffers** (Effort: M; Depends on: Task 2)
   - Acceptance: Config-driven rules for X-only azimuth exclusions (standard:
     135°–225°; AAR: 315°–45°). Buffer logic automatically injects ±15-minute
     blackout around takeoff/landing, ±15-minute degrade windows around every
     X/Ka transition, plus AAR intervals; rule engine tells operators when to
     disable X manually and marks the transport unavailable for customer
     timelines.
4. **Spatial overlay & coverage modeling** (Effort: M; Depends on: Task 1)
   - Acceptance: Coverage KML overlays (including the bundled HCX KMZ) convert
     to GeoJSON layers stored under `/data/sat_coverage/` and served via API for
     Grafana. When planners select alternate satellites and no overlay exists,
     fall back to math-based footprint estimation to choose mid-overlap
     transition points or flag degraded segments when outside coverage.

### Phase 3 – Communication Timeline Engine

1. **Transport availability modeling** (Effort: M; Depends on: Phases 1–2)
   - Acceptance: Each transport (X/Ka/Ku) tracked with states (available,
     degraded, offline). X state reacts to azimuth conflicts and
     planner-defined transitions, Ka reacts to coverage estimates/overlaps, and
     Ku remains nominal unless overridden; transitions persisted.
2. **Timeline segmentation service** (Effort: L; Depends on: Task 1)
   - Acceptance: Service walks route timeline (leveraging timed KML) to create
     contiguous segments with metadata (time span, active satellites, reason
     codes); compute action from the GUI/API triggers recomputation; passes
     scenario-based tests with sample mission data.
3. **Prometheus + API exposure** (Effort: M; Depends on: Task 2)
   - Acceptance: `/api/missions/{id}/timeline` returns structured JSON;
     Prometheus metrics (`mission_comm_degradation_seconds`,
     `mission_transport_state`) refresh every evaluation cycle; Grafana can
     query timeline endpoints.
4. **Customer timeline export generator** (Effort: S; Depends on: Task 2)
   - Acceptance: Generates Excel-friendly (CSV/XLSX) tables plus server-rendered
     PDF briefs containing per-segment degradation levels, AAR windows,
     takeoff/landing buffers, X manual-disable advisories, and recommended
     satellite transitions, with each timestamp simultaneously formatted as Zulu
     (UTC), Eastern (DST-aware for mission date), and T+HH:MM relative to
     takeoff.

### Phase 4 – Visualization & Customer Outputs

1. **Grafana map enhancements** (Effort: M; Depends on: Phases 2–3)
   - Acceptance: Satellite POIs (icons with azimuth arcs), coverage overlays,
     AAR markers, and transition POIs appear on Fullscreen Overview dashboard;
     off-route POIs show at their actual coordinates while timeline projections
     stay synced; queries reference new APIs.
2. **Mission timeline panel** (Effort: M; Depends on: Phase 3)
   - Acceptance: Custom panel (e.g., state timeline) highlights
     nominal/degraded/critical intervals plus annotations for takeoff, landing,
     refueling, transition points; auto-refreshes with backend timeline data and
     adapts live to actual aircraft position/time relative to the planned
     schedule (showing T+ offsets in real time).
3. **Alerting & notifications** (Effort: S; Depends on: Task 2)
   - Acceptance: Prometheus/Grafana alerts fire when upcoming mission segments
     include critical windows > configurable threshold; includes AAR-specific
     rules.
4. **UX validation with stakeholders** (Effort: S; Depends on: Tasks 1–3)
   - Acceptance: Demo session feedback incorporated; doc updates capture
     workflows for mission planners.

### Phase 5 – Hardening & Ops Readiness

1. **Scenario regression suite** (Effort: M; Depends on: prior phases)
   - Acceptance: Pytest scenarios simulate missions with/without AAR, multiple
     satellite transitions, and random outages; CI pass rate documented.
2. **Performance & scaling review** (Effort: S; Depends on: Task 1)
   - Acceptance: Profiling proves timeline generation handles ≥10 missions
     simultaneously with <1s recompute time; resource usage documented.
3. **Documentation & handoff** (Effort: S; Depends on: completion of above)
   - Acceptance: Update `docs/` (mission planning guide, API reference, Grafana
     instructions) plus `dev/README.md` playbook; include explicit X/Ka/Ku
     behavior tables, off-route projection rules, and customer-facing SOP.

## Risk Assessment and Mitigation

- **Orbital/geometry accuracy risk:** Incorrect azimuth calculations could
  misclassify degradation. Mitigation: leverage vetted formulas (ECEF +
  look-angle math), compare with trusted tools, include unit/regression tests
  with known coordinates.
- **Data quality risk:** Missing or inconsistent satellite coverage data could
  block automation. Mitigation: support both coverage polygons and fallback
  orbital POIs; add validation CLI with warnings.
- **Complex timeline logic:** Combining transports, buffers, and user overrides
  may create brittle logic. Mitigation: centralize rules in declarative engine
  with exhaustive scenario tests and logging.
- **Performance risk:** Evaluating azimuths for every waypoint may be expensive.
  Mitigation: reuse existing timed-route interpolation, cache satellite look
  angles per segment, and limit evaluation cadence.
- **User workflow risk:** Mission planners need intuitive inputs. Mitigation:
  provide templates, API examples, and Grafana forms to reduce friction.

## Success Metrics

- Mission timeline export accuracy within ±2 minutes of expected transitions in
  acceptance tests.
- 100% detection of forbidden azimuth windows in synthetic validation missions.
- Operators can create a mission and view degraded/critical timelines via
  Grafana in <10 minutes (measured during UX validation).
- Prometheus metrics enable alerts with <15-second latency when entering a
  critical window.
- At least three end-to-end automated tests cover normal ops, AAR ops, and
  degraded transport scenarios.

## Required Resources and Dependencies

- Satellite orbital slot data or provided POIs/coverage KML files.
- Access to mission planners/SMEs to confirm transition strategies and
  acceptable buffer durations.
- Updates to Grafana dashboards in `monitoring/grafana/provisioning/dashboards/`
  and backend modules in `backend/starlink-location/`.
- Optional math libraries (e.g., `pyproj`) for geodesic calculations.
- CI capacity to run expanded simulation/timeline tests.

## Timeline Estimates

- Phase 1: ~1.5 weeks.
- Phase 2: ~2 weeks (math + data ingestion heavy).
- Phase 3: ~2 weeks.
- Phase 4: ~1.5 weeks.
- Phase 5: ~1 week. **Total:** ~8 weeks, assuming two developers alternating
  between backend and dashboard work.
