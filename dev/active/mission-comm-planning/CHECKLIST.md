# Checklist for mission-comm-planning

**Branch:** `feature/mission-comm-planning` **Folder:**
`dev/active/mission-comm-planning/` **Status:** In Progress **Current Phase:**
Phase 4 (Grafana Visualization) & Phase 5 (Hardening)

> This checklist assumes execution proceeds through Phase 4 and Phase 5
> sequentially. Phases 1–3 are already complete with 607+ passing tests.

---

## Initialization

- [x] Branch created and on correct branch (`feature/mission-comm-planning`)
- [x] Dev folder exists at `dev/active/mission-comm-planning/`
- [x] All Phase 1–3 code committed and passing tests
- [x] Docker environment healthy (all services running)

---

## Phase 4 — Visualization & Customer Outputs

### 4.1 Grafana Map Overlays

- [x] **Wire satellite POIs to Fullscreen Overview dashboard** _(User to
      execute - backend endpoint ready)_
  - [x] Edit
        `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`
  - [x] Add new panel with ID not conflicting with existing panels
  - [x] Panel type: Geomap
  - [x] Data source: Prometheus or Infinity datasource
  - [x] Query: Call `/api/missions/active/satellites` endpoint (implementation
        complete)
  - [x] Layer type: Points (for satellite locations)
  - [x] Symbol: Satellite icon or marker
  - [x] Test: Activate a mission and verify satellite POIs appear on map

- [x] **Implement `/api/missions/active/satellites` endpoint** _(Completed;
      executed before wiring due to API dependency)_
  - [x] Location: `backend/starlink-location/app/mission/routes.py`
  - [x] Add new route handler:

    ```python
    @router.get("/missions/active/satellites")
    async def get_active_mission_satellites():
        """Return satellite POIs for active mission in Grafana-compatible format."""
        # Fetch active mission
        # Extract satellite definitions from mission.transports
        # Return as GeoJSON FeatureCollection with satellite metadata
    ```

  - [x] Test: `curl http://localhost:8000/api/missions/active/satellites`
        returns valid GeoJSON
  - [x] Commit:
        `feat: add /api/missions/active/satellites endpoint for Grafana overlay`

- [x] **Add coverage overlay layer (HCX GeoJSON)** ✅ COMPLETE
  - [x] **Backend setup:** Edit `backend/starlink-location/main.py`
    - [x] Add import: `from fastapi.staticfiles import StaticFiles` ✅ DONE
    - [x] Add static files mount (after CORS middleware) ✅ DONE
    - [x] Initialize HCX coverage on startup ✅ DONE
      - [x] Added HCX coverage initialization in `startup_event()`
      - [x] Backend logs confirm: "HCX coverage loaded: 4 regions"
      - [x] File created: `/app/data/sat_coverage/hcx.geojson` (64K)
    - [x] Rebuilt Docker with full initialization ✅ DONE
    - [x] Verified endpoint returns GeoJSON ✅ DONE
      - Verified:
        `curl http://localhost:8000/data/sat_coverage/hcx.geojson | jq '.type'`
        returns `"FeatureCollection"`
  - [x] Edit Fullscreen Overview dashboard ✅ COMPLETE
  - [x] Add new Geomap panel for coverage ✅ COMPLETE
  - [x] Data source: Backend endpoint
        `http://localhost:8000/data/sat_coverage/hcx.geojson` ✅ COMPLETE
    - ℹ️ This URL serves the HCX coverage file via FastAPI static files mount
      (no direct filesystem access needed)
  - [x] Layer type: GeoJSON overlay ✅ COMPLETE
  - [x] Styling: Semi-transparent fill (20–30% opacity) with Ka-specific colors
        (AOR/POR/IOR) ✅ COMPLETE
  - [x] Test: Verify HCX polygons display without overlapping waypoints ✅
        COMPLETE

- [x] **Add AAR & transition POI markers**
  - [x] These are already generated as mission-event POIs
  - [x] Add panel querying
        `/api/pois?mission_id=<active_mission_id>&category=mission-event`
  - [x] Filter and display only AAR and X-Band transition POIs
  - [x] Test: Create mission with AAR window and transitions; verify markers
        appear

- [x] **Update `monitoring/README.md`** ✅ COMPLETE
  - [x] Document new Grafana plugins or permissions needed
  - [x] Document layer setup and configuration steps
  - [x] Include troubleshooting and verification procedures
  - [x] Commit: `docs: update Grafana setup for mission overlays`

### 4.2 Mission Timeline Panel & Alerts

- [x] **Create Prometheus alert rules**
  - [x] File: `monitoring/prometheus/rules/mission-alerts.yml` (create if
        missing)
  - [x] Rule 1: Alert when degraded window <15 minutes away

    ```yaml
    alert: MissionDegradedWindowApproaching
    expr: mission_next_conflict_seconds{status="degraded"} < 900
    for: 1m
    labels:
      severity: warning
    annotations:
      summary:
        "Degraded window approaching for mission {{ $labels.mission_id }}"
      description: "Degraded window in {{ humanize $value }}s"
    ```

  - [x] Rule 2: Alert when critical window <15 minutes away

    ```yaml
    alert: MissionCriticalWindowApproaching
    expr: mission_next_conflict_seconds{status="critical"} < 900
    for: 1m
    labels:
      severity: critical
    ```

  - [x] Validate rules:
        `docker compose exec prometheus promtool check rules /etc/prometheus/rules/mission-alerts.yml`
  - [x] Test: Create mission with known degraded window; verify alert fires
        (rules loaded and healthy)

- [x] **Update Grafana dashboard variables**
  - [x] Deferred: Dashboard variable filtering not practical with current refresh options
  - [x] Future work: Ensure all mission-aware API endpoints support filtering on active mission
  - [x] Once dynamic variable refresh is available, revisit this requirement

- [x] **Test dashboard end-to-end**
  - [x] Start Docker environment: `docker compose up -d`
  - [x] Navigate to Fullscreen Overview dashboard
  - [x] Create test mission (at least 2 X transitions, 1 Ka coverage gap)
  - [x] Activate mission
  - [x] Verify:
    - [x] Satellite POIs appear on map
    - [x] Coverage overlays visible
    - [x] AAR markers displayed
    - [x] Metrics updated in Prometheus
  - [x] Commit: `chore: complete Phase 4.2 end-to-end dashboard testing`

### 4.2b Mission API Enhancements

- [x] **Implement mission deactivation endpoint**
  - [x] File: `backend/starlink-location/app/mission/routes.py`
  - [x] Add new route: `POST /api/missions/active/deactivate`
  - [x] Handler function:
    - [x] Get active mission (or return 404 if none)
    - [x] Get the mission's associated route_id
    - [x] Call `_route_manager.deactivate_route()` if route_id exists
    - [x] Set `mission.is_active = False` and save
    - [x] Call `clear_mission_metrics(mission_id)`
    - [x] Clear `_active_mission_id` global
    - [x] Return 200 with confirmation
  - [x] Error handling: Return 404 if no active mission

- [ ] **Update mission deletion to cascade route deactivation**
  - [ ] File: `backend/starlink-location/app/mission/routes.py`
  - [ ] In `delete_mission_endpoint()`, before deleting mission:
    - [ ] Check if mission has `route_id`
    - [ ] If route_id exists, call `_route_manager.deactivate_route(route_id)`
    - [ ] Continue with existing deletion logic
  - [ ] Verify: Deleting active mission should deactivate its route

- [ ] **Update mission planner UI with deactivation button**
  - [ ] File: `backend/starlink-location/app/api/ui.py`
  - [ ] Add "Deactivate Mission" button next to existing "Activate Mission" button
    - [ ] Only visible when mission is active (`currentMission.is_active === true`)
    - [ ] Button styling: secondary (not danger like delete)
  - [ ] Add `deactivateMission()` function:
    - [ ] Confirm with user: "Deactivate mission X?"
    - [ ] Call `POST /api/missions/active/deactivate`
    - [ ] On success: Set `currentMission.is_active = false`, show success alert
    - [ ] On error: Show error alert with detail
    - [ ] Reload missions list
  - [ ] Update button state handler to show/hide deactivate button based on `is_active`
  - [ ] Test: Activate mission → Deactivate button visible → Click deactivate → Mission no longer active

- [ ] **Write tests**
  - [ ] File: `backend/starlink-location/tests/integration/test_mission_routes.py`
  - [ ] Test: Deactivate active mission returns 200
  - [ ] Test: Route is deactivated when mission is deactivated
  - [ ] Test: Mission metrics are cleared after deactivation
  - [ ] Test: No active mission returns 404 on deactivate attempt
  - [ ] Test: Deleting active mission deactivates its route
  - [ ] Run all tests: `docker compose exec starlink-location python -m pytest tests/ -v`

- [ ] **Commit**
  - [ ] Commit message: `feat: add mission deactivation with route cascade and UI button`

### 4.3 UX Validation with Stakeholders

- [ ] **Schedule validation session**
  - [ ] Identify 1–2 mission planners or operators
  - [ ] Schedule 45–60 minute hands-on session
  - [ ] Prepare test mission with real-world-like parameters (e.g., Leg 6 Rev 6
        data)

- [ ] **Run validation workflows**
  - [ ] Create new mission from scratch
  - [ ] Add X transitions with lat/lon coordinates
  - [ ] Schedule Ka outages
  - [ ] Define AAR windows
  - [ ] Activate and view timeline
  - [ ] Export to PDF/CSV and review formatting
  - [ ] Check Grafana display accuracy

- [ ] **Capture feedback**
  - [ ] Document in `dev/active/mission-comm-planning/SESSION-NOTES.md`
  - [ ] Note any UI/UX improvements needed
  - [ ] Record dashboard panel feedback
  - [ ] Collect export format feedback

- [ ] **Iterate on feedback**
  - [ ] Address high-priority UX issues (e.g., form validation, labeling)
  - [ ] Low-priority cosmetic items can defer to Phase 5

- [ ] **Commit feedback and updates**
  - [ ] `chore: capture Phase 4 UX validation feedback in SESSION-NOTES.md`

---

## Phase 5 — Hardening & Ops Readiness

### 5.1 Scenario Regression Tests

- [ ] **Test 1: Normal ops with X transitions**
  - [ ] File:
        `backend/starlink-location/tests/integration/test_mission_scenarios.py`
        (create if missing)
  - [ ] Scenario: Mission with route, 2 X-Band transitions, no AAR
  - [ ] Setup:
    - [ ] Load sample route (cross-country with multiple waypoints)
    - [ ] Add X transition from X-1 to X-2 at waypoint 30%
    - [ ] Add X transition from X-2 back to X-1 at waypoint 70%
  - [ ] Assertions:
    - [ ] Timeline has ≥4 segments (pre-transition, transition1, between,
          transition2, post)
    - [ ] Each X transition has ±15-min degrade buffer
    - [ ] No Ka/Ku degradations (assume nominal coverage)
    - [ ] Export generates without errors
  - [ ] Run test:
        `pytest tests/integration/test_mission_scenarios.py::test_normal_ops_x_transitions -v`

- [ ] **Test 2: Ka coverage gaps**
  - [ ] Scenario: Mission with route crossing POR→AOR boundary, no X transitions
  - [ ] Setup:
    - [ ] Use route that naturally crosses Ka coverage boundary
    - [ ] No manual Ka outages (auto-detected from coverage)
  - [ ] Assertions:
    - [ ] POR→AOR swap event detected
    - [ ] Swap point is at coverage boundary midpoint
    - [ ] X and Ku remain nominal during swap
    - [ ] Swap has <1-minute window
  - [ ] Run test:
        `pytest tests/integration/test_mission_scenarios.py::test_ka_coverage_swap -v`

- [ ] **Test 3: AAR with X azimuth inversion**
  - [ ] Scenario: Mission with AAR window that inverts X azimuth constraints
  - [ ] Setup:
    - [ ] Define mission with normal X assignments
    - [ ] Add AAR window at waypoints 40–60%
    - [ ] Configure azimuth such that normal ops X is blocked during AAR
  - [ ] Assertions:
    - [ ] During AAR, X azimuth rule inverts (315–45° instead of 135–225°)
    - [ ] X becomes degraded during AAR if azimuth within inverted range
    - [ ] Other transports unaffected
    - [ ] AAR window marked as comm blackout (informational)
  - [ ] Run test:
        `pytest tests/integration/test_mission_scenarios.py::test_aar_azimuth_inversion -v`

- [ ] **Test 4: Multi-transport degradation logic**
  - [ ] Scenario: Mission where X and Ka both degrade simultaneously
  - [ ] Setup:
    - [ ] Arrange route + transitions + coverage such that X azimuth conflict
          and Ka gap overlap
  - [ ] Assertions:
    - [ ] Overlapping degradation creates "critical" status (2 transports down)
    - [ ] Prometheus metric `mission_critical_seconds` > 0
    - [ ] Export highlights critical window with dark red background
  - [ ] Run test:
        `pytest tests/integration/test_mission_scenarios.py::test_multi_transport_critical -v`

- [ ] **Commit scenario tests**
  - [ ] `feat: add Phase 5 scenario regression test suite`

### 5.2 Performance Benchmarking

- [ ] **Create benchmark script**
  - [ ] File: `tools/benchmark_mission_timeline.py`
  - [ ] Script:

    ```python
    import time
    import concurrent.futures
    from backend.starlink_location.app.mission import timeline_service

    def benchmark_timeline_recompute(mission_count=10):
        """Measure timeline recompute time and memory for N missions."""
        missions = [create_test_mission() for _ in range(mission_count)]

        start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(timeline_service.compute_mission_timeline, m) for m in missions]
            results = [f.result() for f in futures]
        duration = time.time() - start

        print(f"Recomputed {mission_count} missions in {duration:.2f}s")
        print(f"Average: {duration / mission_count:.3f}s per mission")

        # Memory usage via psutil
        # Record results to docs/PERFORMANCE-NOTES.md
    ```

  - [ ] Run locally: `cd tools && python benchmark_mission_timeline.py`
  - [ ] Target: <1.0s for 10 concurrent missions
  - [ ] If >1.0s, profile and optimize hot paths

- [ ] **Create performance notes document**
  - [ ] File: `docs/PERFORMANCE-NOTES.md`
  - [ ] Include:
    - [ ] Hardware specs (CPU, memory)
    - [ ] Benchmark results (recompute time, memory usage)
    - [ ] Comparison to targets
    - [ ] Any performance optimization recommendations
  - [ ] Commit: `docs: add Phase 5 performance benchmarking results`

### 5.3 Comprehensive Documentation

- [ ] **Create Mission Planning Guide**
  - [ ] File: `docs/MISSION-PLANNING-GUIDE.md`
  - [ ] Include:
    - [ ] Overview of mission planning workflow
    - [ ] Step-by-step planner instructions (with screenshots)
    - [ ] X-Band, Ka, Ku transport behavior tables
    - [ ] Off-route projection rules
    - [ ] Timeline segment interpretation (nominal/degraded/critical)
    - [ ] Export format documentation
    - [ ] Troubleshooting section
  - [ ] Commit: `docs: add comprehensive mission planning guide`

- [ ] **Create Mission Communication SOP**
  - [ ] File: `docs/MISSION-COMM-SOP.md`
  - [ ] Include:
    - [ ] Pre-flight planning checklist
    - [ ] Grafana monitoring setup
    - [ ] Alert response procedures
    - [ ] Operator actions during degraded windows
    - [ ] Export delivery process
    - [ ] Incident response (e.g., unplanned outage)
  - [ ] Commit: `docs: add mission communication operations SOP`

- [ ] **Update monitoring README**
  - [ ] File: `monitoring/README.md`
  - [ ] Add section:
    - [ ] Mission timeline panel setup
    - [ ] Prometheus alert configuration
    - [ ] Dashboard layer management
    - [ ] Troubleshooting common display issues

- [ ] **Update project README**
  - [ ] File: `README.md` (root)
  - [ ] Add section: "Mission Communication Planning"
  - [ ] Link to:
    - [ ] MISSION-PLANNING-GUIDE.md
    - [ ] MISSION-COMM-SOP.md
    - [ ] Grafana dashboard instructions
    - [ ] API reference

- [ ] **Create/update docs/INDEX.md**
  - [ ] Ensure all new documentation is indexed
  - [ ] Add links to mission-specific guides
  - [ ] Commit: `docs: update documentation index with mission planning links`

### 5.4 Final Verification

- [ ] **Run full test suite**
  - [ ] Command:
        `docker compose exec starlink-location python -m pytest tests/ -v`
  - [ ] Expected: 700+ tests passing
  - [ ] If any failures: debug and fix before continuing

- [ ] **Docker rebuild and health check**
  - [ ] Command:
        `docker compose down && docker compose build --no-cache && docker compose up -d`
  - [ ] Verify all containers healthy: `docker compose ps`
  - [ ] Check service endpoints:
    - [ ] `curl http://localhost:8000/health`
    - [ ] `curl http://localhost:8000/api/missions` (returns empty list or
          missions)
    - [ ] `curl http://localhost:3000` (Grafana login page)
    - [ ] `curl http://localhost:9090` (Prometheus)

- [ ] **End-to-end workflow verification**
  - [ ] Create new mission via `/ui/mission-planner`
  - [ ] Activate mission
  - [ ] View timeline at `/api/missions/active/timeline`
  - [ ] Export to CSV/XLSX/PDF
  - [ ] Check Grafana dashboard for updates
  - [ ] Verify alert rules fire correctly

- [ ] **Code quality checks**
  - [ ] No TODO comments remaining in code
  - [ ] All functions documented with docstrings
  - [ ] No console warnings or errors in dev server logs
  - [ ] Commit: `chore: final quality checks before Phase 5 wrap-up`

---

## Documentation Maintenance

- [ ] Update PLAN.md if any phase scope changed
- [ ] Update CONTEXT.md if new files, dependencies, or constraints discovered
- [ ] Update LESSONS-LEARNED.md at `dev/LESSONS-LEARNED.md` with dated entry
      capturing key learnings

---

## Pre-Wrap Checklist

All of the following must be true before handoff to `wrapping-up-plan` skill:

- [ ] All Phase 4 & Phase 5 tasks above are marked `- [x]`
- [ ] 700+ tests passing (full suite: `pytest tests/`)
- [ ] Docker build completes without warnings or errors
- [ ] Grafana dashboard displays mission data without errors
- [ ] Prometheus metrics and alerts functional
- [ ] All exports (CSV/XLSX/PDF) generated successfully
- [ ] No outstanding TODOs in code
- [ ] PLAN.md reflects all completed phases
- [ ] CONTEXT.md updated with final implementation details
- [ ] All documentation files created and linked from README.md
- [ ] Branch ready for PR: `feature/mission-comm-planning` → `main`
