# Route and POI Data Structures

This document describes data structures for route management and Points of
Interest (POI) handling.

---

## Route Data Structures

**Location:** `backend/starlink-location/app/models/route.py`

### ParsedRoute Fields

```python
class ParsedRoute(BaseModel):
    metadata: RouteMetadata              # Route metadata
    points: list[RoutePoint]             # Ordered list of route points
    waypoints: list[RouteWaypoint]       # Optional waypoint placemarks
    timing_profile: Optional[RouteTimingProfile]
    # Timing data if present
```

### RoutePoint Fields (Sequence of Geographic Points)

```python
class RoutePoint(BaseModel):
    latitude: float                      # Decimal degrees (-90 to 90)
    longitude: float                     # Decimal degrees (-180 to 180)
    altitude: Optional[float]            # Meters above sea level
    sequence: int                        # Order in route (0-indexed)
    expected_arrival_time: Optional[datetime]
    # Expected arrival at waypoint
    expected_segment_speed_knots: Optional[float]
    # Speed for segment to this point
```

### RouteWaypoint Fields (Named Points)

```python
class RouteWaypoint(BaseModel):
    name: Optional[str]                  # Waypoint name from KML
    description: Optional[str]           # Waypoint description text
    style_url: Optional[str]             # Referenced style URL
    latitude: float                      # Waypoint latitude
    longitude: float                     # Waypoint longitude
    altitude: Optional[float]            # Waypoint altitude
    order: int                           # Document order index
    role: Optional[str]
    # Semantic role (departure, arrival, etc.)
    expected_arrival_time: Optional[datetime]
    # Parsed from description
```

### RouteMetadata Fields

```python
class RouteMetadata(BaseModel):
    name: str                            # Route name from KML
    description: Optional[str]           # Route description from KML
    file_path: str                       # Path to source KML file
    imported_at: datetime                # When route was imported
    point_count: int                     # Total number of points
```

### RouteTimingProfile Fields

```python
class RouteTimingProfile(BaseModel):
    departure_time: Optional[datetime]   # Expected departure (UTC)
    arrival_time: Optional[datetime]
    # Expected arrival at route end (UTC)
    total_expected_duration_seconds: Optional[float]
    # Expected flight duration
    actual_departure_time: Optional[datetime]
    # Observed departure time
    actual_arrival_time: Optional[datetime]
    # Observed arrival time
    flight_status: str
    # pre_departure | in_flight | post_arrival
    has_timing_data: bool
    # Whether route has timing metadata
    segment_count_with_timing: int
    # Number of segments with expected speeds
```

### Important ParsedRoute Methods

```python
def get_total_distance(self) -> float:
    # Haversine calculation in meters
def get_bounds(self) -> dict:
    # Returns {"min_lat", "max_lat", "min_lon", "max_lon"}
```

---

## POI Data Structures

**Location:** `backend/starlink-location/app/models/poi.py`

### POI Fields (Core Data)

```python
class POI(BaseModel):
    id: str                              # Unique POI identifier
    name: str                            # POI name
    latitude: float                      # Decimal degrees (-90 to 90)
    longitude: float                     # Decimal degrees (-180 to 180)
    icon: str                            # Icon identifier (default: "marker")
    category: Optional[str]              # POI category (airport, city, etc.)
    description: Optional[str]           # Detailed description
    route_id: Optional[str]              # Associated route ID if route-specific
    mission_id: Optional[str]            # Associated mission ID if mission-scoped
    created_at: datetime                 # Creation timestamp
    updated_at: datetime                 # Last update timestamp
    # Route projection fields (calculated when route is active)
    projected_latitude: Optional[float]
    # Projection point on active route
    projected_longitude: Optional[float]
    # Projection point on active route
    projected_waypoint_index: Optional[int]
    # Index of closest route point
    projected_route_progress: Optional[float]
    # Progress % where POI projects (0-100)
```

### POIWithETA Fields (For Real-Time ETA)

```python
class POIWithETA(BaseModel):
    # Core POI data
    poi_id: str
    name: str
    latitude: float
    longitude: float
    category: Optional[str]
    icon: str
    active: bool                         # Based on route/mission active status

    # ETA information
    eta_seconds: float                   # Time to arrival in seconds (-1 if no speed)
    eta_type: str                        # "anticipated" or "estimated"
    is_pre_departure: bool               # True if flight hasn't departed yet
    flight_phase: Optional[str]          # pre_departure | in_flight | post_arrival

    # Navigation information
    distance_meters: float               # Distance to POI
    bearing_degrees: Optional[float]     # Bearing to POI (0=North)
    course_status: Optional[str]
    # on_course | slightly_off | off_track | behind

    # Route awareness (populated when active route exists)
    is_on_active_route: bool
    # Whether POI projects to active route
    projected_latitude: Optional[float]  # Projected point on route
    projected_longitude: Optional[float] # Projected point on route
    projected_waypoint_index: Optional[int]
    # Index of closest route point
    projected_route_progress: Optional[float]
    # Progress % on route (0-100)
    route_aware_status: Optional[str]
    # ahead_on_route | already_passed | not_on_route | pre_departure
```
