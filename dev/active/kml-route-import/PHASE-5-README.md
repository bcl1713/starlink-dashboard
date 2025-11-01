# Phase 5: Simulation Mode Route Following

## Quick Overview

Integrate KML routes into the simulation mode so the simulated aircraft follows planned routes, with real-time progress tracking and completion behavior options.

**Status:** Starting Phase 5
**Branch:** `feature/kml-route-import`
**Last Updated:** 2025-11-02

## What This Phase Does

When simulation mode is enabled and a route is active:
- Simulated position updates follow the route's waypoints in sequence
- Real-time progress metrics track current waypoint and completion percentage
- Route completion behavior configurable (loop, stop, reverse)
- All existing metrics continue to work normally

## Key Components

**Files to Modify:**
- `backend/starlink-location/app/simulation/coordinator.py` - Main simulator integration
- `backend/starlink-location/app/simulation/kml_follower.py` - Route following logic
- `backend/starlink-location/app/core/metrics.py` - Progress tracking metrics
- `backend/starlink-location/config.yaml` - Route completion behavior config
- `backend/starlink-location/main.py` - Dependency injection setup

**Files to Reference (no changes):**
- `backend/starlink-location/app/services/route_manager.py` - Route data access
- `backend/starlink-location/app/models/route.py` - Route data models

## Phase Breakdown

1. **Review Route Following (1-2 hours)**
   - Analyze existing `kml_follower.py` implementation
   - Understand waypoint chaining and interpolation
   - Document integration points

2. **Integrate with Simulator (2-3 hours)**
   - Modify SimulationCoordinator to check for active route
   - Inject RouteManager via dependency injection
   - Test route following in simulation mode

3. **Add Progress Metrics (1 hour)**
   - Create `starlink_route_progress_percent` metric
   - Track current waypoint index
   - Expose through Prometheus

4. **Implement Completion Behavior (1 hour)**
   - Add loop/stop/reverse options
   - Make configurable in config.yaml
   - Test each completion mode

5. **Full Integration Testing (2 hours)**
   - Upload test route
   - Activate in simulation mode
   - Verify follows waypoints correctly
   - Check metrics exposed

## Related Documentation

- **Planning:** `PHASE-5-PLAN.md`
- **Technical Context:** `PHASE-5-CONTEXT.md`
- **Task Checklist:** `PHASE-5-TASKS.md`
- **Session Notes:** `SESSION-NOTES.md` (see Phase 5 section)

## Getting Started

```bash
# Verify on the correct branch
git branch --show-current
# Should show: feature/kml-route-import

# Verify services are running
docker compose ps

# View API docs
curl http://localhost:8000/docs
```

## Success Criteria

✅ Route following logic integrated with simulator
✅ Progress metrics calculated and exposed
✅ Completion behavior configurable
✅ All 6 test routes follow correctly
✅ Existing metrics/features unaffected

---

**Created:** 2025-11-02
**Phase Status:** Starting Phase 5.1
