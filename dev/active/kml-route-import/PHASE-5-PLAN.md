# Phase 5 Implementation Plan: Simulation Mode Route Following

## Overview

Enable the simulator to follow KML routes with real-time progress tracking. This allows offline development and testing with planned flight paths instead of pre-recorded positions.

## Strategic Goals

1. **Route Following:** Simulated position updates follow active route waypoints
2. **Progress Tracking:** Expose route progress as Prometheus metrics
3. **Completion Behavior:** Configurable end-of-route handling (loop/stop/reverse)
4. **Transparency:** Log route following decisions for debugging
5. **Backward Compatible:** No impact on routes without active routes

## Architecture

### Current State

**Simulator (working):**
- `SimulationCoordinator` in `app/simulation/coordinator.py` generates telemetry
- Updates include position, speed, heading, metrics
- Updates POI ETAs every cycle

**Route System (working):**
- Routes loaded by `RouteManager` from `/data/routes/`
- Route file has coordinates, metadata
- GeoJSON endpoint serves route geometry
- No integration with simulator yet

**KML Follower (exists but unused):**
- `kml_follower.py` has route following logic
- Classes: `RouteFollower`, `WaypointInterpolator`
- Can calculate position along route based on distance/time

### Phase 5 Changes

```
SimulationCoordinator
  ├── Check for active route via RouteManager
  ├── If route exists:
  │   ├── Use RouteFollower to get next position
  │   ├── Calculate progress percentage
  │   └── Update simulator position to follow route
  └── If no route: use existing simulator logic

RouteManager (injected)
  ├── Provides active_route property
  ├── Returns full route coordinates
  └── Called each simulation cycle

Progress Metrics (new)
  ├── starlink_route_progress_percent (gauge)
  ├── starlink_current_waypoint_index (gauge)
  └── starlink_route_name (label)

Completion Behavior (new config)
  └── config.yaml: route_completion_behavior
      ├── loop (restart from beginning)
      ├── stop (stay at last waypoint)
      └── reverse (go back to start)
```

## Implementation Steps

### Phase 5.1: Route Following Review (1-2 hours)

**Goal:** Understand existing route following code

**Tasks:**
1. Read `app/simulation/kml_follower.py`
   - Understand `RouteFollower` class API
   - Find methods for position interpolation
   - Check how it handles waypoint sequences

2. Read `app/simulation/coordinator.py`
   - Understand current position update cycle
   - Identify where route integration would go
   - Find dependency injection pattern used

3. Document integration points
   - Where simulator gets position update
   - What RouteFollower methods needed
   - How to inject RouteManager

**Output:** Summary document with code references

---

### Phase 5.2: Simulator Integration (2-3 hours)

**Goal:** Connect SimulationCoordinator with active route

**Tasks:**
1. Modify `main.py` startup
   - Inject RouteManager into SimulationCoordinator
   - Pattern: similar to ETA service injection

2. Modify `SimulationCoordinator`
   - Add RouteManager property
   - Add setter function for injection
   - Add route-following logic to update cycle
   - Check for active route before each position update
   - If route exists, use RouteFollower for next position
   - If no route, use existing simulator logic

3. Handle edge cases
   - No active route (use simulator)
   - Route with no coordinates (skip route mode)
   - Route with 1 waypoint (stay there)
   - Aircraft ahead of route start (catch up logic)

4. Test basic integration
   - Upload test route
   - Activate in simulator mode
   - Verify position follows route

**Output:** Working route integration in simulator

---

### Phase 5.3: Progress Metrics (1 hour)

**Goal:** Expose route following progress to Prometheus

**Tasks:**
1. Modify `app/core/metrics.py`
   - Add `starlink_route_progress_percent` gauge
   - Add `starlink_current_waypoint_index` gauge
   - Add route name as label
   - Initialize in startup

2. Modify `SimulationCoordinator`
   - Calculate progress percentage (distance traveled / total)
   - Get current waypoint index from RouteFollower
   - Update metrics each cycle

3. Update ETA service (if needed)
   - Ensure POI ETAs calculated from current position
   - Should work automatically if position updated

4. Test metrics
   - `curl http://localhost:8000/metrics`
   - Verify progress metrics appear
   - Check progress increases as route follows

**Output:** Metrics exposed and updating

---

### Phase 5.4: Completion Behavior (1 hour)

**Goal:** Configurable end-of-route handling

**Tasks:**
1. Update `config.yaml`
   - Add `route_completion_behavior: [loop|stop|reverse]`
   - Default: `loop`

2. Modify `RouteFollower` or `SimulationCoordinator`
   - Add method to set completion behavior
   - Implement completion logic:
     - `loop`: reset to start of route
     - `stop`: stay at last waypoint, don't advance
     - `reverse`: return to start, alternating direction

3. Update `SimulationCoordinator`
   - Load config value on startup
   - Pass to RouteFollower
   - Test each mode

4. Test completion behavior
   - Short 3-point test route
   - Activate and simulate until route ends
   - Verify each mode works

**Output:** Configurable completion behavior working

---

### Phase 5.5: Integration Testing (2 hours)

**Goal:** Full end-to-end verification with all 6 test routes

**Tasks:**
1. Prepare test routes
   - All 6 Leg KML files available in current directory
   - Note expected waypoint counts for each

2. Test route 1 (KADW→PHNL)
   - Upload Leg 1 Rev 6.kml via web UI
   - Activate in simulator mode
   - Watch position update in Grafana
   - Verify progress metrics in Prometheus
   - Check logs for route following messages
   - Deactivate and verify simulator resumes normal behavior

3. Test all 6 routes
   - Repeat for each Leg file
   - Verify no errors in logs
   - Check metric updates in Prometheus

4. Test edge cases
   - Activate different routes (should switch)
   - Deactivate during simulation (should revert to simulator)
   - Test each completion behavior (loop/stop/reverse)

5. Verify backward compatibility
   - POI ETA calculations still work
   - Metrics still update
   - No new errors in logs
   - Existing features unaffected

**Output:** All tests passing, ready for PR

---

## Risk Assessment

### Low Risk
- **Route Following:** Logic already exists in `kml_follower.py`, just needs integration
- **Dependency Injection:** Pattern already established in codebase
- **Metrics:** Prometheus setup already working, just adding new metrics

### Medium Risk
- **Simulator Interaction:** Modifying SimulationCoordinator core loop, need careful testing
- **Edge Cases:** Handling missing routes, bad coordinates, etc.

### Mitigation
- Add comprehensive logging to route following decisions
- Test each route individually before combining
- Keep git history clean with frequent commits
- Test with all 6 real-world routes before finalizing

## Success Criteria

✅ Route following integrated into simulator
✅ Position updates follow route waypoints
✅ Progress metrics calculated and exposed
✅ Completion behavior configurable
✅ All 6 test routes work correctly
✅ No regressions in existing features
✅ Clear logging of route following decisions
✅ Backward compatible (works with/without active route)

## Timeline

**Estimated Total:** 7-8 hours
- Phase 5.1: 1-2 hours (review)
- Phase 5.2: 2-3 hours (integration)
- Phase 5.3: 1 hour (metrics)
- Phase 5.4: 1 hour (completion behavior)
- Phase 5.5: 2 hours (testing)

**Can be completed in 1-2 development sessions**

---

## Next Phase (Phase 6)

Once Phase 5 is complete:
- **Testing & Documentation:** Expand test coverage, finalize docs
- **CI/CD Integration:** Add automated tests
- **Feature Branch:** Merge to dev, then create PR to main

---

**Last Updated:** 2025-11-02
**Status:** Ready to Begin Phase 5.1
