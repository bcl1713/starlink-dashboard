# Phase 5: Task Checklist

## Phase 5.1: Review Route Following (Target: 1-2 hours)

- [ ] **5.1.1** Read `app/simulation/kml_follower.py` (30 min)
  - [ ] Understand RouteFollower class and its __init__ signature
  - [ ] Identify all public methods available
  - [ ] Find update() method and understand parameters
  - [ ] Find get_current_position() and what it returns
  - [ ] Check for completion handling methods

- [ ] **5.1.2** Read `app/simulation/coordinator.py` (30 min)
  - [ ] Find SimulationCoordinator class definition
  - [ ] Understand __init__ parameters and properties
  - [ ] Locate update() method and trace execution flow
  - [ ] Identify position update methods
  - [ ] Find metric update calls

- [ ] **5.1.3** Review `main.py` startup pattern (15 min)
  - [ ] Find where SimulationCoordinator is created
  - [ ] Check how ETA service is injected (pattern to follow)
  - [ ] Identify startup_event and shutdown_event

- [ ] **5.1.4** Document integration design (15 min)
  - [ ] Create summary of integration points
  - [ ] Note any required parameter changes
  - [ ] Identify potential edge cases

**Output:** Document detailing integration plan with code line references

---

## Phase 5.2: Simulator Integration (Target: 2-3 hours)

- [ ] **5.2.1** Modify `main.py` for dependency injection (30 min)
  - [ ] Create RouteManager instance in startup_event (if not already done)
  - [ ] Create SimulationCoordinator with RouteManager reference
  - [ ] Add setter method for RouteManager injection
  - [ ] Test: `docker compose logs starlink-location | grep "SimulationCoordinator"`

- [ ] **5.2.2** Add RouteManager to SimulationCoordinator (1 hour)
  - [ ] Add `route_manager` property to __init__
  - [ ] Add `set_route_manager(manager)` method
  - [ ] Import RouteFollower class
  - [ ] Create route_follower instance when route activated
  - [ ] Add route_completion_behavior config read

- [ ] **5.2.3** Integrate route following into update cycle (1 hour)
  - [ ] Add check for active route in update()
  - [ ] Create _get_route_position() method
  - [ ] Implement RouteFollower initialization on route activation
  - [ ] Call route_follower.update() each cycle if route active
  - [ ] Update self.latitude/longitude from route position
  - [ ] Add fallback to simulator if no route

- [ ] **5.2.4** Handle edge cases (30 min)
  - [ ] No active route (skip route logic)
  - [ ] Route with 0 coordinates (log warning, skip)
  - [ ] Route with 1 waypoint (stay at that waypoint)
  - [ ] Route deactivation (reset route_follower to None)
  - [ ] Route activation switch (reinitialize route_follower)

- [ ] **5.2.5** Basic integration test (30 min)
  - [ ] Start docker compose: `docker compose up -d`
  - [ ] Upload a test route via web UI
  - [ ] Activate route
  - [ ] Check logs: `docker compose logs -f starlink-location | grep -i route`
  - [ ] Verify position updates (use Grafana or API)
  - [ ] Deactivate route and verify simulator resumes

**Output:** Working route integration with SimulationCoordinator

---

## Phase 5.3: Progress Metrics (Target: 1 hour)

- [ ] **5.3.1** Add metrics to `app/core/metrics.py` (20 min)
  - [ ] Add `starlink_route_progress_percent` Gauge
  - [ ] Add `starlink_current_waypoint_index` Gauge
  - [ ] Add route_name label to both metrics
  - [ ] Initialize metrics in startup
  - [ ] Verify metrics appear in `/metrics` endpoint

- [ ] **5.3.2** Update SimulationCoordinator metrics (20 min)
  - [ ] Add `_calculate_route_progress()` method
  - [ ] Calculate percentage: (distance_traveled / total_distance) * 100
  - [ ] Get waypoint index from route_follower
  - [ ] Update metrics each cycle if route active
  - [ ] Set metrics to 0 if no active route

- [ ] **5.3.3** Verify metrics in Prometheus (20 min)
  - [ ] Activate test route
  - [ ] Check `/metrics` endpoint: `curl http://localhost:8000/metrics | grep starlink_route`
  - [ ] Verify progress increases over time
  - [ ] Check Prometheus UI: http://localhost:9090/graph
  - [ ] Query: `starlink_route_progress_percent`
  - [ ] Verify metrics update every ~1 second

**Output:** Progress metrics exposed and updating correctly

---

## Phase 5.4: Completion Behavior (Target: 1 hour)

- [ ] **5.4.1** Update `config.yaml` (10 min)
  - [ ] Add `route_completion_behavior: loop` under simulation section
  - [ ] Document options: loop, stop, reverse
  - [ ] Set default to `loop`

- [ ] **5.4.2** Implement completion logic in SimulationCoordinator (30 min)
  - [ ] Read config value in __init__
  - [ ] Pass to RouteFollower on initialization
  - [ ] Implement in RouteFollower or SimulationCoordinator:
    - [ ] `loop`: Reset route_follower to start when finished
    - [ ] `stop`: Keep route_follower at last waypoint
    - [ ] `reverse`: Alternate direction on completion

- [ ] **5.4.3** Test each completion behavior (20 min)
  - [ ] Set config to `loop` and test (route restarts)
  - [ ] Set config to `stop` and test (route stays at end)
  - [ ] Set config to `reverse` and test (route goes backward)
  - [ ] Verify metrics continue updating
  - [ ] Check logs for completion events

**Output:** Configurable route completion behavior working

---

## Phase 5.5: Integration Testing (Target: 2 hours)

- [ ] **5.5.1** Test Route 1: KADW→PHNL (20 min)
  - [ ] Upload Leg 1 Rev 6.kml via web UI
  - [ ] Activate in simulator mode
  - [ ] Watch position in Grafana map for 30 seconds
  - [ ] Verify position moves along route
  - [ ] Check progress metric increases
  - [ ] Verify logs: `docker compose logs starlink-location | tail -50`
  - [ ] Check for any error messages

- [ ] **5.5.2** Test Routes 2-6 (30 min total, 5 min each)
  - [ ] Repeat for Leg 2, 3, 4, 5, 6
  - [ ] Verify each follows without errors
  - [ ] Note any issues

- [ ] **5.5.3** Test route switching (15 min)
  - [ ] Activate Route 1, observe for 15 seconds
  - [ ] Deactivate Route 1
  - [ ] Activate Route 2
  - [ ] Verify position jumps to Route 2 start
  - [ ] Position follows Route 2 correctly

- [ ] **5.5.4** Test completion behavior (15 min)
  - [ ] Create short 3-point test route or use Leg 2 (30 points)
  - [ ] Set `route_completion_behavior: loop`
  - [ ] Watch until route completes and restarts
  - [ ] Set `route_completion_behavior: stop`
  - [ ] Watch until route ends and position stays
  - [ ] Verify metrics during completion

- [ ] **5.5.5** Verify backward compatibility (10 min)
  - [ ] Deactivate all routes
  - [ ] Simulator should run normal pattern
  - [ ] POI ETAs still calculate
  - [ ] All existing metrics still update
  - [ ] No new errors in logs

- [ ] **5.5.6** Performance verification (5 min)
  - [ ] Monitor CPU: `docker stats`
  - [ ] Check metrics update rate hasn't degraded
  - [ ] Verify no memory leaks (stats stable for 1 min)
  - [ ] Check Prometheus scrape success

**Output:** All routes tested, backward compatible, ready for PR

---

## Phase 5 Completion Checklist

- [ ] All 5.1-5.5 tasks completed
- [ ] No TODO comments left in code
- [ ] No errors in logs during testing
- [ ] All 6 test routes follow correctly
- [ ] Progress metrics working
- [ ] Completion behavior configurable
- [ ] Backward compatible verified
- [ ] Code committed with clear message
- [ ] Ready for merge to dev and PR to main

---

## Notes

**Test Route Files Location:** Current directory (kml-route-import/)

**Key Metrics to Monitor:**
- `starlink_dish_latitude_degrees` - Position changes along route
- `starlink_dish_longitude_degrees` - Position changes along route
- `starlink_route_progress_percent` - Should increase from 0 to 100
- `starlink_current_waypoint_index` - Should increment

**Important Endpoints:**
- Upload route: POST `/api/routes`
- List routes: GET `/api/routes`
- Activate: POST `/api/routes/{route_id}/activate`
- Metrics: GET `/metrics`
- Grafana: http://localhost:3000

**Useful Commands:**
```bash
# Watch logs
docker compose logs -f starlink-location

# Check metrics
curl http://localhost:8000/metrics | grep starlink_route

# Check active route
curl http://localhost:8000/api/routes | grep active

# View Prometheus
open http://localhost:9090/graph
```

---

**Created:** 2025-11-02
**Last Updated:** 2025-11-02
**Target Completion:** 1-2 development sessions
