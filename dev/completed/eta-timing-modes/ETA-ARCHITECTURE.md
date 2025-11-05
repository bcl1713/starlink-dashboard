# ETA Calculation Architecture Analysis

**Analysis Date:** 2025-11-04
**Project:** Starlink Dashboard Dev
**Branch:** feature/eta-route-timing
**Status:** Session 28 - Dashboard ETA Fix In Progress

---

## 1. CURRENT ETA IMPLEMENTATION ARCHITECTURE

### 1.1 Core ETA Calculation Components

#### A. ETACalculator (Primary Calculator)
**Location:** `backend/starlink-location/app/services/eta_calculator.py`

**Responsibilities:**
- Speed smoothing using 120-second rolling window average
- Distance calculations using Haversine formula
- ETA calculations for POIs
- Route-aware ETA calculations (new in Session 28)
- POI passing detection (100m threshold)

**Key Methods:**
- `calculate_eta(distance_meters, speed_knots)` - Basic ETA calculation
- `calculate_poi_metrics(current_lat, current_lon, pois, speed_knots, active_route)` - Calculate ETA for all POIs
- `_calculate_route_aware_eta(current_lat, current_lon, poi, active_route)` - NEW: Route-aware calculation

**Speed Calculation:**
```
ETA (seconds) = Distance (meters) / 1852.0 / Speed (knots) * 3600.0
```

**Special Cases:**
- Returns -1.0 for speeds < 0.5 knots (stationary)
- Tracks passed POIs to avoid recalculating for distant POIs

#### B. RouteETACalculator (Route-Specific Calculator)
**Location:** `backend/starlink-location/app/services/route_eta_calculator.py`

**Responsibilities:**
- Segment-by-segment distance calculations
- Route progress tracking
- Waypoint arrival time extraction from timing data
- POI projection onto route path
- ETA calculations using route timing profiles

**Key Features:**
- Projects POIs onto route segments to find nearest point
- Calculates progress percentage along route
- Supports routes with and without timing data
- Caches ETA calculations with 5-second TTL

#### C. ETA Service (Singleton Manager)
**Location:** `backend/starlink-location/app/core/eta_service.py`

**Responsibilities:**
- Maintains singleton ETACalculator instance
- Initializes ETA service on startup
- Coordinates metric updates with active route context
- Handles speed smoothing initialization (120s window)

**Key Function:**
```python
update_eta_metrics(latitude, longitude, speed_knots, active_route=None)
```
- Updates speed in calculator
- Calculates metrics for all POIs
- Passes active_route for route-aware calculations

---

## 2. DATA FLOW: HOW ETA VALUES GET TO DASHBOARD

### 2.1 Metrics Export Pipeline

**Flow:**
1. **Coordinator Background Loop** (`main.py`)
   - Runs every update_interval_seconds (default: 1 second)
   - Gets current telemetry (position, speed, heading)
   - Gets active route if one exists

2. **Metrics Update** (`app/core/metrics.py`)
   - `update_metrics_from_telemetry(telemetry, active_route)`
   - Calls `update_eta_metrics()` from eta_service

3. **ETA Service** (`app/core/eta_service.py`)
   - `update_eta_metrics(latitude, longitude, speed_knots, active_route=None)`
   - Calls `calculate_poi_metrics()` on calculator
   - Returns metric dict for all POIs

4. **Prometheus Metrics**
   - Metrics exported via `/metrics` endpoint
   - Labels: `name` and `category`
   - Values: `eta_seconds` and `distance_meters`

### 2.2 API Endpoint Pipeline

**Flow:**
1. **Dashboard requests:** `/api/pois/etas` endpoint
   - Calls `get_pois_with_etas()` in `app/api/pois.py`
   - Gets current position and speed from coordinator
   - Gets active route if one exists

2. **POI ETA Calculation**
   - For each POI, calculates:
     - Distance (Haversine)
     - ETA (route-aware if active route, else distance/speed)
     - Bearing to POI
     - Course status (on_course, slightly_off, off_track, behind)
     - Route projection data (if active route)

3. **Response Format:** `POIWithETA` model
   - Includes ETA, distance, bearing, course status
   - Includes route projection fields
   - Includes route_aware_status (ahead_on_route, already_passed, not_on_route, pre_departure)

### 2.3 Flight State & Dashboard Metadata (Session 11+)

- **FlightStateManager integration**
  - Tracks `active_route_id`, scheduled departure/arrival, and automatic countdowns
  - Provides `time_until_departure_seconds` and `time_since_departure_seconds` in status snapshots
  - Manual triggers (`/api/flight-status/depart` and `/api/flight-status/arrive`) update Prometheus + API in sync
- **Prometheus extensions**
  - `starlink_time_until_departure_seconds` drives countdown panels (0 once departed, maps to "Departed")
  - `starlink_eta_poi_seconds` and `starlink_distance_to_poi_meters` now carry an `eta_type` label (`anticipated` vs `estimated`)
- **API enhancements**
  - `/api/flight-status` response includes route metadata, countdown values, and timestamps
  - POI stats endpoints (`/api/pois/stats/next-destination`, `/api/pois/stats/next-eta`) surface `eta_type` and `flight_phase`
- **Grafana dashboards**
  - Stat tables render ETA mode badges (planned/live) via value mappings
  - New countdown panels visualize `starlink_time_until_departure_seconds`

---

## 3. ROUTE TIMING DATA STRUCTURE

### 3.1 RouteTimingProfile
**Location:** `backend/starlink-location/app/models/route.py`

```python
class RouteTimingProfile(BaseModel):
    departure_time: Optional[datetime]              # Expected departure (first waypoint time)
    arrival_time: Optional[datetime]                # Expected arrival (last waypoint time)
    total_expected_duration_seconds: Optional[float]
    has_timing_data: bool                           # Whether route has timing metadata
    segment_count_with_timing: int                  # Segments with calculated expected speeds
```

**Source:** Extracted from KML waypoint descriptions
- Pattern: `Time Over Waypoint: YYYY-MM-DD HH:MM:SSZ`
- Parsed by `app/services/kml_parser.py`

### 3.2 RoutePoint (Individual Waypoint)
```python
class RoutePoint(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float]
    sequence: int
    expected_arrival_time: Optional[datetime]      # Extracted from KML
    expected_segment_speed_knots: Optional[float]  # Calculated from timing data
```

### 3.3 RouteWaypoint (Named POI on Route)
```python
class RouteWaypoint(BaseModel):
    name: Optional[str]
    description: Optional[str]
    latitude: float
    longitude: float
    order: int
    role: Optional[str]                            # 'departure', 'arrival', 'waypoint', 'alternate'
    expected_arrival_time: Optional[datetime]      # Extracted from description
```

---

## 4. ROUTE-AWARE ETA CALCULATION (Session 28)

### 4.1 Problem Statement
Dashboard showed incorrect ETAs because:
- POI ETA endpoint was using basic distance/speed calculation
- Route timing data was being ignored in Prometheus metrics
- Two separate ETA paths: RouteETACalculator (API) and ETACalculator (metrics)

### 4.2 Solution: Make ETACalculator Route-Aware

**Files Modified:**
1. `app/services/eta_calculator.py`
   - Added `_calculate_route_aware_eta()` method
   - Modified `calculate_poi_metrics()` to accept optional `active_route` parameter
   - Added `_calculate_on_route_eta()` for waypoints on route
   - Added `_calculate_off_route_eta_with_projection()` for POIs near route

2. `app/core/eta_service.py`
   - Updated `update_eta_metrics()` to accept and pass `active_route`

3. `app/core/metrics.py`
   - Updated `update_metrics_from_telemetry()` to accept `active_route`

4. `main.py`
   - Extracts active route before metrics update
   - Passes route to metrics update function

5. `app/api/pois.py`
   - Updated `/api/pois/etas` endpoint to use route-aware ETA

### 4.3 Route-Aware ETA Logic

**For on-route POIs (POI name matches waypoint name):**
1. Find nearest route point to current position
2. Walk segments from nearest point to destination waypoint
3. Use current smoothed speed for first segment
4. Use expected segment speeds for subsequent segments
5. Sum segment ETAs for total ETA

**For off-route POIs with projection data:**
1. Find route segment containing POI's projection point
2. Calculate ETA from current position to projection (current speed)
3. Calculate ETA from projection to final destination (route speeds)
4. Return sum of both ETAs

**Fallback (no route-aware data):**
- Use basic distance/speed calculation

---

## 5. POI DATA MODEL & PROJECTION

### 5.1 POI Model
**Location:** `app/models/poi.py`

```python
class POI(BaseModel):
    id: str
    name: str
    latitude: float
    longitude: float
    icon: str                              # 'marker', 'airport', 'city', etc.
    category: Optional[str]                # 'airport', 'city', 'waypoint', etc.
    description: Optional[str]
    route_id: Optional[str]                # Associated route
    
    # Route projection fields (calculated when route active)
    projected_latitude: Optional[float]    # Projection point on active route
    projected_longitude: Optional[float]
    projected_waypoint_index: Optional[int]
    projected_route_progress: Optional[float]  # 0-100% along route
```

### 5.2 POIWithETA (API Response)
```python
class POIWithETA(BaseModel):
    poi_id: str
    name: str
    latitude: float
    longitude: float
    category: Optional[str]
    icon: str
    eta_seconds: float                     # Estimated time in seconds
    distance_meters: float
    bearing_degrees: Optional[float]       # 0=North, 90=East
    course_status: Optional[str]           # on_course, slightly_off, off_track, behind
    
    # Route-aware fields
    is_on_active_route: bool
    projected_latitude: Optional[float]
    projected_longitude: Optional[float]
    projected_waypoint_index: Optional[int]
    projected_route_progress: Optional[float]
    route_aware_status: Optional[str]      # ahead_on_route, already_passed, not_on_route, pre_departure
```

---

## 6. PROMETHEUS METRICS EXPOSED

### 6.1 POI/ETA Metrics
**File:** `app/core/metrics.py` (lines 228-242)

```python
starlink_eta_poi_seconds = Gauge(
    'starlink_eta_poi_seconds',
    'Estimated time of arrival to point of interest in seconds',
    labelnames=['name', 'category'],
    registry=REGISTRY
)

starlink_distance_to_poi_meters = Gauge(
    'starlink_distance_to_poi_meters',
    'Distance to point of interest in meters',
    labelnames=['name', 'category'],
    registry=REGISTRY
)
```

### 6.2 Route Timing Metrics
**File:** `app/core/metrics.py` (lines 264-297)

```python
starlink_route_has_timing_data           # 1=timing data, 0=no timing
starlink_route_total_duration_seconds     # Expected flight duration
starlink_route_departure_time_unix        # Unix timestamp of departure
starlink_route_arrival_time_unix          # Unix timestamp of arrival
starlink_route_segment_count_with_timing  # Number of timed segments
starlink_eta_to_waypoint_seconds          # ETA to specific waypoint
```

### 6.3 Update Mechanism
**Location:** `app/api/metrics_export.py` (lines 45-120)

- `/metrics` endpoint is scraped by Prometheus
- Updates route timing metrics if active route with timing profile exists
- Updates POI ETA metrics for all POIs with active telemetry

---

## 7. GRAFANA DASHBOARD INTEGRATION

### 7.1 POI Management Dashboard
**File:** `monitoring/grafana/provisioning/dashboards/poi-management.json`

**Key Panels:**
1. **Next Destination** - Calls `/api/pois/stats/next-destination`
2. **Time to Next Arrival** - Calls `/api/pois/stats/next-eta` and displays in seconds
3. **Points of Interest - ETA Table** - Shows all POIs with ETA values
4. **Projected Route Data** - Shows route projections if active route exists

### 7.2 Data Source
- Uses Infinity datasource plugin
- Directly calls REST API endpoints
- Caches responses for 1 second
- Parses JSON responses

### 7.3 Field Configuration
- ETA displayed in seconds
- Color thresholds:
  - Red: 0-0 seconds (passed)
  - Orange: 0-300 seconds (5 minutes)
  - Yellow: 300-900 seconds (15 minutes)
  - Blue: >900 seconds (beyond 15 minutes)

---

## 8. SPEED SMOOTHING IMPLEMENTATION

### 8.1 Rolling Window Average
**Duration:** 120 seconds (configurable)
**Method:** Time-based rolling average

**Implementation** (`eta_calculator.py` lines 41-75):
1. Store tuples of (speed_knots, timestamp)
2. Add new speed sample on each update
3. Remove samples older than 120 seconds
4. Calculate average of remaining samples

**Use Cases:**
- Stabilizes ETA calculations against speed variations
- Prevents extreme ETA swings from brief speed changes
- Uses actual current speed for first segment in route-aware calc

---

## 9. CURRENT OUTSTANDING ISSUES (Session 28)

### 9.1 In-Progress Fix
**Status:** Route-aware ETA calculation partially implemented

**Completed:**
- KADW (waypoint on route) shows correct ETA with route awareness
- ETACalculator method for on-route POIs working
- All 451 tests passing

**Remaining:**
- SAT SWAP (POI not on route) needs:
  1. Use POI's `projected_latitude`/`projected_longitude` if available
  2. Calculate ETA from current position to projection (current speed)
  3. Calculate ETA from projection to destination (route-aware speeds)
  4. Return sum of both ETAs

### 9.2 Testing Requirements
Need to verify:
1. On-route waypoints (KADW) - ✅ working
2. Off-route POIs with projection (SAT SWAP) - needs verification
3. Manual POIs without route data - should fall back to distance/speed

---

## 10. KEY ARCHITECTURAL DECISIONS

### 10.1 Single Source of Truth
ETACalculator is the primary ETA calculation engine for all scenarios:
- Basic distance/speed for POIs without route
- Route-aware segment speeds for POIs on active route
- Projection-based for POIs near route

### 10.2 Graceful Degradation
If route-aware calculation fails:
1. Try projected ETA calculation
2. Fall back to basic distance/speed calculation
3. Return -1.0 only for zero/no speed cases

### 10.3 Route-Aware Decision Logic
```
IF active_route exists AND route has timing data:
  IF POI name matches route waypoint:
    Use on-route calculation (segment-by-segment)
  ELSE IF POI has projection data:
    Use projection-based calculation
  ELSE:
    Use fallback distance/speed
ELSE:
  Use fallback distance/speed
```

### 10.4 Speed Strategy for Route-Aware ETAs
- **First segment:** Current smoothed speed (actual movement)
- **Subsequent segments:** Expected segment speeds from route timing data
- **Rationale:** Realistic ETA considering current conditions while using known future speeds

---

## 11. FILES NEEDING CHANGES FOR PRE-DEPARTURE / POST-DEPARTURE DISTINCTION

### 11.1 Route Timing Profile Enhancement
**File:** `app/models/route.py`

**Current State:**
- `departure_time` - First waypoint arrival time
- `arrival_time` - Last waypoint arrival time

**Needed for Pre/Post Distinction:**
- Add `flight_departure_time` - Actual flight departure (before first waypoint)
- Add `flight_status` - enum: 'pre_departure', 'in_flight', 'post_arrival'
- Add `current_flight_phase_index` - Which phase the flight is in

### 11.2 POI Model Enhancement
**File:** `app/models/poi.py`

**Needed:**
- Add `poi_type` - enum: 'departure', 'arrival', 'waypoint', 'alternate'
- Add `is_future_poi` - Boolean based on route progress
- Add `time_until_departure` - If pre-departure scenario

### 11.3 ETA Response Enhancement
**File:** `app/models/poi.py` (POIWithETA)

**Needed:**
- Add `eta_type` - enum: 'estimated' (post-departure), 'anticipated' (pre-departure)
- Add `is_pre_departure` - Boolean flag
- Add `flight_phase` - Current phase of flight

### 11.4 Dashboard Display Logic
**File:** `monitoring/grafana/provisioning/dashboards/poi-management.json`

**Needed:**
- Conditional formatting based on `eta_type`
- Different colors/styling for anticipated vs estimated
- Display "Anticipated" label for pre-departure
- Display "Estimated" label for post-departure

---

## 12. SUMMARY TABLE

| Component | Location | Responsibility |
|-----------|----------|-----------------|
| ETACalculator | `services/eta_calculator.py` | Core ETA calculations with speed smoothing |
| RouteETACalculator | `services/route_eta_calculator.py` | Route-specific timing calculations |
| ETA Service | `core/eta_service.py` | Singleton manager for ETA calculations |
| POI Manager | `services/poi_manager.py` | Manages POI persistence and retrieval |
| Route Manager | `services/route_manager.py` | Manages route lifecycle |
| KML Parser | `services/kml_parser.py` | Extracts timing data from KML files |
| Metrics Export | `api/metrics_export.py` | Prometheus metrics endpoint |
| POI API | `api/pois.py` | REST endpoints for POI operations with ETA |
| Coordinator | `live/coordinator.py` + `simulation/coordinator.py` | Telemetry loop, passes data to metrics |

---

## 13. CONCLUSION

The ETA system is a mature, multi-layer implementation with:
- ✅ Route-aware ETA calculations
- ✅ Speed smoothing and noise reduction
- ✅ Prometheus metrics integration
- ✅ Grafana dashboard visualization
- ✅ API endpoints with comprehensive POI data
- ✅ Support for routes with and without timing data
- 🔧 **Needs:** Pre-departure vs post-departure time distinction

To implement pre-departure/post-departure distinction, the system needs:
1. Flight status tracking in route timing profile
2. Enhanced POI model with timing type classification
3. Dashboard logic to display different labels/colors
4. API response updates to indicate ETA type
