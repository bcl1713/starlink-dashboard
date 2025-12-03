# Mission and Timeline Models

This document describes the core data structures for mission planning, timeline
generation, and route management.

---

## Mission Model

**Location:** `backend/starlink-location/app/mission/models.py`

### Mission Fields

```python
class Mission(BaseModel):
    id: str                              # Unique mission identifier
    name: str                            # Human-readable name
    description: Optional[str]           # Detailed description
    route_id: str                        # Associated flight route ID
    transports: TransportConfig          # Transport/satellite configuration
    created_at: datetime                 # Creation timestamp (UTC)
    updated_at: datetime                 # Last update timestamp (UTC)
    is_active: bool                      # Currently active flag
    notes: Optional[str]                 # Planner notes
```

### Key Relationships

- **route_id** → Links to a ParsedRoute (via route manager)
- **transports** → Contains transport configuration with satellite transitions

---

## MissionTimeline Model

**Location:** `backend/starlink-location/app/mission/models.py`

### MissionTimeline Fields

```python
class MissionTimeline(BaseModel):
    mission_id: str                      # Associated mission ID
    created_at: datetime                 # When timeline was computed (UTC)
    segments: list[TimelineSegment]      # Ordered timeline segments
    advisories: list[TimelineAdvisory]   # Operator advisories
    statistics: dict                     # Summary statistics
```

### Statistics Dict Keys

```python
{
    "total_duration_seconds": float,     # Total mission duration
    "nominal_seconds": float,            # Time with all transports available
    "degraded_seconds": float,           # One transport unavailable
    "critical_seconds": float,           # Two+ transports unavailable
    "_aar_blocks": list[dict]            # AAR windows (internal, starts with _)
}
```

---

## TimelineSegment Model

**Location:** `backend/starlink-location/app/mission/models.py`

### TimelineSegment Fields

```python
class TimelineSegment(BaseModel):
    id: str                              # Unique segment identifier
    start_time: datetime                 # Segment start (UTC, ISO-8601)
    end_time: datetime                   # Segment end (UTC, ISO-8601)
    status: TimelineStatus               # Overall communication status
    x_state: TransportState              # X-Band transport state
    ka_state: TransportState             # Ka (CommKa) transport state
    ku_state: TransportState             # Ku (StarShield) transport state
    reasons: list[str]                   # Reason codes explaining status
    impacted_transports: list[Transport] # Transports that are degraded/offline
    metadata: dict                       # Additional context
```

### Metadata Dict Structure

```python
{
    "satellites": {
        "X": "X-1" or "X-2",            # Current X-Band satellite
        "Ka": ["AOR", "POR", "IOR"]     # Current Ka satellites
    },
    # Additional context keys may vary
}
```

---

## TimelineAdvisory Model

**Location:** `backend/starlink-location/app/mission/models.py`

### TimelineAdvisory Fields

```python
class TimelineAdvisory(BaseModel):
    id: str                              # Unique advisory identifier
    timestamp: datetime                  # When advisory applies (UTC)
    event_type: str
    # e.g., "transition", "azimuth_conflict", "buffer", "aar_window"
    transport: Transport                 # X, Ka, or Ku
    severity: str                        # "info", "warning", or "critical"
    message: str                         # Human-readable advisory message
    metadata: dict
    # Additional context (satellite IDs, reason codes, etc.)
```

### Advisory Metadata Example

```python
{
    "reason": "transition",
    "satellite_from": "X-1",
    "satellite_to": "X-2",
    "buffer_minutes": 15,
}
```

---

## TransportConfig Model

**Location:** `backend/starlink-location/app/mission/models.py`

### TransportConfig Fields

```python
class TransportConfig(BaseModel):
    initial_x_satellite_id: str          # Initial X satellite (e.g., "X-1")
    initial_ka_satellite_ids: list[str]
    # Initial Ka satellites (e.g., ["AOR", "POR", "IOR"])
    x_transitions: list[XTransition]     # Satellite transitions on X
    ka_outages: list[KaOutage]           # Manual Ka outage windows
    aar_windows: list[AARWindow]         # Air-refueling segments
    ku_overrides: list[KuOutageOverride]
    # Manual Ku outage overrides
```

### XTransition Fields

```python
class XTransition(BaseModel):
    id: str                              # Unique transition identifier
    latitude: float                      # Actual transition latitude
    longitude: float                     # Actual transition longitude
    target_satellite_id: str
    # Target satellite ID (e.g., "X-1", "X-2")
    target_beam_id: Optional[str]        # Optional target beam ID
    is_same_satellite_transition: bool
    # True if different beam, same satellite
```

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
