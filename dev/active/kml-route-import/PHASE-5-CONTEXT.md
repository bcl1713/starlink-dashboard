# Phase 5: Technical Context & Integration Points

## Current Implementation Status

### Simulator System

**Location:** `backend/starlink-location/app/simulation/`

**Key Classes:**

1. **SimulationCoordinator** (`coordinator.py`)
   - Generates simulated telemetry data
   - Main update loop: `update()` method
   - Current behavior:
     - Updates position with simulated movement
     - Rotates heading smoothly
     - Updates network metrics (latency, throughput)
     - Calculates POI ETAs using ETA service
   - Initialization pattern: Takes config in `__init__`, called from `main.py`

2. **WaypointInterpolator** (`kml_follower.py`)
   - Interpolates position between waypoints
   - Methods: `interpolate(distance)` - gets position at distance along route
   - Used by RouteFollower

3. **RouteFollower** (`kml_follower.py`)
   - Core route following logic
   - Maintains current waypoint index
   - Methods: `update(speed_knots, time_delta)` - advances along route
   - Can get current position from interpolator

### Route System

**Location:** `backend/starlink-location/app/services/`

**Key Classes:**

1. **RouteManager** (`route_manager.py`)
   - Loads routes from `/data/routes/` directory
   - Properties:
     - `active_route` - Returns current active route or None
     - `routes` - Dict of all routes
   - Methods:
     - `set_active_route(route_id)` - Activates a route
     - `deactivate_route()` - Deactivates current route
   - Initialization: Created in `main.py` startup event

2. **Route Model** (`app/models/route.py`)
   - `Route` dataclass with:
     - `coordinates`: List of (lat, lon, alt) tuples
     - `metadata`: RouteMetadata with name, distance, etc.
   - All coordinates available via `.coordinates` property

### Metrics System

**Location:** `backend/starlink-location/app/core/metrics.py`

**Current Metrics:**
- Position: `starlink_dish_latitude_degrees`, etc.
- Speed: `starlink_dish_speed_knots`
- Heading: `starlink_dish_heading_degrees`
- Network: `starlink_network_latency_ms`, etc.
- POI: `starlink_eta_poi_seconds`, etc.

**Initialization Pattern:**
- Gauges created at module level
- Updated in coordinator via `set_value()` or `labels().set()`
- Exposed via `/metrics` endpoint (Prometheus format)

## Integration Points

### 1. Dependency Injection Pattern

**Current Pattern (ETA Service):**

```python
# main.py
eta_service = ETAService()  # Create instance
eta_service.set_route_manager(route_manager)  # Inject
set_eta_service_instance(eta_service)  # Global access

# app/api/ui.py
def set_eta_service_instance(service):
    global eta_service_instance
    eta_service_instance = service
```

**For Phase 5:** Apply same pattern to SimulationCoordinator

---

### 2. Update Cycle Integration

**Current Cycle (SimulationCoordinator.update()):**

```python
def update(self):
    # 1. Update position (simulated movement)
    # 2. Update speed (random variations)
    # 3. Update heading
    # 4. Calculate POI ETAs
    # 5. Update metrics
```

**Phase 5 Change:**

```python
def update(self):
    # NEW: Check for active route
    if self.route_manager and self.route_manager.active_route:
        # NEW: Use RouteFollower for position
        position = self.get_route_position()
    else:
        # EXISTING: Use simulated movement
        position = self.get_simulated_position()

    # REST: Same as before (POI ETAs, metrics, etc.)
```

---

### 3. Position Update Methods

**Existing (Simulator):**
- `SimulationCoordinator._update_position()` - Moves randomly
- `SimulationCoordinator._update_heading()` - Rotates smoothly

**New (Route-following):**
- `SimulationCoordinator._get_route_position()` - Uses RouteFollower
- `SimulationCoordinator._calculate_route_progress()` - Progress percentage

---

## Key Code Files to Review

### Priority 1 (Must Review First)

1. **`app/simulation/coordinator.py`** (~200 lines)
   - Lines 1-50: Class definition and __init__
   - Lines 60-120: update() method - where integration goes
   - Lines 130-180: Position/heading/metrics update methods
   - **Key insight:** update() is called every simulation cycle

2. **`app/simulation/kml_follower.py`** (~300 lines)
   - Lines 1-80: RouteFollower class API
   - Lines 20-40: __init__ - see how it takes waypoints
   - Lines 50-100: update() method - advances along route
   - Lines 110-150: get_current_position() - returns Lat/Lon/Alt

3. **`main.py` startup** (~50 lines)
   - Lines 40-60: Startup event, where services initialized
   - **Key insight:** This is where RouteManager gets injected to coordinator

### Priority 2 (Reference Only)

4. **`app/core/metrics.py`** (~100 lines relevant)
   - Lines 1-30: Gauge definitions
   - Lines 200-250: Where new progress metrics go

5. **`app/services/route_manager.py`** (~150 lines)
   - Lines 1-50: Class definition, properties
   - Line 15: `active_route` property - returns Route or None
   - Line 30: Route structure - has `.coordinates` list

6. **`config.yaml`** (~30 lines)
   - Structure for adding new config options
   - Where to add `route_completion_behavior`

---

## Code References for Phase 5

### Accessing Active Route

```python
# In SimulationCoordinator after RouteManager injected:
if self.route_manager.active_route:
    route = self.route_manager.active_route
    coordinates = route.coordinates  # List of (lat, lon, alt)
```

### Using RouteFollower

```python
# Create instance
self.route_follower = RouteFollower(coordinates)

# Update each cycle
self.route_follower.update(speed_knots=self.speed, time_delta=delta_time)

# Get current position
position = self.route_follower.get_current_position()
lat, lon, alt = position.latitude, position.longitude, position.altitude

# Get progress
progress_pct = self.route_follower.get_progress_percentage()
waypoint_idx = self.route_follower.current_waypoint_index
```

### Creating Metrics

```python
# In app/core/metrics.py
route_progress = Gauge(
    'starlink_route_progress_percent',
    'Route progress percentage',
    ['route_name']
)

# In SimulationCoordinator
route_progress.labels(route_name=route.metadata.name).set(progress_pct)
```

---

## Configuration Approach

### Current config.yaml Structure

```yaml
simulation:
  initial_latitude: 41.6
  initial_longitude: -74.0
  speed_knots: 350
```

### Phase 5 Addition

```yaml
simulation:
  # ... existing ...
  route_completion_behavior: loop  # or 'stop', 'reverse'
```

---

## Testing Strategy

### Unit Tests (Run locally)
- Test RouteFollower with sample coordinates
- Test progress calculation
- Test completion behavior logic

### Integration Tests (With Docker)
- Upload route via web UI
- Activate in simulator mode
- Monitor metrics in Prometheus
- Watch Grafana for position updates
- Verify POI ETAs still work

### Test Routes Available

All in current directory:
- Leg 1 Rev 6.kml - KADW→PHNL (49 points)
- Leg 2 Rev 6.kml - PHNL→RJTY (30 points)
- Leg 3 Rev 6.kml - RJTY→WMSA (65 points)
- Leg 4 Rev 6.kml - WMSA→VVNB (35 points)
- Leg 5 Rev 6.kml - VVNB→RKSO (51 points)
- Leg 6 Rev 6.kml - RKSO→KADW (88 points)

---

## Known Constraints

1. **Simulator Cycle Speed:** update() called ~1x per second (configurable)
2. **Route Data:** Coordinates are static, loaded once at activation
3. **POI Integration:** ETA service already receives lat/lon, works automatically
4. **Metric Exposure:** Prometheus scrapes every 1-15 seconds (configurable)

---

## Success Metrics for Phase 5

✅ SimulationCoordinator accepts RouteManager via injection
✅ update() checks for active_route and uses RouteFollower
✅ Position follows route waypoints in correct sequence
✅ Progress metrics appear in `/metrics` endpoint
✅ All 6 test routes follow without errors
✅ POI ETAs calculate correctly with route-following position
✅ No performance degradation (metrics update at same rate)

---

**Last Updated:** 2025-11-02
**Status:** Ready for Phase 5.1 Review
