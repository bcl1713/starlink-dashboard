# ETA Timing Modes Plan Updates

**Date:** 2025-11-04
**Updated By:** User feedback
**Version:** 1.1.0

## Summary of Changes

This document tracks updates made to the ETA Timing Modes implementation plan based on user feedback and requirements clarification.

---

## Change 1: Speed-Based Departure Detection

**Previous Approach:**
- Departure detected by comparing current time to scheduled departure time (5-minute buffer)
- Also checked distance from first waypoint (>1000m threshold)

**Updated Approach:**
- Departure detected when current speed exceeds **50 knots consistently**
- Speed must remain above threshold for 10+ seconds to prevent false positives
- Manual override still available via API

**Rationale:**
- More intuitive trigger point (clearly corresponds to takeoff/climb)
- Works for any departure time (scheduled or unscheduled)
- Prevents false positives from GPS noise or pre-flight taxi
- Aircraft-agnostic (50 knots is well below typical takeoff speeds)

**Files Updated:**
- `eta-timing-modes-plan.md` (lines 134-136, 224-228, 739-740)
- `eta-timing-modes-context.md` (lines 102-110, 173-175, 219-223, 327-330)

---

## Change 2: Intelligent Speed Calculation for Estimated Mode

**Previous Approach:**
- All estimated ETAs used current smoothed speed for entire remaining route
- Simple but potentially inaccurate for multi-segment routes

**Updated Approach:**
- **Future route segments:** Use calculated/scheduled segment speeds from route data
- **Current segment:** Blend current speed with expected speed based on segment progress
  - Formula: `blended_speed = (current_speed + expected_speed) / 2`
  - Balances real-time conditions with route plan
- **Off-route POIs:** Project to route first, then apply same logic

**Rationale:**
- More accurate ETAs by respecting planned speed changes between segments
- Current segment blending prevents excessive volatility from speed fluctuations
- Leverages existing route timing data for better predictions
- Reuses existing projection logic from RouteETACalculator

**Example Calculation:**
```
Scenario: Flight route KADW → KORD → PHNL
- Segment 1 (KADW-KORD): 600nm @ 350 knots (completed)
- Segment 2 (KORD-PHNL): 4,250nm @ 480 knots (current segment, 10% complete)

Current state:
- Position: 425nm from KORD
- Current speed: 460 knots (slower due to headwind)
- Expected speed: 480 knots (from route plan)

Calculation:
- Remaining in current segment: 3,825nm
- Blended speed: (460 + 480) / 2 = 470 knots
- Time for current segment: 3,825nm / 470 knots = 8.14 hours
- ETA to PHNL: current_time + 8.14 hours
```

**Files Updated:**
- `eta-timing-modes-plan.md` (lines 143-147, 271-278)
- `eta-timing-modes-context.md` (lines 134-153, 236-241, 359-368)

**Implementation Notes:**
- Off-route projection logic already exists in `RouteETACalculator.project_poi_to_route()`
- Speed blending will be implemented in new `_calculate_estimated_eta()` method
- Segment speed data available via `RouteTimingProfile.segment_speeds` (if timing data present)

---

## Change 3: Updated Configuration Constants

**Previous Constants:**
```python
DEPARTURE_TIME_BUFFER_SECONDS = 300  # 5 minutes
DEPARTURE_DISTANCE_THRESHOLD_M = 1000  # 1000 meters
ARRIVAL_DISTANCE_THRESHOLD_M = 100  # 100 meters
ARRIVAL_DWELL_TIME_SECONDS = 60  # 60 seconds
```

**Updated Constants:**
```python
DEPARTURE_SPEED_THRESHOLD_KNOTS = 50.0  # 50 knots
DEPARTURE_SPEED_PERSISTENCE_SECONDS = 10  # 10 seconds above threshold
ARRIVAL_DISTANCE_THRESHOLD_M = 100  # 100 meters
ARRIVAL_DWELL_TIME_SECONDS = 60  # 60 seconds
```

**Files Updated:**
- `eta-timing-modes-context.md` (lines 324-331)

---

## Change 4: Updated Test Coverage

**New Test Cases Added:**
- Speed persistence tracking (prevent false positives from brief speed spikes)
- Speed blending accuracy (current segment calculations)
- Future segment speed usage (route-aware calculations)
- Off-route POI projection with speed blending

**Files Updated:**
- `eta-timing-modes-context.md` (lines 348-368)

---

## Change 5: Updated Data Flow Diagrams

**Changes:**
- Pre-departure flow: Updated to show speed checking instead of time/distance
- Post-departure flow: Added speed persistence tracking step
- Estimated ETA calculation: Detailed speed blending logic

**Files Updated:**
- `eta-timing-modes-context.md` (lines 166-257)

---

## Impact Assessment

### Implementation Complexity
- **Change 1 (Speed-based detection):** Similar complexity, simpler logic (no time comparisons)
- **Change 2 (Speed blending):** Moderate increase in complexity, but cleaner architecture

### Performance Impact
- Negligible (speed checks are simple comparisons)
- Speed blending adds ~5 arithmetic operations per POI ETA calculation

### Testing Impact
- Slightly increased test coverage needed for speed blending logic
- Easier to test (speed thresholds simpler than time/distance combinations)

### User Experience Impact
- **Positive:** More intuitive departure trigger (clearly maps to takeoff)
- **Positive:** More accurate in-flight ETAs with speed blending
- **Positive:** Works regardless of scheduled departure time

---

## Implementation Checklist

- [x] Update `eta-timing-modes-plan.md` with new departure logic
- [x] Update `eta-timing-modes-context.md` with speed blending details
- [x] Add new architectural decision (Decision 4: Speed Blending)
- [x] Update configuration constants
- [x] Update data flow diagrams
- [x] Update test coverage requirements
- [ ] Implement FlightStateManager with speed-based detection (Phase 2)
- [ ] Implement speed blending in ETACalculator (Phase 3)
- [ ] Add unit tests for new logic (Phase 7)
- [ ] Update documentation (Phase 8)

---

## Backward Compatibility

All changes are implementation-only and do not affect the external API:
- API response format unchanged
- Metric labels unchanged
- Dashboard queries unchanged

Users will see:
- Departure now triggered by speed (transparent change)
- More accurate in-flight ETAs (improvement)

---

## References

- Main Plan: `eta-timing-modes-plan.md`
- Context Document: `eta-timing-modes-context.md`
- Task Checklist: `eta-timing-modes-tasks.md`

---

**Changelog Version:** 1.0.0
**Last Updated:** 2025-11-04
