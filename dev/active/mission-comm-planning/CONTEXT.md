# Context for mission-comm-planning

**Branch:** `feature/mission-comm-planning`
**Folder:** `dev/active/mission-comm-planning/`
**Last Updated:** 2025-11-14

---

## Background

Mission communication planning is critical for flight operations because the aircraft depends on three independent satellite communication transports with different coverage, constraints, and failure modes. Planners must predict degradation windows before flight to prepare operators for handoff procedures and potential communication blackouts. This feature enables pre-flight mission planning that:

- Merges timed flight routes with satellite geometries and operational constraints
- Predicts degradation/critical communication windows
- Generates customer-facing timeline briefings with timestamps in multiple timezones
- Surfaces data to Grafana for live monitoring and alerting
- Exports CSV/XLSX/PDF formats for customer delivery

**Why now:** Phases 1–3 are production-ready. Phase 4 (Grafana visualization) unlocks live operator awareness, and Phase 5 (hardening/docs) ensures sustainable operations.

---

## Relevant Code Locations

**Core mission modules:**
- `backend/starlink-location/app/mission/models.py` — Pydantic data models (Mission, TimelineSegment, etc.)
- `backend/starlink-location/app/mission/storage.py` — Portable JSON-based persistence
- `backend/starlink-location/app/mission/routes.py` — CRUD/activation endpoints
- `backend/starlink-location/app/mission/state.py` — Transport availability state machine
- `backend/starlink-location/app/mission/timeline.py` — Timeline segmentation logic
- `backend/starlink-location/app/mission/timeline_service.py` — End-to-end timeline computation
- `backend/starlink-location/app/mission/exporter.py` — CSV/XLSX/PDF export generators

**Satellite geometry & rules:**
- `backend/starlink-location/app/satellites/catalog.py` — Satellite definitions (X/Ka/Ku)
- `backend/starlink-location/app/satellites/geometry.py` — ECEF, azimuth/elevation calculations
- `backend/starlink-location/app/satellites/coverage.py` — Ka coverage sampling
- `backend/starlink-location/app/satellites/rules.py` — Constraint evaluation engine
- `backend/starlink-location/app/satellites/kmz_importer.py` — HCX KMZ ingest with IDL handling

**UI & integration:**
- `backend/starlink-location/app/api/ui.py` — Mission Planner GUI (lines 1775–2964)
- `backend/starlink-location/app/api/pois.py` — POI filtering with mission scoping
- `backend/starlink-location/app/models/poi.py` — POI model with mission_id support
- `backend/starlink-location/app/services/poi_manager.py` — POI lifecycle management

**Metrics & monitoring:**
- `backend/starlink-location/app/core/metrics.py` — Prometheus gauge registration
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` — Primary dashboard (to be extended)

**Tests:**
- `backend/starlink-location/tests/unit/test_mission_*.py` — 87+ unit tests
- `backend/starlink-location/tests/integration/test_mission_routes.py` — 33+ integration tests
- `backend/starlink-location/tests/unit/test_satellite_*.py` — 75+ satellite tests

---

## Dependencies

**External APIs & Services:**
- Prometheus `/metrics` endpoint for gauge registration and querying
- Grafana dashboard provisioning (JSON-based)
- FastAPI for backend endpoints
- Pydantic v2 for data validation
- pandas/openpyxl/reportlab for export generation
- pyproj/pymap3d for geodetic calculations

**Environment Variables:**
- `STARLINK_MODE` — "simulation" or "live" (affects telemetry sources)
- `PROMETHEUS_RETENTION` — metrics retention period (default: 1y)

**Feature Flags:**
- None currently; all mission features are always-on after activation

**Upstream Dependencies:**
- Route system: `/api/routes`, `/api/routes/{id}`, timed KML parsing
- POI system: `/api/pois`, POI projection to route
- Flight Status system: FlightStateManager, flight phases (pre_departure/in_flight/post_arrival)
- ETA service: RouteETACalculator for timing computations

---

## Constraints & Assumptions

**Constraints:**
- Mission storage must be portable (flat JSON files in `data/missions/`) for staging→production workflows
- Only one mission can be active at a time (global `active_mission_id`)
- Timeline recompute must complete in <1 second for responsive UI
- Grafana panels must query live `/api/missions/active/timeline` endpoints
- X-Band azimuth constraints are X-only; Ka/Ku are not affected

**Assumptions:**
- Timed KML routes are already available and properly formatted
- Satellite catalog (HCX KMZ for Ka, orbital POIs for X) will be provided
- Planners have access to mission planner GUI at `/ui/mission-planner`
- Operators use Grafana for real-time monitoring
- Customer deliverables are one-way exports (CSV/XLSX/PDF); no live customer dashboards

---

## Risks

**Risk 1: Azimuth calculation accuracy**
- *Impact:* Incorrect degradation predictions could lead to operator surprise
- *Mitigation:* Use vetted ECEF formulas, unit test against known coordinates, compare with external tools

**Risk 2: IDL polygon handling complexity**
- *Impact:* False coverage gaps when HCX polygons cross ±180°
- *Mitigation:* Ka coverage sampler now IDL-aware; extensive test coverage for wrap scenarios

**Risk 3: Grafana dashboard complexity + Cross-container file access**
- *Impact:* Panel configuration errors could break live monitoring; Grafana cannot access backend filesystem directly
- *Mitigation:* Version-control all dashboard JSON, test overlay layers in staging before production; expose satellite coverage files via FastAPI static file serving at `/data/sat_coverage/` endpoint (Architecture decision documented below)

**Risk 4: Performance under high mission load**
- *Impact:* Timeline recompute >1s could slow planner workflow
- *Mitigation:* Profile and optimize critical paths; use caching for satellite look-angles

**Risk 5: Test isolation issues**
- *Impact:* Intermittent test failures in full suite (pre-existing)
- *Mitigation:* ETA service fixture initialization, prometheus registry reset; documented in STATUS.md

---

## Testing Strategy

**Done and verified means:**

1. **Unit Tests Passing:**
   - All `tests/unit/test_mission_*.py` pass (87+ tests)
   - All `tests/unit/test_satellite_*.py` pass (75+ tests)
   - Command: `docker compose exec starlink-location python -m pytest tests/unit/ -v`

2. **Integration Tests Passing:**
   - All `tests/integration/test_mission_*.py` pass (33+ tests)
   - Command: `docker compose exec starlink-location python -m pytest tests/integration/ -v`

3. **Manual Verification:**
   - Create mission at `/ui/mission-planner` with sample route + transitions
   - Activate mission; confirm `/api/missions/active/timeline` returns valid JSON
   - Export to CSV/XLSX/PDF; verify timestamps and formatting
   - Check Prometheus metrics at `/metrics` for `mission_*` gauges
   - Verify Grafana panels display without errors

4. **Phase 4 Verification (Grafana):**
   - Satellite POI layer renders on fullscreen-overview dashboard
   - Coverage overlay (HCX GeoJSON) displays correctly
   - Mission timeline panel shows nominal/degraded/critical intervals
   - Prometheus alert rules trigger when upcoming window <15 min away

5. **Performance Validation:**
   - Benchmark: 10 concurrent missions recompute in <1s
   - Memory usage <500MB during recompute
   - Results logged in `docs/PERFORMANCE-NOTES.md`

---

## References

**Existing Documentation:**
- `dev/active/mission-comm-planning/mission-comm-planning-plan.md` — Full 8-week roadmap (superseded by PLAN.md)
- `dev/active/mission-comm-planning/STATUS.md` — Current implementation state
- `dev/active/mission-comm-planning/SESSION-NOTES.md` — Technical decisions and session logs
- `dev/active/mission-comm-planning/PHASE-1-COMPLETION.md` — Phase 1 completion report

**Design & Architecture:**
- `docs/design-document.md` — System architecture overview
- `docs/ROUTE-TIMING-GUIDE.md` — Timed KML route format and timing extraction
- `docs/METRICS.md` — Prometheus metrics reference

**Related Work:**
- `dev/active/eta-route-timing/` — ETA/flight-phase system (dependency)
- `dev/completed/poi-interactive-management/` — POI system foundations
- `dev/completed/kml-route-import/` — Route import infrastructure

**Grafana & Prometheus:**
- `monitoring/grafana/provisioning/dashboards/` — Dashboard JSON files
- `monitoring/prometheus/` — Prometheus configuration
- `CLAUDE.md` — Project conventions and Docker rebuild workflow

---

## Current Session Highlights

**Phase 3 Status (as of 2025-11-12):**
- Timeline computation, APIs, and exporters fully operational
- HCX/X-Band/AAR POI auto-sync on every mission save
- International Date Line coverage gaps fixed
- Mission-event POIs de-duped and filtered
- 607+ tests passing (99.5% pass rate)

**Outstanding Work:**
- Phase 4: Grafana overlays, timeline panel, alerts (ready to start)
- Phase 5: Scenario tests, performance benchmarks, documentation (ready after Phase 4)

**Next Steps:**
1. Start Phase 4 by wiring `/api/missions/active/timeline` into dashboard
2. Add satellite POI and coverage overlay layers
3. Configure mission timeline panel and Prometheus alerts
4. Update documentation with Grafana workflows

---

## Architecture Decision: Static File Serving for Satellite Coverage

**Problem:** Step 4.1 (Grafana coverage overlays) requires Grafana to access `hcx.geojson` coverage polygons. In Docker Compose, Grafana runs in a separate container with no filesystem access to the starlink-location backend service.

**Solution:** Mount `data/sat_coverage/` directory as static files via FastAPI `StaticFiles` middleware, serving at `http://localhost:8000/data/sat_coverage/`. This allows:

- ✅ Grafana (and any HTTP client) to fetch GeoJSON via HTTP
- ✅ No changes to Grafana configuration
- ✅ Portable across Docker Compose, Kubernetes, bare-metal
- ✅ CORS-enabled by default (existing middleware covers it)

**Implementation:**
- Add `from fastapi.staticfiles import StaticFiles` to `main.py`
- After CORS middleware, mount: `app.mount("/data/sat_coverage", StaticFiles(directory="data/sat_coverage"), name="sat_coverage")`
- Directory is auto-created on startup if missing
- No security implications (coverage data is non-sensitive)

**Tested Verification:**
```bash
curl http://localhost:8000/data/sat_coverage/hcx.geojson | jq '.type'
# Returns: "FeatureCollection"
```

**Related CHECKLIST tasks:** Step 4.1 (Add coverage overlay layer) now includes backend setup with verification curl command.
