# ETA Calculations Using Route Timing from KML Files

**Last Updated:** 2025-11-03
**Status:** Planning Phase
**Author:** Claude Code

---

## Executive Summary

This feature enhances ETA calculations by leveraging timing metadata embedded in KML route files (specifically the test flight plan KML files in `dev/completed/kml-route-import/`). The system will parse `Time Over Waypoint` timestamps to determine anticipated speeds for each route segment, enabling accurate ETAs both before departure and during flight.

**Key Improvements:**
- **Pre-departure ETAs:** Accurate waypoint arrival times based on flight plan
- **In-flight ETAs:** Dynamic blending of actual speed with anticipated segment speeds
- **Departure detection:** Use existing logic to detect when the aircraft leaves the ground
- **Graceful fallback:** Use configurable default speed when timing data unavailable

---

## Current State Analysis

### Existing Components

1. **KML Parser** (`app/services/kml_parser.py`)
   - Parses `Time Over Waypoint` from waypoint descriptions
   - Currently extracts `RouteWaypoint` objects with roles
   - Does NOT extract or store timing information

2. **Route Models** (`app/models/route.py`)
   - `RoutePoint`: Basic coordinate + altitude, no timing
   - `RouteWaypoint`: Includes description (contains timing), no parsed timestamp
   - `ParsedRoute`: Container for points and waypoints
   - No segment-level speed or timing data

3. **ETA Calculator** (`app/services/eta_calculator.py`)
   - Distance-based ETA using Haversine formula
   - Speed-based ETA: `eta_seconds = (distance_m / 1852) / speed_knots * 3600`
   - Current smoothing uses 120-second rolling window
   - No awareness of route timing or anticipated speeds

4. **KML Route Follower** (`app/simulation/kml_follower.py`)
   - Follows routes by interpolating position along waypoints
   - Calculates progress as 0.0-1.0 along total distance
   - No timing/speed awareness

5. **POI/ETA Metrics** (`app/core/metrics.py`, `app/api/pois.py`)
   - Exposes `starlink_eta_poi_seconds` and `starlink_distance_to_poi_meters`
   - Calculated using current speed and great-circle distance
   - No route context or anticipated speeds

### What's Missing

- Timestamp parsing from KML waypoint descriptions
- Segment-level speed calculations (distance / time delta)
- Expected speed profile for entire route
- Awareness of whether aircraft has departed (pre-flight vs. in-flight)
- Dynamic ETA blending logic (actual speed + anticipated speed)
- Metrics for segment expected speed and deviation

---

## Proposed Future State

### Architecture Overview

```
KML File with Timing
      ↓
[KML Parser]
      ↓
Extract & Parse Timestamps
      ↓
[RouteTimingProfile]
  - Segments with expected times
  - Calculated expected speeds
  - Pre-departure reference times
      ↓
[ETA Calculator v2]
  - Pre-departure: Use timing data directly
  - In-flight: Blend actual + anticipated speeds
      ↓
Prometheus Metrics + API Responses
  - starlink_eta_poi_seconds (now route-aware)
  - starlink_expected_segment_speed_knots (new)
  - starlink_departure_time (new)
```

### Key Concepts

**1. Timing Data Extraction**
- Parse `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ` from waypoint descriptions
- Extract ISO-8601 timestamps (UTC)
- Store in `RoutePoint` model as `expected_arrival_time: Optional[datetime]`

**2. Segment Speed Calculation**
- For adjacent waypoints with times: `speed = distance / time_delta`
- Example: PHNL (16:51:13Z) → APPCH (16:57:55Z), 62.8 km distance
  - Time delta: 6m 42s = 402 seconds
  - Expected speed: (62800m / 1852) / (402 / 3600) = ~598 knots
- Used to populate segment expected speeds

**3. Departure Detection**
- Track initial position and speed
- Departure = speed exceeds threshold (e.g., 10 knots) after ground start
- Used to switch from "pre-departure" to "in-flight" mode

**4. Pre-Departure ETA Calculation**
- If aircraft on ground (speed ~0) and route active:
  - Calculate current UTC time to first waypoint arrival time
  - Report absolute ETA, or as relative countdown
  - Use segment expected speeds if available

**5. In-Flight ETA Blending**
- When departed:
  - Remaining waypoints use their expected arrival times
  - If actual speed < expected: ETA extends backward
  - If actual speed > expected: ETA compresses forward
  - Blend formula: `eta = (remaining_distance / current_speed) * α + (remaining_time_by_plan) * (1-α)`
  - Where `α` is a weight factor (0.5 = 50% actual, 50% plan)

---

## Implementation Phases

### Phase 1: Data Model Enhancements (Effort: M)

**Objective:** Add timing support to route models

**Tasks:**
1. Extend `RoutePoint` model
   - Add `expected_arrival_time: Optional[datetime]` field
   - Add `expected_segment_speed_knots: Optional[float]` field
   - Keep backward compatible

2. Extend `RouteWaypoint` model
   - Add `expected_arrival_time: Optional[datetime]` field
   - Used for reference during POI display

3. Create `RouteTimingProfile` class (optional, initially)
   - Holds: segment speeds, total expected duration, departure time
   - Later phases may move to separate profile if needed

4. Update API response models
   - Include timing info in route detail responses
   - Expose expected segment speeds for dashboard display

**Acceptance Criteria:**
- ✅ Models include timing fields
- ✅ Existing routes still parse (fields optional)
- ✅ Unit tests pass for model creation with/without timing
- ✅ API responses include timing when available

---

### Phase 2: KML Parser Enhancements (Effort: M)

**Objective:** Extract timing metadata from KML waypoint descriptions

**Tasks:**
1. Create timestamp extraction utility
   - Regex pattern: `Time Over Waypoint: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}Z)`
   - Parse to `datetime` object (UTC)
   - Handle missing/malformed timestamps gracefully

2. Update KML parser
   - Call extraction utility for each waypoint
   - Store parsed timestamp in `RouteWaypoint.expected_arrival_time`
   - Log warnings if timestamp parsing fails

3. Calculate expected segment speeds
   - During route parsing, iterate through consecutive waypoints with times
   - For each segment: `speed = distance(p1, p2) / time_delta(p1, p2)`
   - Store in `RoutePoint.expected_segment_speed_knots`
   - Handle edge cases:
     - Zero time delta (simultaneous waypoints)
     - Waypoints without timestamps
     - Out-of-order timestamps

4. Add route-level timing metadata
   - Extract departure waypoint from route name (KADW in "KADW-PHNL")
   - Find first waypoint with timestamp = departure time
   - Store in `ParsedRoute` or `RouteTimingProfile`

**Acceptance Criteria:**
- ✅ All 6 test KML files parse correctly
- ✅ Waypoint timestamps extracted accurately
- ✅ Segment speeds calculated correctly (validate math)
- ✅ Edge cases handled without crashes
- ✅ Integration tests verify parsing roundtrip

---

### Phase 3: ETA Calculator v2 (Effort: L)

**Objective:** Implement route-aware ETA calculations with blending

**Tasks:**
1. Create `RouteETACalculator` class (or extend `ETACalculator`)
   - Accept `ParsedRoute` as input
   - Methods:
     - `set_route(route: ParsedRoute)` - Activate route context
     - `is_departed() -> bool` - Check if aircraft has left ground
     - `update_position(lat, lon, speed, timestamp)` - Track position/speed
     - `calculate_poi_etas(pois) -> dict` - Route-aware POI ETA

2. Implement departure detection
   - Track ground position on startup
   - Threshold: speed > 10 knots = departed
   - Once departed, flag persists until route deactivated
   - Log departure event with timestamp

3. Implement pre-departure ETA
   - Input: current UTC time, first waypoint expected arrival
   - Output: seconds to arrival (countdown)
   - For intermediate waypoints: use their expected_arrival_time
   - Handle case where expected times are in the past

4. Implement in-flight ETA blending
   - Input: remaining distance, current speed, expected segment speed, time-to-expected-arrival
   - Blend formula: `eta = (dist / speed_actual) * α + (time_to_expected) * (1-α)`
   - Configurable `α` (default 0.5)
   - Fallback to current speed if segment speed unavailable

5. Extend POI ETA calculations
   - If POI matches a waypoint with expected arrival time: use that
   - Otherwise: calculate as normal but consider segment speeds
   - Add metric: `expected_arrival_time` in response

**Acceptance Criteria:**
- ✅ Departure detection works reliably
- ✅ Pre-departure ETAs match KML timing (within 1 second)
- ✅ In-flight blending adjusts ETAs dynamically
- ✅ Fallback to current speed works
- ✅ Unit tests cover all blending scenarios
- ✅ Integration tests with real KML files pass

---

### Phase 4: Simulator & Route Follower Integration (Effort: S)

**Objective:** Use timing data for realistic route-following simulation

**Tasks:**
1. Extend `KMLRouteFollower`
   - Accept route timing profile
   - Methods:
     - `set_target_speed_for_segment(segment_idx) -> float` - Get expected speed
     - `get_expected_arrival_time(waypoint_idx) -> datetime` - Get timing

2. Update `SimulationCoordinator`
   - When following a route, use expected segment speeds
   - Simulate speed variations within ±10% of expected speed
   - Speed up/slow down to match expected arrival times more closely

3. Add simulation controls (optional)
   - `POST /api/sim/set_speed_multiplier?factor=1.0` - Speed up/slow down simulation

**Acceptance Criteria:**
- ✅ Simulation respects expected segment speeds
- ✅ Route following timestamps match KML data
- ✅ Speed variations are realistic

---

### Phase 5: Dashboard & Metrics (Effort: M)

**Objective:** Expose timing data and new metrics to Grafana

**Tasks:**
1. Create new Prometheus metrics
   - `starlink_expected_segment_speed_knots` - Expected speed for current segment
   - `starlink_departure_time` - Unix timestamp of departure
   - `starlink_eta_to_next_waypoint_seconds` - ETA to next route waypoint
   - `starlink_waypoint_sequence` - Current waypoint index
   - `starlink_actual_vs_expected_speed_ratio` - actual / expected

2. Update `/api/route/coordinates` endpoint
   - Include timing info in response
   - Show expected vs. actual speeds per waypoint

3. Update `/api/pois` endpoint
   - Include `expected_arrival_time` in POI responses
   - Show confidence/accuracy based on deviation

4. Create Grafana dashboard panel
   - Timeline showing planned vs. actual waypoint arrivals
   - Speed profile (expected vs. actual over route)
   - Departure countdown timer (pre-flight)

5. Update route management UI
   - Display timing profile when route selected
   - Show expected duration and departure/arrival times
   - Display segment speeds

**Acceptance Criteria:**
- ✅ All new metrics exposed to Prometheus
- ✅ Dashboard panels display timing correctly
- ✅ Grafana queries work without errors
- ✅ UI shows timing info for active route

---

### Phase 6: Testing & Documentation (Effort: M)

**Objective:** Comprehensive test coverage and user documentation

**Tasks:**
1. Unit tests
   - Timestamp extraction and parsing
   - Speed calculations (math verification)
   - Departure detection logic
   - ETA blending formulas
   - All edge cases

2. Integration tests
   - Parse all 6 test KML files
   - Verify ETAs against expected values
   - Test pre-flight vs. in-flight transitions
   - Route switching behavior

3. End-to-end tests
   - Upload KML → activate route → simulate flight → verify ETAs
   - Dashboard displays timing correctly
   - Metrics update as expected

4. Documentation
   - Update design doc with timing architecture
   - Document ETA calculation algorithms
   - Document configuration options (α blending factor, departure speed threshold)
   - Create user guide for timing-aware routes

5. Configuration
   - Add environment variables:
     - `ETA_BLENDING_FACTOR` (default: 0.5)
     - `DEPARTURE_SPEED_THRESHOLD_KNOTS` (default: 10)
     - `ENABLE_ROUTE_TIMING` (default: true)

**Acceptance Criteria:**
- ✅ >90% code coverage for new ETA logic
- ✅ All 6 KML files tested
- ✅ Integration tests pass
- ✅ Documentation complete
- ✅ No regressions in existing functionality

---

## Risk Assessment & Mitigation

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|-----------|
| Malformed timestamp data in KML | ETAs invalid | Medium | Regex validation + fallback to default speed |
| Out-of-order waypoints in timing | Negative time deltas | Low | Validation during parse, skip bad segments |
| Departure detection false positives | Wrong ETA mode | Medium | Higher speed threshold (10 knots), hysteresis |
| Backward compatibility break | Existing routes fail | Low | All timing fields optional, defaults work |
| Blending factor complexity | Hard to debug | Medium | Expose α as configurable, log blending ratio |
| Timezone issues in timestamp parsing | Wrong times | Low | Enforce UTC in parser, unit tests verify |

---

## Success Metrics

**Functional:**
- ✅ Pre-departure ETAs match KML timing (±2%)
- ✅ In-flight ETAs adjust smoothly with actual speed
- ✅ All 6 test KML files parse without errors
- ✅ Zero regressions in existing ETA functionality

**Quality:**
- ✅ >90% code coverage for new modules
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ No critical or high-severity bugs

**Performance:**
- ✅ ETA calculations <10ms per POI
- ✅ Route parsing <5 seconds even for 10,000-point routes
- ✅ Simulator speed/timing accurate within 1-2%

**User Experience:**
- ✅ Dashboard displays timing clearly
- ✅ Pre-flight countdown visible and accurate
- ✅ Speed profile visualization helpful
- ✅ Documentation clear and comprehensive

---

## Required Resources & Dependencies

### Python Packages
- Existing: `pydantic`, `fastapi`, `prometheus_client`
- New: None (use stdlib `datetime`, `re`)

### Files to Create
- `app/services/route_timing_calculator.py` - Timing profile generation
- `app/services/route_eta_calculator.py` - Enhanced ETA logic
- `tests/unit/test_route_timing.py` - Unit tests
- `tests/integration/test_route_eta.py` - Integration tests

### Files to Modify
- `app/models/route.py` - Add timing fields
- `app/services/kml_parser.py` - Parse timestamps
- `app/services/eta_calculator.py` - Or create wrapper
- `app/core/metrics.py` - New Prometheus metrics
- `app/api/pois.py` - Route-aware ETA responses
- `app/simulation/kml_follower.py` - Use expected speeds
- `monitoring/grafana/provisioning/dashboards/*.json` - New panels

### Test Data
- All 6 existing test KML files already have timing data

---

## Timeline Estimates

| Phase | Effort | Duration | Dependencies |
|-------|--------|----------|--------------|
| Phase 1: Data Models | M | 1-2 days | None |
| Phase 2: KML Parser | M | 2-3 days | Phase 1 |
| Phase 3: ETA Calculator | L | 3-4 days | Phase 2 |
| Phase 4: Simulator | S | 1-2 days | Phase 3 |
| Phase 5: Dashboard | M | 2-3 days | Phase 3 |
| Phase 6: Testing & Docs | M | 2-3 days | All phases |
| **Total** | **XL** | **11-17 days** | Sequential |

---

## Implementation Notes

### Key Decisions

1. **Timing in RoutePoint, not separate model**
   - Simpler API, less refactoring needed
   - Each point knows its expected arrival time
   - Segment speeds calculated on-the-fly or stored

2. **Blending factor configurable but with sensible default**
   - 0.5 = 50% actual speed, 50% planned timing
   - Can be tuned per operation (e.g., 0.7 for more aggressive)
   - Exposed via env variable and API

3. **Departure detection based on speed threshold**
   - Simple and reliable
   - 10 knots = clear distinction from ground operations
   - Persists until route deactivated

4. **Graceful degradation**
   - If timing data unavailable: use current speed (existing behavior)
   - If some waypoints lack times: skip blending for that segment
   - If route not active: use simple great-circle distance ETA

### Configuration Example

```python
# .env
ETA_BLENDING_FACTOR=0.5  # 50% actual, 50% plan
DEPARTURE_SPEED_THRESHOLD_KNOTS=10
ENABLE_ROUTE_TIMING=true
ETA_DEFAULT_SPEED_KNOTS=400
```

### Sample Output (Pre-flight)

```json
{
  "poi_id": "waypoint_1",
  "poi_name": "APPCH",
  "distance_meters": 62800,
  "eta_seconds": 402,  // 6m 42s
  "expected_arrival_time": "2025-10-27T16:57:55Z",
  "is_expected_timing": true,
  "is_pre_departure": true
}
```

### Sample Output (In-flight)

```json
{
  "poi_id": "waypoint_2",
  "poi_name": "TOC",
  "distance_meters": 28900,
  "eta_seconds": 187,  // 3m 7s (actual speed faster than expected)
  "expected_arrival_time": "2025-10-27T17:02:32Z",
  "expected_segment_speed_knots": 598,
  "actual_speed_knots": 650,
  "blending_factor": 0.5,
  "is_expected_timing": true,
  "is_pre_departure": false
}
```

---

## Next Steps

1. ✅ Create planning documents (this phase)
2. ⬜ Phase 1: Extend data models with timing fields
3. ⬜ Phase 2: Enhance KML parser to extract timestamps
4. ⬜ Phase 3: Implement route-aware ETA calculator with blending
5. ⬜ Phase 4: Integrate with simulator
6. ⬜ Phase 5: Update Grafana dashboard and metrics
7. ⬜ Phase 6: Comprehensive testing and documentation

---

**Document Status:** ✅ Ready for Implementation
**Approval:** Pending User Review
