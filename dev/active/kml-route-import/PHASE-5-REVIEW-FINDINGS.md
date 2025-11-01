# Phase 5.1 Review Findings - Route Following Code Analysis

**Date:** 2025-11-02
**Reviewer:** Claude Code
**Status:** Complete - Ready for Phase 5.2 Integration

---

## Executive Summary

The existing code infrastructure is well-designed and mostly ready for Phase 5 integration. The `KMLRouteFollower` class provides all necessary functionality to follow routes. The main work in Phase 5.2 will be connecting it to `SimulationCoordinator` and integrating with `RouteManager`.

**Key Finding:** The simulator architecture is clean and modular. We can add route-following without disrupting existing functionality.

---

## 1. KMLRouteFollower Analysis (`app/simulation/kml_follower.py`)

### Class Purpose
Follows a KML route during simulation with realistic position deviations.

### Constructor
```python
def __init__(self, route: ParsedRoute, deviation_degrees: float = 0.0005)
```
- Takes a `ParsedRoute` object (from Phase 4 implementation)
- Optional deviation parameter for realistic off-route positioning
- Initializes progress tracking (0.0 to 1.0)
- Calculates total route distance on init

### Key Methods

#### 1. `get_position(progress: float) -> dict`
**Purpose:** Get position at a specific progress point (0.0-1.0)

**Returns:**
```python
{
    "latitude": float,
    "longitude": float,
    "altitude": float or None,
    "heading": float (0-360),
    "sequence": int (waypoint index),
    "progress": float (0.0-1.0)
}
```

**How it works:**
1. Normalizes progress to 0-1 range (wraps for looping)
2. Calculates distance along route: `distance = progress * total_distance`
3. Finds which segment the distance falls into
4. Interpolates lat/lon/alt within that segment
5. Calculates heading based on next waypoint direction
6. Adds realistic deviation (±0.0005° by default)
7. Returns complete position dictionary

**Integration Notes:**
- Progress is the KEY input - we need to update this each simulator cycle
- Deviation is realistic but can be disabled by setting to 0.0
- Handles altitude interpolation (needed for our 3D routes)

#### 2. `reset() -> None`
Resets progress to 0.0 and waypoint index to 0. Useful for:
- Starting a new route
- Completing route (if "loop" mode)
- Manual reset via API

#### 3. Utility Methods
- `get_total_distance()` → Route distance in meters
- `get_point_count()` → Number of waypoints
- `get_route_name()` → Route name from metadata

### What It Does Well
✅ Handles progress-based interpolation correctly
✅ Calculates proper headings using bearing formula
✅ Supports altitude interpolation
✅ Uses Haversine formula for accurate distance/heading calculations
✅ Adds realistic deviation automatically

### What We Need to Add
- Track current waypoint index (partially implemented, needs exposure)
- Implement completion behaviors (loop/stop/reverse)
- Integrate with SimulationCoordinator's update cycle

---

## 2. SimulationCoordinator Analysis (`app/simulation/coordinator.py`)

### Class Purpose
Orchestrates all simulators (position, network, obstruction) and maintains state.

### Constructor
```python
def __init__(self, config: SimulationConfig)
```
Takes a `SimulationConfig` and initializes:
- `PositionSimulator` - Updates position
- `NetworkSimulator` - Simulates network metrics
- `ObstructionSimulator` - Simulates signal obstruction
- `SpeedTracker` - Tracks GPS-based speed

### Update Cycle
**Method:** `update() -> TelemetryData`

**Current Flow:**
1. Call `position_sim.update()` to get new position
2. Call `speed_tracker.update()` with position to calculate speed
3. Call `network_sim.update()` for network metrics
4. Call `obstruction_sim.update()` for obstruction data
5. Calculate environmental data (signal quality, uptime)
6. Return complete `TelemetryData`

**Called:** From background loop in `main.py` (line 205), approximately once per second

### Key Properties
- `mode` property returns "simulation" (used for health checks)
- `get_current_telemetry()` returns last generated telemetry
- `reset()` resets all simulators

### Injection Pattern
**Current Pattern (Example: How ETA Service is injected):**
```python
# In main.py (line 91-95)
initialize_eta_service(poi_manager)

# In app/api/ui.py (or similar)
def set_eta_service_instance(service):
    global eta_service_instance
    eta_service_instance = service
```

**For Phase 5:** We'll follow the SAME pattern to inject RouteManager

### Where to Add Route Following
**Location:** In `_generate_telemetry()` method after position update (line 88)

```python
# After line 88:
position_data = self.position_sim.update()

# ADD HERE: Check for active route and override position
if self._should_follow_route():
    position_data = self._get_route_position()
```

---

## 3. PositionSimulator Analysis (`app/simulation/position.py`)

### How It Currently Works
1. **Tracks progress** (0.0-1.0) along a pre-generated route
2. **Updates progress** based on speed and time elapsed
3. **Gets position** from route using `route.get_segment(progress)`
4. **Tracks heading** using `HeadingTracker` based on movement

### Key Methods
- `update()` - Called each cycle, returns PositionData
- `set_progress(progress)` - Manual progress control
- `_update_progress()` - Updates based on speed * time
- `_update_speed()` - Simulates realistic speed variations

### What We Need to Know
- **Progress is stored as:** `self.progress` (0.0-1.0)
- **Position calculation:** Uses `self.route.get_segment(progress)`
- **Can be overridden:** We can set progress directly via `set_progress()`
- **Or replaced:** We can use our own KMLRouteFollower instead

### Integration Strategy
We have TWO options:
1. **Wrap PositionSimulator:** Have it check for active route
2. **Replace in Coordinator:** Override position directly in coordinator.update()

**Recommendation:** Option 1 - Modify `PositionSimulator` to accept optional `KMLRouteFollower`
- Cleaner separation of concerns
- Easier to test
- Maintains existing interface

---

## 4. RouteManager Integration

### What RouteManager Provides (from `main.py` lines 119-137)
- Already initialized in startup
- Already injected into multiple modules
- Properties:
  - `active_route` → Returns current `ParsedRoute` or None
  - `routes` → Dict of all routes
- Methods:
  - `set_active_route(route_id)`
  - `deactivate_route()`
  - `start_watching()` - Watches for KML file changes

### How to Access It
**In main.py startup (already exists):**
```python
_route_manager = RouteManager()  # Line 122
```

**Then inject:**
```python
coordinator.set_route_manager(_route_manager)  # TO BE ADDED
```

### Available Route Data
From `ParsedRoute`:
```python
route.metadata.name        # Route name
route.points              # List of RoutePoint objects
route.get_total_distance()  # Total distance in meters
route.get_bounds()        # Min/max lat/lon
```

From `RoutePoint`:
```python
point.latitude
point.longitude
point.altitude
point.sequence
```

---

## 5. Metrics System (`app/core/metrics.py`)

### How Metrics Work
- Gauges defined at module level
- Updated in `SimulationCoordinator._generate_telemetry()`
- Exposed via `/metrics` endpoint (Prometheus format)

### Example Gauge Creation
```python
starlink_dish_latitude_degrees = Gauge(
    'starlink_dish_latitude_degrees',
    'Dish latitude in decimal degrees',
    ['region']  # Optional labels
)
```

### How to Update
```python
starlink_dish_latitude_degrees.set(value)
# Or with labels:
starlink_dish_latitude_degrees.labels(region='us').set(value)
```

### For Phase 5 Progress Metrics
We need to add:
```python
starlink_route_progress_percent = Gauge(
    'starlink_route_progress_percent',
    'Current progress along active route (0-100)',
    ['route_name']
)

starlink_current_waypoint_index = Gauge(
    'starlink_current_waypoint_index',
    'Index of current waypoint in route',
    ['route_name']
)
```

---

## 6. Main.py Startup Pattern

### Current Injection Pattern (lines 104-117)
```python
# 1. Initialize service
poi_manager = POIManager()

# 2. Inject into API modules
pois.set_poi_manager(poi_manager)
routes.set_poi_manager(poi_manager)
geojson.set_poi_manager(poi_manager)
```

### For Phase 5 (to be added after line 137)
```python
# Inject RouteManager into SimulationCoordinator
if isinstance(_coordinator, SimulationCoordinator):
    _coordinator.set_route_manager(_route_manager)
    logger.info_json("RouteManager injected into SimulationCoordinator")
```

---

## Integration Design: Phase 5.2 Approach

### Option A: Modify PositionSimulator (RECOMMENDED)
**Pros:**
- Cleaner - keeps route logic in position simulator
- Less change to coordinator
- Easier to test independently

**Steps:**
1. Add `KMLRouteFollower` property to `PositionSimulator`
2. Add setter: `set_route_follower(follower)`
3. In `PositionSimulator.update()`, check if follower exists
4. If follower: use its `get_position()` for position
5. If no follower: use existing route logic

### Option B: Override in Coordinator
**Pros:**
- Simpler for coordinator
- Route logic centralized

**Cons:**
- Changes coordinator architecture more
- Duplicates some position logic

### Recommendation
**Use Option A** - Modify PositionSimulator because:
1. Keeps route-following logic in one place (position simulator)
2. Minimal changes to coordinator
3. Easier to maintain and debug
4. Follows single-responsibility principle

---

## Phase 5.2 Implementation Plan

### Step 1: Add RouteManager Injection to Coordinator
**File:** `backend/starlink-location/app/simulation/coordinator.py`
```python
# In __init__:
self.route_manager = None

# Add method:
def set_route_manager(self, manager):
    self.route_manager = manager
```

### Step 2: Add KMLRouteFollower to PositionSimulator
**File:** `backend/starlink-location/app/simulation/position.py`
```python
# In __init__:
self.route_follower = None
self.route_completion_behavior = "loop"

# Add method:
def set_route_follower(self, follower, completion_behavior="loop"):
    self.route_follower = follower
    self.route_completion_behavior = completion_behavior

# Modify update():
if self.route_follower:
    position_dict = self.route_follower.get_position(self.progress)
    # Convert dict to PositionData
else:
    # existing logic
```

### Step 3: Wire Them in Coordinator
**File:** `backend/starlink-location/app/simulation/coordinator.py`
```python
# In _generate_telemetry() or update():
if self.route_manager and self.route_manager.active_route:
    route = self.route_manager.active_route
    follower = KMLRouteFollower(route)
    self.position_sim.set_route_follower(follower, config.route_completion_behavior)
```

### Step 4: Inject in main.py
**File:** `backend/starlink-location/main.py`
```python
# After line 137:
if isinstance(_coordinator, SimulationCoordinator):
    _coordinator.set_route_manager(_route_manager)
```

---

## Key Code References for Phase 5.2

### KMLRouteFollower Usage
```python
from app.simulation.kml_follower import KMLRouteFollower

# Initialize
follower = KMLRouteFollower(route=ParsedRoute, deviation_degrees=0.0005)

# Get position
pos_dict = follower.get_position(progress=0.5)  # progress: 0.0-1.0

# Access components
lat = pos_dict["latitude"]
lon = pos_dict["longitude"]
alt = pos_dict["altitude"]
heading = pos_dict["heading"]
progress = pos_dict["progress"]

# Reset
follower.reset()
```

### RouteManager Usage
```python
# Check for active route
if self.route_manager.active_route:
    route = self.route_manager.active_route
    name = route.metadata.name
    total_distance = route.get_total_distance()
    points = route.points
```

### Metrics Update
```python
from app.core.metrics import update_metrics_from_telemetry

# Or directly:
starlink_route_progress_percent.labels(route_name=name).set(progress_pct)
```

---

## Edge Cases to Handle

1. **No active route**
   - Route follower is None
   - Use existing PositionSimulator logic

2. **Route with 0 coordinates**
   - Check `len(route.points) < 2`
   - Skip route mode, use simulator

3. **Progress beyond route end**
   - KMLRouteFollower handles with `progress % 1.0`
   - Returns last point if past end

4. **Route changes during simulation**
   - RouteManager's `active_route` updates
   - Check each cycle for new active route
   - Reinitialize KMLRouteFollower if route changed

5. **Speed transitions**
   - When following route: Speed still updated by SpeedTracker
   - Speed affects progress (if we let PositionSimulator handle it)
   - Or we can use KMLRouteFollower's progress directly

---

## Testing Checklist for Phase 5.2

After implementation:
- [ ] Load KMLRouteFollower with test route
- [ ] Verify `get_position()` returns correct structure
- [ ] Test progress from 0.0 to 1.0
- [ ] Verify heading changes as route direction changes
- [ ] Test with/without active route
- [ ] Verify route switching works
- [ ] Check coordinate values match route points
- [ ] Monitor logs for any errors

---

## Success Criteria for Phase 5.1 Review

✅ Understood KMLRouteFollower API and capabilities
✅ Identified integration point in SimulationCoordinator
✅ Reviewed dependency injection pattern
✅ Determined integration approach (modify PositionSimulator)
✅ Documented edge cases and testing strategy
✅ Created detailed implementation plan

**Ready for Phase 5.2: Simulator Integration**

---

**Next:** Begin Phase 5.2 implementation with PositionSimulator modification
