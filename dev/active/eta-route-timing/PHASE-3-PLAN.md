# Phase 3: API Integration & Endpoints - Detailed Plan

**Objective:** Expose ETA route timing functionality through API endpoints, Prometheus metrics, and Grafana visualizations.

**Phase Status:** Ready to implement
**Session:** 20 (starting)
**Branch:** `feature/eta-route-timing`

---

## Executive Summary

Phase 3 builds on the timing data infrastructure created in Phases 1-2 by:

1. **Updating existing endpoints** to include timing metadata
2. **Creating new ETA calculation endpoints** for dynamic ETA queries
3. **Exposing timing data to Prometheus** for monitoring and alerting
4. **Enhancing Grafana dashboard** with timing visualizations

At the end of Phase 3, users will be able to:
- Query routes with timing information included
- Calculate ETAs to waypoints or specific locations
- Monitor timing metrics in Prometheus
- Visualize ETA information on the Grafana map

---

## Task 3.1: Update Route Response Endpoints

**Status:** Pending

### Current State

**RouteResponse model** already has:
- ✅ `has_timing_data: bool` field
- ❌ Missing: `timing_profile` (only in RouteDetailResponse)

**Endpoints to Update:**
1. `GET /api/routes` - List routes
2. `GET /api/routes/{route_id}` - Route details

### Implementation

#### 1.1 Update `RouteResponse` model
- Add `timing_profile: Optional[RouteTimingProfile]` field (optional, for backward compatibility)
- Update model docstring to explain timing fields

**File:** `backend/starlink-location/app/models/route.py`
```python
class RouteResponse(BaseModel):
    # ... existing fields ...
    has_timing_data: bool = Field(
        default=False,
        description="Whether route has embedded timing metadata"
    )
    timing_profile: Optional[RouteTimingProfile] = Field(
        default=None,
        description="Timing profile (if has_timing_data is True)"
    )
```

#### 1.2 Update `list_routes()` endpoint
- Populate `has_timing_data` from `parsed_route.timing_profile.has_timing_data`
- For list view, omit full timing_profile (keep responses lightweight)

**File:** `backend/starlink-location/app/api/routes.py:154-197`

#### 1.3 Update `get_route_detail()` endpoint
- Already includes full `timing_profile` in response
- Verify it's properly populated from `parsed_route.timing_profile`
- Add test coverage

**File:** `backend/starlink-location/app/api/routes.py:200-247`

### Testing

Create `test_route_endpoints_with_timing.py`:
- Test `list_routes()` includes `has_timing_data`
- Test `get_route_detail()` includes full `timing_profile`
- Test backward compatibility (routes without timing still work)
- Test serialization/deserialization of timing fields

---

## Task 3.2: Create ETA Calculation Endpoints

**Status:** Pending

### New Endpoints

#### 3.2.1 Calculate ETA to waypoint

**Endpoint:** `GET /api/routes/{route_id}/eta/waypoint/{waypoint_index}`

**Query Parameters:**
- `current_position_lat` (float, required) - Current latitude
- `current_position_lon` (float, required) - Current longitude
- `current_position_alt` (float, optional) - Current altitude

**Response:**
```json
{
  "waypoint_index": 5,
  "waypoint_name": "Checkpoint Alpha",
  "waypoint_lat": 40.7128,
  "waypoint_lon": -74.0060,
  "expected_arrival_time": "2025-10-27T17:30:00Z",
  "distance_remaining_meters": 50000,
  "distance_remaining_km": 50.0,
  "estimated_time_remaining_seconds": 300,
  "estimated_speed_knots": 500
}
```

**Logic:**
1. Get current position and parse route
2. Find nearest route point to current position
3. Calculate remaining distance from current to waypoint
4. Use segment speeds from timing_profile for speed estimation
5. Calculate ETA based on distance and speeds

#### 3.2.2 Calculate ETA to arbitrary location

**Endpoint:** `GET /api/routes/{route_id}/eta/location`

**Query Parameters:**
- `latitude` (float, required)
- `longitude` (float, required)
- `current_position_lat` (float, required)
- `current_position_lon` (float, required)

**Response:** Same as waypoint endpoint but with closest route point info

#### 3.2.3 Get route progress

**Endpoint:** `GET /api/routes/{route_id}/progress`

**Query Parameters:**
- `current_position_lat` (float, required)
- `current_position_lon` (float, required)

**Response:**
```json
{
  "current_waypoint_index": 3,
  "current_waypoint_name": "Checkpoint B",
  "progress_percent": 35.2,
  "total_route_distance_meters": 250000,
  "distance_completed_meters": 87500,
  "distance_remaining_meters": 162500,
  "expected_total_duration_seconds": 3600,
  "expected_duration_remaining_seconds": 2340,
  "average_speed_knots": 500
}
```

### Implementation Files

**New file:** `backend/starlink-location/app/services/eta_calculator.py`

```python
class ETACalculator:
    """Calculate ETAs and route progress for active routes."""

    def __init__(self, parsed_route: ParsedRoute):
        self.route = parsed_route

    def find_nearest_point(self, lat: float, lon: float) -> tuple[int, float]:
        """Find nearest route point and distance to it."""
        # Haversine distance calculation
        # Return (point_index, distance_meters)

    def calculate_eta_to_waypoint(
        self,
        waypoint_index: int,
        current_lat: float,
        current_lon: float
    ) -> dict:
        """Calculate ETA to specific waypoint."""
        # Logic here

    def calculate_eta_to_location(
        self,
        target_lat: float,
        target_lon: float,
        current_lat: float,
        current_lon: float
    ) -> dict:
        """Calculate ETA to arbitrary location."""

    def get_route_progress(
        self,
        current_lat: float,
        current_lon: float
    ) -> dict:
        """Calculate overall route progress."""
```

**Update file:** `backend/starlink-location/app/api/routes.py`

Add three new endpoints:
- `GET /api/routes/{route_id}/eta/waypoint/{waypoint_index}`
- `GET /api/routes/{route_id}/eta/location`
- `GET /api/routes/{route_id}/progress`

### Testing

Create `test_eta_calculator.py`:
- Test nearest point detection (multiple scenarios)
- Test ETA calculations with various speeds
- Test progress calculation
- Test with routes that have no timing data (should use default speed)
- Test edge cases (current position beyond route, etc.)

---

## Task 3.3: Prometheus Metrics for Timing

**Status:** Pending

### New Metrics

1. **Route Timing Metrics** (when route is active)
   - `starlink_route_total_duration_seconds{route_name="..."}` - Total expected flight time
   - `starlink_route_departure_time{route_name="..."}` - Departure timestamp
   - `starlink_route_arrival_time{route_name="..."}` - Arrival timestamp
   - `starlink_route_segment_count_with_timing{route_name="..."}` - Number of timed segments

2. **ETA Metrics** (dynamically calculated from current position)
   - `starlink_eta_to_waypoint_seconds{route_name="...", waypoint_name="..."}` - ETA to specific waypoint
   - `starlink_distance_to_waypoint_meters{route_name="...", waypoint_name="..."}` - Distance to waypoint
   - `starlink_route_progress_percent{route_name="..."}` - Progress along active route (already exists)
   - `starlink_route_segment_speed_knots{route_name="...", segment_index="..."}` - Segment speed

3. **Timing Data Quality Metrics**
   - `starlink_route_has_timing_data{route_name="..."}` - Binary: 1 if timing data present, 0 otherwise

### Implementation

**Update file:** `backend/starlink-location/app/api/metrics_export.py`

Add metric collection logic:
```python
from prometheus_client import Gauge, Counter

# Route timing metrics
route_total_duration = Gauge(
    'starlink_route_total_duration_seconds',
    'Total expected flight duration',
    ['route_name']
)

route_departure_time = Gauge(
    'starlink_route_departure_time',
    'Route departure time (Unix timestamp)',
    ['route_name']
)

# ETA metrics
eta_to_waypoint = Gauge(
    'starlink_eta_to_waypoint_seconds',
    'Estimated time to waypoint',
    ['route_name', 'waypoint_name']
)

distance_to_waypoint = Gauge(
    'starlink_distance_to_waypoint_meters',
    'Distance to waypoint',
    ['route_name', 'waypoint_name']
)
```

During metrics export:
1. Check if route is active
2. If active and has timing data:
   - Export route-level timing metrics
   - Calculate current ETAs for all waypoints
   - Export ETA metrics

### Testing

Create `test_timing_metrics.py`:
- Test metrics are exported for active routes with timing data
- Test metrics have correct labels
- Test metric values are reasonable (positive durations, future ETAs)
- Test metrics update when route changes

---

## Task 3.4: Grafana Dashboard Updates

**Status:** Pending

### Dashboard Changes

**File:** `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json`

#### 4.1 Add Timing Information Panel
- Display route timing profile (departure, arrival, duration)
- Show segment count with timing
- Update when active route changes

#### 4.2 Enhance Route Progress Panel
- Add ETA information
- Show remaining distance and time
- Add waypoint progress bars

#### 4.3 Add ETA Waypoint Table
- List all waypoints for active route
- Show expected arrival times
- Highlight upcoming waypoints
- Show distance/ETA to each

#### 4.4 Add Segment Speed Visualization
- Graph showing speed by segment
- Overlay on time series
- Help users understand route timing characteristics

### Specific Changes

1. **New variable:**
   - `$waypoint_index` - Current waypoint index (sourced from metrics)

2. **New panels:**
   - "Route Timing Profile" (stat panel showing departure/arrival/duration)
   - "Upcoming Waypoints" (table with ETA data)
   - "Segment Speeds" (time series graph)
   - "ETA to Destination" (large stat showing time remaining)

3. **Update existing panels:**
   - Route progress bar: Add ETA info
   - Map panel: Show waypoints with ETA markers

### Testing

Manual testing checklist:
- Upload route with timing data
- Activate route
- Verify timing panels display correctly
- Check waypoint table shows all waypoints with ETAs
- Verify ETA updates as position moves along route

---

## Task 3.5: Integration & System Tests

**Status:** Pending

### Test Coverage

#### 5.1 Route Response Integration Tests
- Test routes with and without timing data serialize correctly
- Test backward compatibility (old client code still works)
- Test filter by `has_timing_data=true`

#### 5.2 ETA Calculation Tests
- Test with real flight routes and timing data
- Verify ETA accuracy against known waypoint times
- Test edge cases (position ahead of route, position off-route)
- Test routes without timing data (should estimate or return null)

#### 5.3 End-to-End API Tests
- Upload route → activate → query ETA → verify response
- Test all three ETA endpoints with various inputs
- Test progress endpoint accuracy

#### 5.4 Metrics Integration Tests
- Verify metrics endpoint includes timing metrics
- Parse Prometheus metrics and validate values
- Test metrics update frequency

#### 5.5 Performance Tests
- Measure ETA calculation performance (should be <100ms)
- Test with large routes (1000+ points)
- Verify no memory leaks in repeated ETA queries

### Test Files to Create

1. `test_phase3_route_responses.py` - Route endpoint integration tests
2. `test_phase3_eta_endpoints.py` - ETA calculation endpoint tests
3. `test_phase3_metrics.py` - Prometheus metrics integration tests
4. `test_phase3_end_to_end.py` - Full workflow tests

---

## Success Criteria

Phase 3 completion requires:

### Code Quality
- ✅ All new code follows existing patterns and style
- ✅ Comprehensive docstrings and type hints
- ✅ No breaking changes to existing endpoints
- ✅ Backward compatible (routes without timing still work)

### Testing
- ✅ 40+ new unit tests (ETA calculator, endpoints)
- ✅ 15+ integration tests (full workflows)
- ✅ All tests passing
- ✅ >80% code coverage for new code

### Documentation
- ✅ Docstrings for all new endpoints and methods
- ✅ Update CLAUDE.md with new endpoint examples
- ✅ Grafana dashboard updates documented

### Functionality
- ✅ All 5 tasks completed
- ✅ ETA endpoints calculate correct values
- ✅ Metrics available in Prometheus
- ✅ Grafana dashboard displays timing information

---

## Risk Mitigation

**Risk:** ETA calculations are inaccurate

**Mitigation:**
- Use segment speeds from timing data (not estimates)
- Validate against known flight patterns
- Include confidence metrics
- Test with real KML files

**Risk:** Performance degradation with large routes

**Mitigation:**
- Implement caching for route data
- Use indexed lookups for nearest point
- Profile before/after implementation

**Risk:** Backward compatibility breaks

**Mitigation:**
- All timing fields are Optional
- Endpoints work with routes that have no timing
- Comprehensive integration tests

---

## Time Estimate

- Task 3.1: 1-2 hours (endpoint updates, testing)
- Task 3.2: 2-3 hours (ETA service, endpoints, testing)
- Task 3.3: 1-2 hours (metrics integration, testing)
- Task 3.4: 1-2 hours (dashboard updates, testing)
- Task 3.5: 2-3 hours (integration tests, validation)

**Total: 7-12 hours**

---

## Next Steps

1. Review and approve this plan
2. Begin Task 3.1 (route response updates)
3. Proceed sequentially through tasks
4. Update SESSION-NOTES.md after each task completion
5. Commit changes with clear commit messages

---

**Document Created:** 2025-11-03
**Session:** 20
**Status:** Ready for implementation approval
