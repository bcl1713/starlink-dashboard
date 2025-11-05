# ETA Route Timing - Implementation Context

**Last Updated:** 2025-11-04 (Session 27 - Root Cause Identified, Approach Refined)
**Feature Branch:** `feature/eta-route-timing`
**Status:** 🔧 BUG FIX IN PROGRESS - Root cause identified, architecture redesign in progress

---

## Overview & Current Issue (Session 27 - ARCHITECTURAL REDESIGN)

ETA Route Timing feature is feature-complete (Sessions 1-26) for API and simulation, but **metrics dashboard shows incorrect ETA** (27 hours instead of 14) for Korea-to-Andrews route.

### Root Cause (CONFIRMED)
Two separate ETA calculation codepaths:
1. **`RouteETACalculator`** (API endpoint) - ✅ Works correctly, uses segment-based speeds from timing profile
2. **`ETACalculator`** (Prometheus metrics) - ❌ Broken, uses only distance/smoothed_speed, completely ignores route timing

### The Real Problem
The attempted fix (override after calculation) was wrong architecturally. **ETACalculator should BE route-aware by default**, not have it bolted on afterward. The calculator needs to know about the active route and use segment-based speeds automatically when available.

### Solution (NEW APPROACH)
Enhance `ETACalculator` to:
- Accept optional `active_route: ParsedRoute` parameter
- When POI matches active route waypoint with timing data, use RouteETACalculator logic
- Use segment-based speeds from route timing profile
- Fall back to distance/speed only for POIs not on active route
- Make this the default behavior, not an override

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
**Trigger:** Speed exceeds 50 knots threshold (configurable via DEPARTURE_THRESHOLD_SPEED_KNOTS)
**Status:** Sticky once departed, resets when route deactivated
**Rationale:** 50 knots clearly indicates takeoff roll (max taxi ~30 knots with buffer)
**Future Consideration:** Can be adjusted per-operation for different aircraft types

### 5. ETA Data Formats
**ETA always returned in two formats:**
- `eta_countdown_seconds`: Relative time in seconds (e.g., 402 for 6m 42s)
- `eta_time_gmt`: Absolute time in GMT/Z format (e.g., "2025-10-27T16:57:55Z")

**Why:** Both formats needed for dashboard display (countdown for clarity, GMT for mission planning)

### 6. ETA Blending Formula
**Current Mode (Pre-departure):**
```
eta_countdown_seconds = expected_arrival_time - current_utc_time
eta_time_gmt = expected_arrival_time (as ISO-8601 datetime)
```

**Blending Mode (In-flight):**
```
alpha = 0.5  # Configurable via ETA_BLENDING_FACTOR
eta_countdown_seconds = (remaining_distance / actual_speed) * alpha
                      + (time_to_expected_arrival) * (1 - alpha)
eta_time_gmt = now + eta_countdown_seconds (as ISO-8601 datetime)
```

**Why:** Balances actual performance with flight plan, prevents wild swings

### 7. Off-Route Point Projection & Hybrid Point Status
**For POIs not strictly on route (e.g., satellite handoff markers):**
- **ETA Calculation:** Project point onto nearest route segment, use projected distance
- **Map Display:** Show point at original coordinates (unchanged visual position)
- **API Response:** Include both original and projected coordinates
- **Point Status:** Hybrid approach:
  - **Primary:** Route-based - Is projected point ahead/passed current position along route?
  - **Fallback:** Angle-based - Existing heading logic for non-routed points
  - **Flag:** Mark as "projected_to_route" in API response

**Use Case:** Satellite communication handoff points in space that aren't on flight path
- Provides accurate ETA for strategic event (when we reach that point in space)
- Maintains accurate position display on map (original coordinates)
- Supports mission planning and communication transition scheduling

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

# Speed threshold to detect departure (knots) - 50 knots indicates takeoff roll
# (max taxi ~30 knots, so 50 knots gives clear buffer for this aircraft)
# Can be adjusted per-operation for different aircraft types
DEPARTURE_THRESHOLD_SPEED_KNOTS=50

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

## Session 27 Debugging Findings

### Metrics ETA Bug Investigation

**What Works:**
- API endpoint `/api/routes/{id}/progress?lat=X&lon=Y` returns correct ~14 hour ETA ✅
- RouteETACalculator `_calculate_remaining_duration_from_segments()` uses timing profile correctly
- Route timing profile populated correctly (departure 09:15, arrival 23:17, duration 50572 seconds = 14.04 hours)

**What's Broken:**
- Prometheus metric `starlink_eta_poi_seconds` shows 98773 seconds (27.4 hours) ❌
- Metrics calculated via `update_eta_metrics()` in `app/core/eta_service.py`
- ETACalculator uses simple distance/speed, ignores route timing

**Root Cause Anatomy:**
```
Metrics Flow:
  telemetry_update_loop()
    → update_eta_metrics(lat, lon, speed)  [in eta_service.py]
      → ETACalculator.calculate_poi_metrics()  [WRONG: uses distance/speed only]
      → Sets starlink_eta_poi_seconds gauge

API Flow:
  /api/routes/{id}/progress?lat=X&lon=Y
    → RouteETACalculator(route).get_route_progress(lat, lon)  [CORRECT]
    → Returns expected_duration_remaining_seconds from timing profile
```

### Attempted Fix (In Progress)

Modified `update_eta_metrics()` to:
1. Get active route from route_manager
2. If route has timing_profile, create RouteETACalculator
3. Calculate progress and remaining duration
4. Find arrival POI (last waypoint) in POI list
5. Override its ETA in metrics dict before returning

**Potential Issues to Debug:**
- Route manager import/availability from eta_service
- POI matching logic ("KADW" substring search may not work)
- Metrics recalculation frequency (might be using cached values)
- Need to verify waypoint.name matches poi.name correctly

**Code Added:**
- `app/core/eta_service.py:105-150` - Route-aware ETA override logic
- Fall back to standard POI metrics if route logic fails

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
