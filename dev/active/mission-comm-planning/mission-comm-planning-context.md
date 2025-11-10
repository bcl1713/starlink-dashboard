# Mission Communication Planning Context

Last Updated: 2025-11-10

## Purpose

Enable pre-flight mission planning that predicts communication degradation
across three onboard transports by analyzing timed flight routes, satellite
geometries, and operational constraints (AAR, takeoff/landing buffers,
transition points).

## Key Components & Files

### Completed (Phase 1)
- `backend/starlink-location/app/mission/models.py` – Pydantic models for Mission, TransportConfig, XTransition, KaOutage, AARWindow, KuOutageOverride, TimelineSegment, TimelineAdvisory, MissionTimeline
- `backend/starlink-location/app/mission/storage.py` – Portable mission persistence (JSON + SHA256 checksums)
- `backend/starlink-location/tests/unit/test_mission_*.py` – 42 passing unit tests
- `data/missions/` – Mission storage directory (auto-created)
- `dev/active/mission-comm-planning/PHASE-1-COMPLETION.md` – Detailed Phase 1 report

### In Progress / Planned
- `backend/starlink-location/app/mission/routes.py` – CRUD endpoints (Phase 1 continuation)
- `backend/starlink-location/app/mission/satellites/` – Geometry engine (Phase 2)
- `backend/starlink-location/app/mission/timeline.py` – Timeline engine (Phase 3)
- `frontend/mission-planner/` (new) – UI for mission configuration
- `monitoring/grafana/provisioning/dashboards/` – Mission timeline panel updates (Phase 4)

### Foundation Systems
- `backend/starlink-location/` – FastAPI service hosting mission APIs, simulation, metrics exporters
- `data/routes/` + `/data/sim_routes/` – Input KML files with timing metadata already supported
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` – Primary visualization to extend
- `docs/ROUTE-TIMING-GUIDE.md`, `docs/METRICS.md`, `docs/ROUTE-API-SUMMARY.md` – Foundational APIs
- `dev/active/eta-route-timing/` – Previous work that established the timing engine we depend on

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
   as the default footprint set. When alternative satellites are needed, fall
   back to math-based coverage estimates unless planners supply another KMZ.
3. **Planner workflow:** Provide a mission-planning GUI (Grafana panel or
   standalone web UI) backed by the same APIs used for routes/POIs so planners
   rarely touch raw JSON.
4. **Airports:** Departure and arrival POIs already exist and are properly
   labeled inside the KML—no extra generation needed.
5. **Schedule volatility:** Plans rarely change but departure times can slip.
   Customer deliverables must show timestamps in UTC (Zulu), Eastern (DST-aware
   for the mission date), and relative T+HH:MM. Live dashboards should
   automatically align to actual time/position vs. the plan.

## Open Questions

- None at this time.
