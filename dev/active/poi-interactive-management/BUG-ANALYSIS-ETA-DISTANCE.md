# Bug Analysis: Distance and ETA Calculation Issues

**Date:** 2025-10-31
**Severity:** HIGH
**Status:** IDENTIFIED - Root cause determined

---

## Problem Summary

Test 3 (and other dynamically added POIs) show incorrect distance and ETA values in the dashboard. According to the screenshot, Test 3 should be the "next POI" but the ETA and distance calculations appear off.

**Screenshot Data (from 2025-10-30-222821_hyprshot.png):**
- Test 3 location: 39.76105, -74.09798
- Displayed ETA: ~99.6 minutes
- Displayed distance: appears as ~25 km in tooltip
- Status: Listed as next destination but with suspicious timing

---

## Root Cause Analysis

### The Core Issue

The `/api/pois/etas` endpoint uses **hardcoded fallback coordinates** instead of the actual current position:

**In `app/api/pois.py` (lines 119-144):**
```python
# Always use fallback coordinates for now
# TODO: Fix coordinator integration for dynamic current position
# Hardcoded fallback to 41.6, -74.0 with 67 knots speed
if latitude is None or not latitude:
    latitude = 41.6
else:
    # ... conversion attempts ...
```

### What's Actually Happening

1. **Current Position Fallback:** `41.6°N, 74.0°W` (stationary reference point)
2. **Test 3 Position:** `39.76105°N, 74.09798°W` (placed in southern part of route)
3. **Actual Distance:** `204.65 km` (over 200 kilometers south)
4. **Calculated ETA at 67 knots:** `98.96 minutes` ✅ **This is CORRECT**

### Why It Looks Wrong

The distance **is** being calculated correctly:
- Haversine formula ✅ Correct implementation
- Speed conversion ✅ Correct (knots → nautical miles → seconds)
- ETA formula ✅ Correct (distance / speed * 3600)

**The problem is the CURRENT POSITION being used for calculations is wrong.**

---

## Evidence

### Manual Verification

```python
# Hardcoded position (what's being used)
Current: 41.6°N, -74.0°W

# Test 3 (from database)
Target: 39.76105°N, -74.09798°W

# Distance calculation verification
Distance = 204,648.72 meters = 204.65 km = 110.5 nm
ETA at 67 knots = (110.5 nm / 67 knots) * 3600 = 5937.39 seconds = 98.96 minutes
```

This matches exactly what the endpoint returns!

### What's Being Returned

```json
{
  "poi_id": "test-3",
  "name": "Test 3",
  "latitude": 39.76105,
  "longitude": -74.09798,
  "eta_seconds": 5937.392211908409,
  "distance_meters": 204648.7153395675,
  "bearing_degrees": 182.34584420798603
}
```

The calculations are **mathematically correct** - the issue is the input coordinates are wrong!

---

## Why This Matters

**Test 3 is NOT actually the next POI.** It's 200km away because:

1. The endpoint doesn't have access to real-time position from the coordinator
2. It falls back to a hardcoded reference point
3. Any POI's distance is calculated from this fixed point, not the actual moving position
4. This makes all ETA/distance values statically wrong

### The TODO Comment Confirms This

From `pois.py:119-121`:
```python
# Always use fallback coordinates for now
# TODO: Fix coordinator integration for dynamic current position
# Hardcoded fallback to 41.6, -74.0 with 67 knots speed
```

This was identified as a known limitation but never fixed.

---

## Impact Analysis

| Component | Current Behavior | Expected Behavior |
|-----------|------------------|-------------------|
| **Distance Display** | Calculated from fixed 41.6,-74.0 | Should use current position from coordinator |
| **ETA Display** | Based on static position | Should update as position changes |
| **POI List Ordering** | Sorted by distance from fixed point | Should sort by distance from actual position |
| **"Next Destination"** | May not be actually next | Should reflect actual closest POI |
| **Grafana Tooltips** | Show correct math but wrong base position | Should show accurate real-time ETAs |

---

## Technical Details

### Where the Issue Originates

**File:** `/backend/starlink-location/app/api/pois.py`
**Functions Affected:**
- `get_pois_with_etas()` (line 93-189)
- `get_next_destination()` (line 207-249)
- `get_next_eta()` (line 252-291)
- `get_approaching_pois()` (line 294-334)

All use the same fallback pattern.

### Why Access to Coordinator is Missing

The `_coordinator` object is set by `pois.set_coordinator()` in `main.py:87`, but the endpoints **don't use it**:

```python
# Global coordinator reference for accessing telemetry
_coordinator: Optional[object] = None

def set_coordinator(coordinator):
    """Set the simulation coordinator reference."""
    global _coordinator
    _coordinator = coordinator
```

The coordinator is set but **never called** to get current position!

---

## Solution Approach

### Option 1: Use Coordinator Current Position (RECOMMENDED)

Extract current position from coordinator before calculating ETAs:

```python
@router.get("/etas", response_model=POIETAListResponse)
async def get_pois_with_etas(
    route_id: Optional[str] = Query(None),
    # ... other params ...
) -> POIETAListResponse:
    # Get current position from coordinator
    if _coordinator:
        current_state = _coordinator.get_current_state()
        latitude = current_state.latitude
        longitude = current_state.longitude
        speed_knots = current_state.speed_knots
    else:
        # Fallback only if no coordinator available
        latitude, longitude, speed_knots = 41.6, -74.0, 67.0

    # ... rest of calculation ...
```

### Option 2: Add Query Parameters for Position

Modify Grafana queries to pass actual coordinates:

```python
# Grafana would pass: ?latitude=${current_lat}&longitude=${current_lon}
# Python would use those instead of fallback
```

### Option 3: Create New Dedicated Endpoint

Separate internal ETA endpoint that takes current position from coordinator:

```python
@router.get("/etas/real-time")
async def get_real_time_etas() -> POIETAListResponse:
    """Get ETAs using actual current position from coordinator."""
```

---

## What's Working Correctly

✅ **Haversine Distance Formula** - Mathematically correct
✅ **ETA Calculation** - Formula is sound (distance / speed * 3600)
✅ **Bearing Calculation** - Correctly computed bearing angles
✅ **POI List Ordering** - Correctly sorts by calculated values
✅ **Grafana Integration** - Panels correctly render the data provided

---

## What's Broken

❌ **Input Coordinates** - Using hardcoded fallback instead of actual position
❌ **Real-time Updates** - No connection to coordinator's telemetry stream
❌ **Dynamic Position Tracking** - Treated as static fixed point

---

## Recommended Fix Priority

**Phase 6 (Next Sprint):**
- Task 6.1: Update POI endpoints to use coordinator position
- Task 6.2: Verify distance calculations with live position data
- Task 6.3: Test ETA accuracy with simulated movement
- Task 6.4: Update Grafana queries if needed

---

## Files Requiring Changes

1. `/backend/starlink-location/app/api/pois.py` (4 functions)
2. Potentially: Grafana dashboard queries (if we change parameter format)

---

## Testing Plan

After fix implementation:

1. **Manual Testing:**
   - Create POI at known distance
   - Verify ETA matches expected calculation
   - Test as position changes in simulation

2. **Automated Testing (Future):**
   - Unit test with fixed positions
   - Integration test with coordinator mock
   - E2E test with simulation mode

3. **Validation Checks:**
   - ETA decreases as position approaches POI
   - Distance decreases as position approaches POI
   - POI order changes dynamically
   - "Next destination" updates correctly

---

## Solution Implemented ✅

**Status:** FIXED - 2025-10-31

### Changes Made

Updated all four POI stat endpoints in `app/api/pois.py`:

1. **`get_pois_with_etas()`** (lines 93-200)
   - Now calls `_coordinator.get_current_telemetry()` to get real-time position
   - Falls back to query parameters only if coordinator unavailable
   - Uses actual speed from coordinator for accurate ETA

2. **`get_next_destination()`** (lines 218-275)
   - Retrieves closest POI based on real current position
   - Updates dynamically as position changes

3. **`get_next_eta()`** (lines 278-333)
   - Returns accurate ETA using coordinator telemetry
   - Changes as position progresses along route

4. **`get_approaching_pois()`** (lines 336-392)
   - Correctly identifies POIs within 30-minute window
   - Uses actual position and speed

### Verification Results

**Test Case:** JFK Airport POI
- **Distance Calculation:** ✅ Perfect match (88,307.14 meters)
- **ETA Calculation:** ✅ Perfect match (17,019.61 seconds = 4.73 hours at 10.09 knots)
- **Formula Accuracy:** ✅ Verified against manual calculation
- **Dynamic Updates:** ✅ Values update as position changes

### Before vs After

**BEFORE (Hardcoded Fallback):**
- Position: Always 41.6°N, -74.0°W
- Speed: Always 67 knots
- Distance: Static, doesn't reflect actual position
- ETA: Never updates relative to actual movement

**AFTER (Coordinator Integration):**
- Position: Real-time from coordinator (41.611809°N, -73.976251°W)
- Speed: Real-time from coordinator (10.085737 knots)
- Distance: Calculated from actual current position
- ETA: Updates as position progresses

## Conclusion

The ETA and distance calculation **formulas were always correct**. The issue was that the endpoints used a hardcoded fallback position instead of the actual current position from the coordinator.

**This was an integration bug, not a math bug.**

The fix successfully integrates the POI endpoints with the coordinator's real-time telemetry stream, enabling accurate, dynamic ETA calculations for all POIs.

