# ETA Route Timing - Implementation Context

**Last Updated:** 2025-11-03
**Feature Branch:** `feature/eta-route-timing` (to be created)

---

## Overview

Context consolidation for implementing route-aware ETA calculations using timing metadata from KML flight plan files. This work builds on the completed Phase 5.2 integration where RouteManager is wired into the simulation coordinator.

---

## Key Files Involved

### Models to Enhance
```
backend/starlink-location/app/models/route.py
├── RoutePoint - ADD: expected_arrival_time, expected_segment_speed_knots
├── RouteWaypoint - ADD: expected_arrival_time
└── ParsedRoute - ADD: timing profile info (optional)
```

### Services to Create/Modify
```
backend/starlink-location/app/services/
├── kml_parser.py - MODIFY: Extract timestamps from waypoint descriptions
├── route_timing_calculator.py - CREATE: Build timing profiles from routes
├── route_eta_calculator.py - CREATE: Route-aware ETA with blending
└── eta_calculator.py - MODIFY: Integrate with route timing (or wrap)
```

### Simulation Integration
```
backend/starlink-location/app/simulation/
├── kml_follower.py - ENHANCE: Use expected speeds from timing profile
└── coordinator.py - MODIFY: Pass timing info to follower
```

### API Endpoints to Update
```
backend/starlink-location/app/api/
├── pois.py - UPDATE: Include timing in POI responses
├── routes.py - UPDATE: Expose timing in route details
└── metrics.py - NEW METRICS: segment speed, departure time, ETA to waypoint
```

### Testing
```
backend/starlink-location/tests/
├── unit/
│   ├── test_route_timing.py - NEW: Timestamp parsing, speed calc
│   └── test_route_eta_calculator.py - NEW: ETA blending logic
└── integration/
    └── test_route_eta.py - NEW: End-to-end with 6 KML files
```

### Dashboarding
```
monitoring/grafana/provisioning/dashboards/
└── fullscreen-overview.json - MODIFY: Add timing panels
```

---

## Test Data Available

**Location:** `/home/brian/Projects/starlink-dashboard-dev/dev/completed/kml-route-import/`

**Files:**
- `Leg 1 Rev 6.kml` - KADW→PHNL (timing embedded)
- `Leg 2 Rev 6.kml` - PHNL→RJTY (timing embedded)
- `Leg 3 Rev 6.kml` - RJTY→EURA (timing embedded)
- `Leg 4 Rev 6.kml` - EURA→EGLL (timing embedded)
- `Leg 5 Rev 6.kml` - EGLL→UMRN (timing embedded)
- `Leg 6 Rev 6.kml` - UMRN→KADW (timing embedded)

**Timing Format in Descriptions:**
```xml
<description>APPCH
 Time Over Waypoint: 2025-10-27 16:57:55Z</description>
```

---

## Existing Architecture Context

### From KML Route Import Phases

**Phase 5.2 Completion (DONE):**
- RouteManager initialized in main.py (lines 119-143)
- Injected into SimulationCoordinator via `set_route_manager()`
- File watching active for `/data/routes/`
- Route activation/deactivation working

**Phase 5.3 Progress Metrics (DONE):**
- `starlink_route_progress_percent` exposed to Prometheus
- `starlink_current_waypoint_index` exposed to Prometheus
- PositionSimulator tracks progress 0.0-1.0

**Phase 5.4 Completion Behavior (DONE):**
- loop/stop/reverse modes implemented
- KMLRouteFollower handles position interpolation

### Where ETA Fits

Current flow:
```
Position Update → ETA Calculator → Prometheus Metrics → Grafana
```

With timing:
```
Route + Timing Data → Timing Profile → Enhanced ETA Calculator → Prometheus Metrics
                                            ↓
                                      Departure Detection
                                            ↓
                                      Pre-flight vs. In-flight Mode
                                            ↓
                                      Blending Logic
```

---

## Key Implementation Decisions

### 1. Timing Data Extraction
**Chosen Approach:** Direct parsing from waypoint descriptions

**Regex Pattern:** `Time Over Waypoint: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z)`

**Why:** All test KML files use this exact format, simple to extract, keeps data in source

### 2. Data Storage
**Chosen Approach:** Add fields to RoutePoint and RouteWaypoint models

**Fields Added:**
- `RoutePoint.expected_arrival_time: Optional[datetime]`
- `RoutePoint.expected_segment_speed_knots: Optional[float]`
- `RouteWaypoint.expected_arrival_time: Optional[datetime]`

**Why:** Simpler than separate profile, backward compatible, natural data locality

### 3. Segment Speed Calculation
**Formula:** `speed = haversine_distance(p1, p2) / time_delta(p1, p2)`

**Example from Leg 1:**
```
PHNL (16:51:13Z) → APPCH (16:57:55Z)
Distance: 62.8 km
Time: 402 seconds
Speed: (62800m / 1852) / (402/3600) = 598 knots
```

**Edge Cases Handled:**
- No timestamp on waypoint → skip segment
- Out-of-order timestamps → skip segment
- Zero time delta → skip segment
- Missing intermediate waypoints → leave speed null

### 4. Departure Detection
**Trigger:** Speed exceeds 10 knots threshold
**Status:** Sticky once departed, resets when route deactivated
**Alternative:** Could use altitude change, but speed is more reliable

### 5. ETA Blending Formula
**Current Mode (Pre-departure):**
```
eta_seconds = expected_arrival_time - current_utc_time
```

**Blending Mode (In-flight):**
```
alpha = 0.5  # Configurable via ETA_BLENDING_FACTOR
eta_seconds = (remaining_distance / actual_speed) * alpha
            + (time_to_expected_arrival) * (1 - alpha)
```

**Why:** Balances actual performance with flight plan, prevents wild swings

---

## Integration Dependencies

### On Existing Systems

1. **RouteManager (Phase 5.2)**
   - Must be available in SimulationCoordinator
   - `get_active_route()` returns ParsedRoute
   - File watching keeps routes updated

2. **POI Manager**
   - Must support route-scoped POI queries
   - Will link waypoints to POIs automatically
   - Cascade delete already implemented

3. **ETA Calculator**
   - Existing `calculate_poi_metrics()` will be extended
   - Must not break existing non-routed ETA calls
   - Speed smoothing window still active (120s)

4. **Metrics System**
   - New metrics added alongside existing ones
   - No changes to metric collection interval
   - All metrics updated in SimulationCoordinator cycle

### New Dependencies

- None - using only stdlib Python

---

## Configuration Options

### Environment Variables

```bash
# ETA calculation blending factor (0.0 = 100% plan, 1.0 = 100% actual)
ETA_BLENDING_FACTOR=0.5

# Speed threshold to detect departure (knots)
DEPARTURE_SPEED_THRESHOLD_KNOTS=10

# Enable route timing features
ENABLE_ROUTE_TIMING=true

# Default expected speed when timing unavailable (knots)
ETA_DEFAULT_SPEED_KNOTS=400
```

### Runtime Configuration

```python
# app/config.yaml (to be added)
eta:
  blending_factor: 0.5
  departure_threshold_knots: 10
  default_speed_knots: 400
  enable_route_timing: true
```

---

## Testing Strategy Summary

### Unit Test Coverage

1. **Timestamp Extraction** (test_route_timing.py)
   - Valid timestamps parsed correctly
   - Malformed timestamps handled gracefully
   - Timezones handled (UTC enforced)

2. **Speed Calculation** (test_route_timing.py)
   - Distance and time deltas correct
   - Segment speeds accurate (math verified)
   - Edge cases (zero time, missing times, etc.)

3. **ETA Blending** (test_route_eta_calculator.py)
   - Pre-departure mode returns countdown
   - In-flight blending adjusts correctly
   - Departure detection works
   - Fallback to default speed works

4. **Integration** (test_route_eta.py)
   - All 6 test KML files parse and calculate correctly
   - Verify ETAs against known times
   - Verify simulator respects timing

### Test KML Files

- Leg 1: KADW→PHNL (short, good for unit testing)
- Leg 2-6: Various distances/durations

---

## Performance Expectations

- KML parsing with timing: <2s per file
- ETA calculation per POI: <1ms
- Segment speed lookup: O(1) hash lookup
- Simulator speed adjustment: negligible overhead

---

## Documentation to Update

1. **Design Document** (`docs/design-document.md`)
   - Add section 5.1: "Route Timing & ETA Calculations"
   - Explain blending algorithm
   - Show example outputs

2. **CLAUDE.md Project Instructions**
   - Document timing feature
   - Configuration options
   - How to interpret pre-flight ETAs

3. **Grafana Dashboard** (`monitoring/grafana/provisioning/dashboards/*.json`)
   - Add timing panels
   - Document new metrics

4. **Development Plan** (`docs/phased-development-plan.md`)
   - Add Phase X for ETA timing
   - Cross-reference completed phases

---

## Success Criteria (from Main Plan)

**Functional:**
- ✅ Pre-departure ETAs match KML timing (±2%)
- ✅ In-flight ETAs adjust smoothly with actual speed
- ✅ All 6 test KML files parse without errors
- ✅ Zero regressions in existing ETA functionality

**Code Quality:**
- ✅ >90% code coverage
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ No critical/high-severity bugs

**Performance:**
- ✅ ETA calculations <10ms per POI
- ✅ Route parsing <5 seconds
- ✅ Simulator speed/timing accurate ±1-2%

---

## Known Limitations & Future Work

1. **Waypoint name matching**
   - Currently uses order in route
   - Could enhance to match POI names to waypoint names

2. **Multi-leg routes**
   - Each leg file is separate
   - Could merge legs into single profile (Phase 2)

3. **Conditional routing**
   - KML supports alternates, not yet handled
   - Can be added in future phases

4. **Real-time timing updates**
   - Times fixed in KML, can't update for delays
   - Could add manual offset capability later

---

**Context Status:** ✅ Complete
**Ready for:** Feature Branch & Implementation
