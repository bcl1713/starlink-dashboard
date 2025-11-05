# ETA Timing Modes: Implementation Context

**Version:** 1.1.4
**Last Updated:** 2025-11-05 (Session 32 – 14:15 UTC)
**Related Plan:** `eta-timing-modes-plan.md`

---

## Overview

This document provides essential context for implementing the anticipated vs. estimated ETA feature. It serves as a quick reference for developers working on the implementation, containing file locations, key decisions, architectural patterns, and dependencies.

---

## Current Implementation Snapshot (Session 10)

- **POI Visibility Safeguard:** `/api/pois/etas` now re-labels standalone POIs as `route_aware_status="pre_departure"` whenever the aircraft is still in `FlightPhase.PRE_DEPARTURE`. This prevents pre-flight “other” POIs (e.g., HCX swap) from being filtered out of Grafana quick-reference panels that exclude `not_on_route`.
- **Model + Doc Sync:** `POIWithETA` schema and `dev/active/eta-timing-modes/ETA-ARCHITECTURE.md` document the new `pre_departure` route-awareness state so client integrations stay aligned.
- **Regression Guard:** Added `tests/integration/test_pois_quick_reference.py` to reproduce Grafana’s Infinity query and assert the new status/ETA behaviour. Introduced foundational `tests/unit/test_flight_state_manager.py` coverage (singleton, initial state, departure persistence, arrival detection, reset).

### Session 11 Addendum (Tests & API parity)

- **Route Upload Fix:** `/api/routes/upload` now writes to `RouteManager.routes_dir` instead of hard-coded `/data/routes`, restoring test isolation in sandboxed environments.
- **Timing Metadata Alignment:** `RouteDetailResponse` exposes `has_timing_data`, matching the list endpoint. Integration tests updated for UTC-normalised departure times and current point counts.
- **POI API Expectation Sync:** Quick-reference integration test now accepts HTTP 204 deletes, aligned with `DELETE /api/pois/{id}` behaviour.
- **Verification:** `.venv/bin/pytest backend/starlink-location/tests/integration` → `88 passed, 4 skipped` (12.6s). Previous failures resolved.
- **Files Touched:** `backend/starlink-location/app/api/routes.py`, `backend/starlink-location/app/models/route.py`, `backend/starlink-location/tests/integration/test_pois_quick_reference.py`, `backend/starlink-location/tests/integration/test_route_eta.py`.

### Session 13 Addendum (Phase 7 Test Expansion & Metadata Validation)

- **Unit Coverage:** `test_flight_state_manager.py` now exercises persistence guard, in-flight short-circuit, route-less contexts, and thread-safety via `ThreadPoolExecutor`. `test_eta_calculator.py` adds anticipated/estimated projection paths, eta_type metadata assertions, and route-without-timing fallbacks. New suites `test_flight_status_models.py` and `test_poi_eta_models.py` lock in default serialization.
- **Integration Coverage:** Added `tests/integration/test_eta_modes.py` to verify manual depart/arrive transitions, POI ETA metadata, and metrics label propagation. Updated `test_route_endpoints_with_timing.py` to assert `flight_phase`/`eta_mode` on list/detail/activate responses.
- **Timezone Normalisation:** `FlightStateManager` now records timestamps with `datetime.now(timezone.utc)` to eliminate `datetime.utcnow()` warnings and ensure consistent UTC handling.
- **Test Runs:** `.venv/bin/python -m pytest backend/starlink-location/tests/unit/test_flight_state_manager.py`, `.venv/bin/python -m pytest backend/starlink-location/tests/unit/test_eta_calculator.py`, `.venv/bin/python -m pytest backend/starlink-location/tests/unit/test_route_models_with_timing.py backend/starlink-location/tests/unit/test_flight_status_models.py backend/starlink-location/tests/unit/test_poi_eta_models.py`. Full integration pack (flight status, POI stats, quick reference, route endpoints, eta modes) passes under full environment; harness times out locally.
- **Files Touched:** `backend/starlink-location/app/services/flight_state_manager.py`, `app/services/eta_calculator.py` (tests), integration/unit test suites listed above, `dev/active/eta-timing-modes/eta-timing-modes-tasks.md`, `SESSION-NOTES.md`.
- **Pending:** Performance benchmarks (Task 7.6) and documentation updates (Phase 8). Consider migrating remaining `datetime.utcnow()` instances in ancillary services/tests to `datetime.now(timezone.utc)` to silence residual warnings.

**Immediate Next Steps:**
- Execute performance/load checks once we allocate time for Task 7.6 (`eta_calculator` throughput, FlightStateManager overhead, 1000 POI waypoint stress test).
- Draft Phase 8 docs (`ROUTE-TIMING-GUIDE.md` additions, new `FLIGHT-STATUS-GUIDE.md`).
- Continue monitoring for timezone-normalisation regressions in services still using `datetime.utcnow()`.

### Session 14 Addendum (Performance Benchmarks & Metrics Coverage)

- **Integration Fallbacks:** `tests/integration/test_eta_modes.py` now seeds temporary POIs per test to ensure Prometheus exports `eta_type` labels even when no route is active; added coverage for timing-less routes and route-change resets.
- **Performance Suite:** Introduced `tests/unit/test_performance_metrics.py` to benchmark ETA calculations across ~1.1k POIs on a 1.2k-waypoint route, measure `FlightStateManager.check_departure` overhead, and stress rapid transition loops.
- **UTC Alignment:** Updated `tests/unit/test_flight_state_manager.py` fixtures to use `datetime.now(timezone.utc)`; resolved naive vs. aware subtraction errors observed in the earlier run.
- **Task Tracker:** Phase 7 task list now marks integration/performance items complete; Phase 7.7 (full-suite pytest) recorded with unit/integration commands.
- **Verification Runs:** `.venv/bin/python -m pytest backend/starlink-location/tests/unit/test_performance_metrics.py`, `.venv/bin/python -m pytest backend/starlink-location/tests/integration/test_eta_modes.py`, `.venv/bin/python -m pytest -q backend/starlink-location/tests/unit`, `.venv/bin/python -m pytest -q backend/starlink-location/tests/integration` (warnings remain for services still emitting `datetime.utcnow()`).
- **Open Risk:** Deprecation warnings from core services (`eta_calculator`, `poi_manager`, `geojson`) still reference `datetime.utcnow()`; plan to sweep during Phase 8 documentation/cleanup.

**Next Focus:**
- Phase 8 documentation updates (`docs/ROUTE-TIMING-GUIDE.md`, new `dev/active/eta-timing-modes/FLIGHT-STATUS-GUIDE.md`, `CLAUDE.md` refresh).
- Optional follow-up to replace remaining `datetime.utcnow()` usage outside the main flight-state path.

### Session 12 Addendum (Flight Status APIs & Countdown Visuals)

- **FlightStateManager Upgrades:** Route context updates now reset state on activation and expose scheduled departure/arrival along with `active_route_id` metadata for clients.
- **Manual Triggers:** New `/api/flight-status/depart` and `/api/flight-status/arrive` endpoints wrap the dedicated `trigger_*` helpers so dashboards/tests can flip phases with explicit timestamps.
- **Metrics & Stats:** `starlink_time_until_departure_seconds` feeds countdown panels; POI stats endpoints return `eta_type` and `flight_phase`, aligning with the Prometheus label set.
- **Dashboard Styling:** Overview, fullscreen, and POI Management dashboards render ETA mode badges (`PLANNED` vs `LIVE`) and include the departure countdown stat.
- **Testing:** Unit coverage now exercises route context resets + manual triggers, while integration tests cover the new flight-status endpoints and stats responses.
- **State:** Awaiting `pytest` run inside Docker/venv (host lacks pytest). No functional blockers; optional countdown visibility remains a nice-to-have.

**Next Immediate Steps (Session 12):**
- Run `docker compose exec starlink-location pytest backend/starlink-location/tests/...` once pytest is available to validate new suites.
- Decide whether to add countdown panel conditional visibility or keep the current "Departed" fallback.
- Monitor for additional FlightStateManager edge cases (thread-safety test still pending).

### Session 32 Addendum (Metrics Exporter, Documentation, Final Review Prep)

- **Metrics Exporter Hardening:** `metrics_export.get_metrics` seeds default cruise speed when telemetry speed falls below 0.5 kn and fetches the current `FlightStateManager` snapshot so Prometheus always emits `eta_type` labels. FastAPI `/metrics` now delegates to the exporter, which keeps scrapes accurate even when background updates are disabled.
- **Documentation Sweep:** Added the ETA mode primer to `docs/ROUTE-TIMING-GUIDE.md`, published `dev/active/eta-timing-modes/FLIGHT-STATUS-GUIDE.md`, refreshed `CLAUDE.md`, and created `dev/active/eta-timing-modes/flight-status-migration-notes.md`. `docs/design-document.md` now includes the flight-state architecture summary.
- **Task & Status Tracking:** `eta-timing-modes-tasks.md` is current through Phase 8 Task 8.6; final review items live in `dev/active/eta-timing-modes/final-review-checklist.md`.
- **New Tests:** `tests/unit/test_eta_cache_service.py` covers ETACache + ETAHistoryTracker; `tests/unit/test_route_eta_calculator_service.py` validates projections, waypoint/location ETAs, route progress, and cache helpers.
- **Coverage Snapshot:** `.venv/bin/python -m pytest --cov=app --cov-report=term backend/starlink-location/tests -q` → 530 passed / 4 skipped / 1 warning (overall 79 % coverage; ETA modules >95 %).
- **Outstanding:** Prometheus scrape verification must occur in staging (local TestClient run blocked by sandbox writing to `/data`). Optional follow-up: rerun performance suite on production hardware if it deviates from dev environment.
- **Next Actions:** Complete Task 8.7 by (1) validating the staging `/metrics` scrape for `eta_type`, (2) reviewing logs for sensitive data, and (3) performing final code/doc/test sign-off.

### Snapshot from Previous Session (Session 9)

- **Flight-State Surfacing:** `/health` now publishes `flight_phase`, `eta_mode`, scheduled/actual departure timestamps, active route identifiers, and `time_until_departure_seconds` (auto-normalised to UTC). Works in both live and simulation modes.
- **Prometheus Enhancements:** Added `starlink_time_until_departure_seconds` gauge and expanded `starlink_distance_to_poi_meters` to share the `eta_type` label with `starlink_eta_poi_seconds`. The metrics export shim mirrors the new label set.
- **Model Updates:** `RouteTimingProfile` stores observed departure/arrival times + flight status helpers; `POIWithETA` exposes `eta_type`, `is_pre_departure`, and `flight_phase`.
- **API Synchronisation:** Route endpoints return live flight metadata (`flight_phase`, `eta_mode`, actual departure/arrival). `/api/pois/etas` annotates each row with the new fields.
- **Simulation Fixture:** Added `dev/active/eta-timing-modes/future-ksfo-klax.kml` with “Time Over Waypoint” metadata to exercise pre-departure countdowns in simulation.
- **Verification:** Uploading the sample plan, activating it in simulation, and resetting flight status produces `flight_phase=pre_departure` with a positive `time_until_departure_seconds`; once velocity crosses the threshold, the countdown hits zero and phase flips to `in_flight`.
- **Files Touched:** `backend/starlink-location/app/api/health.py`, `backend/starlink-location/app/core/metrics.py`, `backend/starlink-location/app/api/metrics_export.py`, `backend/starlink-location/app/api/pois.py`, `backend/starlink-location/app/api/routes.py`, `backend/starlink-location/app/models/{route,poi}.py`, and the new fixture `dev/active/eta-timing-modes/future-ksfo-klax.kml`.

### Outstanding Work vs. Plan

- **Phase 2 gaps:** Still missing RouteManager hooks directly on `FlightStateManager` and dedicated `/api/flight-status/depart|arrive` shims.
- **Phase 3 gaps:** Need to thread flight-phase annotations deeper into `calculate_poi_metrics()` return payloads for non-API consumers.
- **Phase 5 gaps:** Grafana panels not yet updated to visualise the new countdown/eta-type labels; `starlink_time_until_departure_seconds` still lacks automated coverage.
- **Phase 6 gaps:** POI Management dashboard styling (badges/countdown) remains outstanding.
- **Phase 7 progress:** Initial `FlightStateManager` unit coverage and POI quick-reference regression test landed; remaining cases (time/distance triggers, thread safety, route resets, ETA calculator dual-mode tests) still open.
- **Phase 8:** Documentation updates pending beyond the architecture note adjusted this session.

- **Immediate Next Steps:**
  1. Finish Phase 7 test matrix (remaining `FlightStateManager` edge cases, ETA calculator dual-mode suites, API/integration flows) and run pytest inside the Docker service.
  2. Update Grafana dashboards to consume `time_until_departure_seconds` and `eta_type` once backend metrics stabilise.
  3. Document the simulation validation recipe and KSFO→KLAX sample in `ROUTE-TIMING-GUIDE.md` / new `FLIGHT-STATUS-GUIDE.md`.
  4. Evaluate whether to reintroduce explicit depart/arrive endpoints or document reliance on manual transitions.

---

## Key Files and Locations

### Backend Core Files

**Models:**
- `backend/starlink-location/app/models/route.py` - Route and timing models (MODIFY)
- `backend/starlink-location/app/models/poi.py` - POI and ETA response models (MODIFY)
- `backend/starlink-location/app/models/flight_status.py` - Flight status models (CREATE)

**Services:**
- `backend/starlink-location/app/services/eta_calculator.py` - ETA calculation engine (MODIFY)
- `backend/starlink-location/app/services/route_eta_calculator.py` - Route-specific calculations (READ ONLY)
- `backend/starlink-location/app/services/flight_state_manager.py` - Flight state management (CREATE)
- `backend/starlink-location/app/core/eta_service.py` - ETA service singleton (MODIFY)

**API Endpoints:**
- `backend/starlink-location/app/api/pois.py` - POI CRUD and ETA endpoints (MODIFY)
- `backend/starlink-location/app/api/routes.py` - Route management endpoints (MODIFY)
- `backend/starlink-location/app/api/flight_status.py` - Flight status endpoints (CREATE)

**Metrics:**
- `backend/starlink-location/app/core/metrics.py` - Prometheus metrics definitions (MODIFY)
- `backend/starlink-location/app/api/metrics_export.py` - Metrics endpoint (READ ONLY)

**Application:**
- `backend/starlink-location/main.py` - Application startup and initialization (MODIFY)

### Frontend/Dashboard Files

**Grafana Dashboards:**
- `monitoring/grafana/provisioning/dashboards/poi-management.json` - POI dashboard (MODIFY)
- `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` - Overview dashboard (MODIFY)

### Simulation Fixtures

- `dev/active/eta-timing-modes/future-ksfo-klax.kml` - Sample timed route (KSFO→KLAX) for pre-departure countdown validation

### Documentation Files

**Technical Documentation:**
- `docs/ROUTE-TIMING-GUIDE.md` - Route timing feature guide (MODIFY)
- `dev/active/eta-timing-modes/FLIGHT-STATUS-GUIDE.md` - Flight status user guide (CREATE)
- `dev/active/eta-timing-modes/ETA-ARCHITECTURE.md` - ETA system architecture (READ ONLY)

**Project Documentation:**
- `CLAUDE.md` - Project instructions for Claude Code (MODIFY)
- `README.md` - Project README (READ ONLY)

### Test Files

**Unit Tests:**
- `backend/starlink-location/tests/test_flight_state_manager.py` - Flight state tests (CREATE)
- `backend/starlink-location/tests/test_eta_calculator.py` - ETA calculator tests (MODIFY)
- `backend/starlink-location/tests/test_models.py` - Model validation tests (MODIFY)

**Integration Tests:**
- `backend/starlink-location/tests/integration/test_flight_status_api.py` - API tests (CREATE)
- `backend/starlink-location/tests/integration/test_eta_modes.py` - End-to-end tests (CREATE)

---

## Architectural Decisions

### Decision 1: In-Memory Flight State (No Database)

**Rationale:**
- Flight state is session-based and transient
- No requirement to persist across service restarts
- Simplifies implementation (no migrations)
- Fast access (O(1) lookups)
- Stateless service design

**Trade-offs:**
- Flight state lost on service restart (acceptable)
- Manual departure triggers must be re-applied after restart
- No historical flight state data

**Implementation:**
- Singleton FlightStateManager class
- Thread-safe with locking
- State reset when route changes

---

### Decision 2: Automatic Departure Detection

**Rationale:**
- Reduces manual intervention
- Works for most standard use cases
- Provides fallback for missed manual triggers

**Triggers:**
- Speed-based: Current speed exceeds 50 knots consistently (10+ seconds)
- Manual override: API call to force departure

**Trade-offs:**
- Speed threshold may need tuning for different aircraft types
- Persistent speed check prevents false positives from GPS noise
- Works reliably for typical flight operations
- Clear, intuitive transition point (takeoff roll/climb)

---

### Decision 3: Dual-Mode Calculation in Single Class

**Rationale:**
- Keeps ETA logic centralized
- Reuses existing route-aware calculation code
- Easier to maintain and test
- Single source of truth

**Alternative Considered:**
- Separate AnticipatedETACalculator and EstimatedETACalculator classes
- Rejected: Code duplication, higher complexity

**Implementation:**
- Branch logic based on `flight_state_manager.get_current_phase()`
- Separate private methods: `_calculate_anticipated_eta()` and `_calculate_estimated_eta()`
- Public method remains `calculate_poi_metrics()`
- Off-route projection logic already exists in RouteETACalculator (reuse for estimated mode)

---

### Decision 4: Intelligent Speed Blending for Current Segment

**Rationale:**
- Current speed reflects real-time conditions (weather, wind, etc.)
- Expected speed based on progress provides stability
- Blending both gives realistic ETAs without excessive volatility
- More accurate than using current speed alone for entire remaining route

**Implementation:**
- Future route segments: Use calculated/scheduled segment speeds
- Current segment: Average current speed with expected speed weighted by progress
- Off-route POIs: Project to route first, then apply same speed logic
- Projection logic already exists in RouteETACalculator

**Example:**
- Current segment: 100nm at planned 400 knots
- Already traveled 75nm (75% complete)
- Current actual speed: 380 knots
- Expected speed based on progress: 400 knots
- Blended speed for remaining 25nm: (380 + 400) / 2 = 390 knots

---

### Decision 5: Optional eta_type Field (Backward Compatibility)

**Rationale:**
- Existing API clients shouldn't break
- Progressive enhancement approach
- Graceful degradation when timing data absent

**Implementation:**
- `eta_type` defaults to "estimated" if not set
- All new fields are optional with sensible defaults
- API documentation clearly marks new fields

---

### Decision 6: Prometheus Metric Labels (Not New Metrics)

**Rationale:**
- Maintains existing metric names
- Avoids dashboard query rewrites
- Easier to filter by ETA type in Grafana

**Implementation:**
- Add `eta_type="anticipated"` or `eta_type="estimated"` labels
- Existing queries work without modification
- New queries can filter by label

---

## Data Flow Diagrams

### Pre-Departure Flow (Anticipated ETAs)

```
┌──────────────────────────────────────────────────────────────┐
│                    Telemetry Update Cycle                     │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              FlightStateManager.check_phase()                 │
│  - Check current speed vs. 50 knot threshold                  │
│  - Verify speed below threshold                               │
│  Result: phase = PRE_DEPARTURE                                │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│         ETACalculator.calculate_poi_metrics()                 │
│  - Receives flight_state_manager parameter                    │
│  - Queries current phase: PRE_DEPARTURE                       │
│  - Branches to _calculate_anticipated_eta()                   │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│         _calculate_anticipated_eta()                          │
│  - Uses route timing data (scheduled speeds)                  │
│  - Calculates from scheduled departure time                   │
│  - Returns: eta_seconds, eta_type="anticipated"               │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                  ETAService.update_metrics()                  │
│  - Receives metrics dict with eta_type                        │
│  - Sets Prometheus metric with label:                         │
│    starlink_eta_poi_seconds{eta_type="anticipated"}           │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                      Grafana Dashboard                         │
│  - Queries metric with eta_type="anticipated"                 │
│  - Displays blue background + "PLANNED" badge                 │
└──────────────────────────────────────────────────────────────┘
```

### Post-Departure Flow (Estimated ETAs)

```
┌──────────────────────────────────────────────────────────────┐
│                    Telemetry Update Cycle                     │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│              FlightStateManager.check_phase()                 │
│  - Detects: speed > 50 knots consistently                     │
│  - Tracks: speed above threshold for 10+ seconds              │
│  - Transitions: PRE_DEPARTURE → IN_FLIGHT                     │
│  Result: phase = IN_FLIGHT                                    │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│         ETACalculator.calculate_poi_metrics()                 │
│  - Receives flight_state_manager parameter                    │
│  - Queries current phase: IN_FLIGHT                           │
│  - Branches to _calculate_estimated_eta()                     │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│         _calculate_estimated_eta()                            │
│  - For future segments: Use calculated/scheduled speed        │
│  - For current segment: Blend current + expected speed        │
│  - For off-route POIs: Project to route, apply same logic    │
│  - Calculates from current position and time                  │
│  - Returns: eta_seconds, eta_type="estimated"                 │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                  ETAService.update_metrics()                  │
│  - Receives metrics dict with eta_type                        │
│  - Sets Prometheus metric with label:                         │
│    starlink_eta_poi_seconds{eta_type="estimated"}             │
└────────────────────┬─────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────────────┐
│                      Grafana Dashboard                         │
│  - Queries metric with eta_type="estimated"                   │
│  - Displays green background + "LIVE" badge                   │
└──────────────────────────────────────────────────────────────┘
```

---

## Key Dependencies

### Internal Dependencies (Within Backend)

**Phase Dependencies:**
- Phase 2 depends on Phase 1 (models must exist before state manager)
- Phase 3 depends on Phase 2 (ETA calculator needs state manager)
- Phase 4 depends on Phase 3 (API needs updated calculator)
- Phase 5 depends on Phase 4 (metrics need updated API)
- Phase 6 depends on Phase 5 (dashboard needs metrics)

**Module Dependencies:**
```
flight_state_manager.py
  └─ depends on: models/flight_status.py

eta_calculator.py
  └─ depends on: flight_state_manager.py
  └─ depends on: models/route.py (RouteTimingProfile)

eta_service.py
  └─ depends on: eta_calculator.py
  └─ depends on: flight_state_manager.py

api/pois.py
  └─ depends on: eta_service.py
  └─ depends on: models/poi.py (POIWithETA)

api/flight_status.py
  └─ depends on: flight_state_manager.py
  └─ depends on: models/flight_status.py
```

### External Dependencies

**Python Packages:**
- `pydantic>=2.0` - Data validation and models
- `fastapi>=0.100` - API framework
- `prometheus-client>=0.17` - Metrics
- `pytest>=7.0` - Testing

**Infrastructure:**
- Docker Compose - Container orchestration
- Prometheus - Metrics storage
- Grafana - Visualization

**Data Dependencies:**
- KML files must have timing metadata for anticipated mode
- Active route must be set for route-aware calculations
- Current position telemetry must be available

---

## Configuration and Environment

### Environment Variables (No Changes Required)

The feature uses existing configuration:
- `STARLINK_MODE` - simulation or live (no change)
- `PROMETHEUS_RETENTION` - metrics retention (no change)

### Configuration Constants (In Code)

**Flight State Manager:**
```python
# app/services/flight_state_manager.py
DEPARTURE_SPEED_THRESHOLD_KNOTS = 50.0  # 50 knots
DEPARTURE_SPEED_PERSISTENCE_SECONDS = 10  # 10 seconds above threshold
ARRIVAL_DISTANCE_THRESHOLD_M = 100  # 100 meters
ARRIVAL_DWELL_TIME_SECONDS = 60  # 60 seconds
```

**ETA Calculator:**
```python
# app/services/eta_calculator.py
# Existing constants remain unchanged
SMOOTHING_DURATION_SECONDS = 120.0  # 2 minutes
POI_DISTANCE_THRESHOLD_M = 100.0  # 100 meters
```

---

## Testing Strategy

### Unit Test Coverage

**FlightStateManager (15 tests):**
- State initialization (default = PRE_DEPARTURE)
- Automatic departure detection (speed-based)
- Speed persistence tracking (prevent false positives)
- Manual departure trigger
- Automatic arrival detection
- Manual arrival trigger
- State reset
- Thread safety (concurrent access)
- Edge cases (no active route, speed fluctuations)

**ETACalculator (20 tests):**
- Anticipated ETA calculation (pre-departure)
- Estimated ETA calculation (in-flight)
- Speed blending for current segment
- Speed calculation for future segments
- Off-route POI projection and calculation
- Mode switching on flight phase change
- Fallback when no timing data available
- Route-aware anticipated calculation
- Edge cases (zero speed, no route, passed POIs)

**Models (10 tests):**
- RouteTimingProfile validation
- FlightStatusResponse serialization
- POIWithETA with eta_type field
- Field defaults and optional fields
- JSON schema generation

**API Endpoints (15 tests):**
- GET /api/routes/flight-status
- POST /api/routes/flight-status/depart
- POST /api/routes/flight-status/arrive
- POST /api/routes/flight-status/reset
- GET /api/pois/etas (with eta_type)
- GET /api/routes/active/timing (with flight status)

### Integration Test Scenarios

**Scenario 1: Pre-Departure → In-Flight → Post-Arrival**
1. Upload route with timing data
2. Activate route
3. Verify flight status = PRE_DEPARTURE
4. Verify ETAs are anticipated
5. Trigger departure (manual or automatic)
6. Verify flight status = IN_FLIGHT
7. Verify ETAs are estimated
8. Reach final waypoint
9. Verify flight status = POST_ARRIVAL

**Scenario 2: Manual Override Flow**
1. Upload route, verify PRE_DEPARTURE
2. Call POST /api/routes/flight-status/depart
3. Verify immediate transition to IN_FLIGHT
4. Verify ETAs switch to estimated
5. Call POST /api/routes/flight-status/reset
6. Verify return to PRE_DEPARTURE

**Scenario 3: No Timing Data Fallback**
1. Upload route without timing metadata
2. Activate route
3. Verify anticipated mode is disabled
4. Verify all ETAs use estimated mode
5. Verify no errors or crashes

### Performance Benchmarks

**Target Metrics:**
- ETA calculation time: <50ms per POI (no change from current)
- Flight state check overhead: <1ms per telemetry cycle
- Metric update frequency: 1 second (no change)
- API response time: <100ms (95th percentile)

**Load Testing:**
- Test with 1000+ POIs
- Test with 1000+ waypoint routes
- Test rapid state transitions (stress test)

---

## Common Pitfalls and Gotchas

### Pitfall 1: Forgetting to Rebuild Docker Container

**Problem:**
Python code changes don't take effect until container is rebuilt.

**Solution:**
Always run after modifying .py files:
```bash
docker compose down && docker compose build --no-cache && docker compose up -d
```

### Pitfall 2: State Lost on Service Restart

**Problem:**
Flight state is in-memory and lost when service restarts.

**Solution:**
- This is expected behavior (by design)
- Document in user guide
- Add warning in API docs
- Consider adding state persistence in future if needed

### Pitfall 3: Timezone Issues with Departure Times

**Problem:**
KML timing data uses UTC, but local time comparisons may fail.

**Solution:**
- Always use UTC for all time comparisons
- Convert current time to UTC before comparison
- Document timezone requirements

### Pitfall 4: Race Condition in State Transitions

**Problem:**
Concurrent telemetry updates may cause state inconsistency.

**Solution:**
- Use thread locks in FlightStateManager
- Make state transitions atomic
- Test with concurrent access

### Pitfall 5: Dashboard Query Performance

**Problem:**
Adding `eta_type` label may slow down Grafana queries.

**Solution:**
- Test query performance with labels
- Use query caching where possible
- Optimize label cardinality (only 2 values: anticipated/estimated)

---

## Debug and Troubleshooting

### How to Verify Flight State

```bash
# Check current flight status
curl http://localhost:8000/api/routes/flight-status | jq .

# Example response:
# {
#   "route_id": "route-001",
#   "flight_phase": "in_flight",
#   "scheduled_departure_time": "2025-10-27T16:45:00Z",
#   "actual_departure_time": "2025-10-27T16:47:32Z",
#   "time_since_departure_seconds": 450
# }
```

### How to Verify ETA Type in Metrics

```bash
# Check Prometheus metrics endpoint
curl http://localhost:8000/metrics | grep starlink_eta_poi_seconds

# Look for eta_type label:
# starlink_eta_poi_seconds{name="KADW",category="airport",eta_type="anticipated"} 1800.0
# starlink_eta_poi_seconds{name="PHNL",category="airport",eta_type="estimated"} 3600.0
```

### How to Verify Dashboard Queries

```bash
# Query Prometheus directly
curl 'http://localhost:9090/api/v1/query?query=starlink_eta_poi_seconds{eta_type="anticipated"}' | jq .

# Check Grafana dashboard JSON
cat monitoring/grafana/provisioning/dashboards/poi-management.json | jq '.panels[] | select(.title == "Next Destination")'
```

### Logs to Monitor

**Backend logs:**
```bash
docker logs -f starlink-location | grep -E "flight_state|eta_type|departure|arrival"
```

**Expected log patterns:**
- `Flight state transitioned: PRE_DEPARTURE → IN_FLIGHT`
- `Departure detected: automatic (time-based)`
- `ETA type: anticipated (flight phase: pre_departure)`
- `ETA type: estimated (flight phase: in_flight)`

---

## Code Style and Patterns

### Naming Conventions

**Classes:**
- PascalCase: `FlightStateManager`, `FlightPhase`

**Methods:**
- snake_case: `get_current_phase()`, `trigger_departure()`

**Constants:**
- UPPER_SNAKE_CASE: `DEPARTURE_TIME_BUFFER_SECONDS`

**File names:**
- snake_case: `flight_state_manager.py`, `flight_status.py`

### Design Patterns Used

**Singleton Pattern:**
- `FlightStateManager` (global flight state)
- `ETAService` (metric coordination)

**State Pattern:**
- Flight phase state machine (PRE_DEPARTURE, IN_FLIGHT, POST_ARRIVAL)

**Strategy Pattern:**
- Anticipated vs. Estimated ETA calculation strategies

**Dependency Injection:**
- Pass `flight_state_manager` to calculator methods

### Type Hints

Use type hints for all function signatures:
```python
def calculate_poi_metrics(
    self,
    current_lat: float,
    current_lon: float,
    pois: list[POI],
    speed_knots: Optional[float] = None,
    active_route: Optional["ParsedRoute"] = None,
    flight_state_manager: Optional[FlightStateManager] = None,
) -> dict[str, dict]:
```

### Error Handling

**Graceful Degradation:**
- If flight state unavailable, default to estimated mode
- If timing data missing, disable anticipated mode
- Log warnings, don't crash

**Example:**
```python
try:
    current_phase = flight_state_manager.get_current_phase()
except Exception as e:
    logger.warning(f"Failed to get flight phase: {e}")
    current_phase = FlightPhase.IN_FLIGHT  # Default to estimated mode
```

---

## Quick Reference Commands

### Development Workflow

```bash
# 1. Make code changes
vim backend/starlink-location/app/services/flight_state_manager.py

# 2. Rebuild Docker (REQUIRED)
docker compose down && docker compose build --no-cache && docker compose up -d

# 3. Wait for services to be healthy
docker compose ps

# 4. Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/api/routes/flight-status

# 5. Run tests
docker compose exec starlink-location pytest tests/

# 6. Check logs
docker logs -f starlink-location
```

### Testing Commands

```bash
# Run specific test file
docker compose exec starlink-location pytest tests/test_flight_state_manager.py -v

# Run tests with coverage
docker compose exec starlink-location pytest --cov=app tests/

# Run integration tests
docker compose exec starlink-location pytest tests/integration/ -v
```

### Debugging Commands

```bash
# Check current flight status
curl http://localhost:8000/api/routes/flight-status

# Trigger manual departure
curl -X POST http://localhost:8000/api/routes/flight-status/depart

# Get POI ETAs with type
curl http://localhost:8000/api/pois/etas | jq '.pois[] | {name, eta_seconds, eta_type}'

# Check Prometheus metrics
curl http://localhost:8000/metrics | grep flight_phase
```

---

## Related Documentation

**Internal Documentation:**
- `dev/active/eta-timing-modes/ETA-ARCHITECTURE.md` - ETA system architecture overview
- `docs/ROUTE-TIMING-GUIDE.md` - Route timing feature guide
- `docs/design-document.md` - Overall system design

**External Resources:**
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)
- [Prometheus Python Client](https://github.com/prometheus/client_python)
- [Grafana Dashboard JSON Model](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/view-dashboard-json-model/)

---

## Contact and Questions

For questions about this implementation:
1. Review the plan: `eta-timing-modes-plan.md`
2. Check related docs: `dev/active/eta-timing-modes/ETA-ARCHITECTURE.md`
3. Consult project guide: `CLAUDE.md`

---

**Last Updated:** 2025-11-04
**Document Version:** 1.0.0
**Plan Version:** 1.0.0
