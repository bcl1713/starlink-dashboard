# Mission Data Structures Reference

## For Map and Chart Generation in Mission Exporter

---

## 1. MISSION MODEL

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

## 2. MISSION TIMELINE MODEL

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

## 3. TIMELINE SEGMENT MODEL

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

## 4. ENUMS

### TimelineStatus

```python
class TimelineStatus(str, Enum):
    NOMINAL = "nominal"      # All transports available
    DEGRADED = "degraded"    # One transport unavailable
    CRITICAL = "critical"    # Two or more transports unavailable
```

### TransportState

```python
class TransportState(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    OFFLINE = "offline"
```

### Transport

```python
class Transport(str, Enum):
    X = "X"      # Fixed geostationary satellite
    KA = "Ka"    # Three geostationary satellites
    KU = "Ku"    # Always-on LEO constellation
```

### MissionPhase

```python
class MissionPhase(str, Enum):
    PRE_DEPARTURE = "pre_departure"
    IN_FLIGHT = "in_flight"
    POST_ARRIVAL = "post_arrival"
```

---

## 5. ROUTE DATA STRUCTURES

**Location:** `backend/starlink-location/app/models/route.py`

### ParsedRoute Fields

```python
class ParsedRoute(BaseModel):
    metadata: RouteMetadata              # Route metadata
    points: list[RoutePoint]             # Ordered list of route points
    waypoints: list[RouteWaypoint]       # Optional waypoint placemarks
    timing_profile: Optional[RouteTimingProfile]  # Timing data if present
```

### RoutePoint Fields (Sequence of Geographic Points)

```python
class RoutePoint(BaseModel):
    latitude: float                      # Decimal degrees (-90 to 90)
    longitude: float                     # Decimal degrees (-180 to 180)
    altitude: Optional[float]            # Meters above sea level
    sequence: int                        # Order in route (0-indexed)
    expected_arrival_time: Optional[datetime]  # Expected arrival at waypoint
    expected_segment_speed_knots: Optional[float]  # Speed for segment to this point
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
    role: Optional[str]                  # Semantic role (departure, arrival, etc.)
    expected_arrival_time: Optional[datetime]  # Parsed from description
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
    arrival_time: Optional[datetime]     # Expected arrival at route end (UTC)
    total_expected_duration_seconds: Optional[float]  # Expected flight duration
    actual_departure_time: Optional[datetime]  # Observed departure time
    actual_arrival_time: Optional[datetime]    # Observed arrival time
    flight_status: str                   # pre_departure | in_flight | post_arrival
    has_timing_data: bool                # Whether route has timing metadata
    segment_count_with_timing: int       # Number of segments with expected speeds
```

### Important ParsedRoute Methods

```python
def get_total_distance(self) -> float:   # Haversine calculation in meters
def get_bounds(self) -> dict:            # Returns {"min_lat", "max_lat", "min_lon", "max_lon"}
```

---

## 6. POI DATA STRUCTURES

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
    projected_latitude: Optional[float]  # Projection point on active route
    projected_longitude: Optional[float] # Projection point on active route
    projected_waypoint_index: Optional[int]  # Index of closest route point
    projected_route_progress: Optional[float]  # Progress % where POI projects (0-100)
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
    course_status: Optional[str]         # on_course | slightly_off | off_track | behind

    # Route awareness (populated when active route exists)
    is_on_active_route: bool             # Whether POI projects to active route
    projected_latitude: Optional[float]  # Projected point on route
    projected_longitude: Optional[float] # Projected point on route
    projected_waypoint_index: Optional[int]  # Index of closest route point
    projected_route_progress: Optional[float]  # Progress % on route (0-100)
    route_aware_status: Optional[str]    # ahead_on_route | already_passed | not_on_route | pre_departure
```

---

## 7. EXPORTER HELPER FUNCTIONS

**Location:** `backend/starlink-location/app/mission/exporter.py`

### Color Constants (Lines 37-48)

```python
LIGHT_YELLOW = colors.Color(1.0, 1.0, 0.85)  # For degraded transport highlighting
LIGHT_RED = colors.Color(1.0, 0.85, 0.85)    # For critical transport highlighting
```

### Transport Display Mapping

```python
TRANSPORT_DISPLAY = {
    Transport.X: "X-Band",
    Transport.KA: "CommKa",
    Transport.KU: "StarShield",
}

STATE_COLUMNS = [
    "X-Band",      # TRANSPORT_DISPLAY[Transport.X]
    "CommKa",      # TRANSPORT_DISPLAY[Transport.KA]
    "StarShield",  # TRANSPORT_DISPLAY[Transport.KU]
]
```

### Key Helper Functions

#### \_format_seconds_hms(value: float | int) -> str

```python
# Formats seconds as HH:MM:SS (handles negative values)
# Example: 3661 -> "01:01:01"
# Example: -3661 -> "-01:01:01"
```

#### \_serialize_transport_list(transports: Iterable[Transport]) -> str

```python
# Converts Transport enums to display names, joined by ", "
# Example: [Transport.X, Transport.KA] -> "X-Band, CommKa"
```

#### \_compose_time_block(moment: datetime, mission_start: datetime) -> str

```python
# Returns multiline string: "UTC time\nEastern time\nT+/-HH:MM"
# Example output:
# "2025-10-27 18:25Z
#  2025-10-27 14:25EDT
#  T+01:40"
```

#### \_format_utc(dt: datetime) -> str

```python
# Returns "YYYY-MM-DD HH:MZ" (no seconds, Z suffix indicates UTC)
```

#### \_format_eastern(dt: datetime) -> str

```python
# Returns "YYYY-MM-DD HH:MMTZE" (with DST-aware timezone abbreviation)
```

#### \_format_offset(delta: timedelta) -> str

```python
# Formats as "T+/-HH:MM"
# Example: timedelta(minutes=100) -> "T+01:40"
# Example: timedelta(minutes=-30) -> "T-00:30"
```

#### \_ensure_timezone(value: datetime) -> datetime

```python
# Ensures datetime is UTC-aware; converts to UTC if needed
```

#### \_mission_start_timestamp(timeline: MissionTimeline) -> datetime

```python
# Returns mission's zero point (earliest segment start or timeline.created_at)
```

#### \_segment_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame

##### Lines 271-331 - Converts segments to exportable rows

```python
# Returns DataFrame with columns:
# - "Segment #", "Mission ID", "Mission Name", "Status"
# - "Start Time", "End Time", "Duration"
# - "X-Band", "CommKa", "StarShield"  (transport states)
# - "Impacted Transports", "Reasons", "Metadata"
#
# Special handling:
# - X-Ku warning conflicts shown as WARNING but not degraded
# - Duration formatted as HH:MM:SS
# - Time blocks show UTC, Eastern, and T+/- offset
# - Metadata serialized as JSON
# - AAR rows inserted in chronological order
```

#### \_segment_at_time

```python
# (timeline: MissionTimeline, timestamp: datetime) -> TimelineSegment | None
# Returns segment containing the given timestamp, or last segment if not found
```

#### \_advisory_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame

```python
# Converts advisories to DataFrame with columns:
# - "Mission ID", "Timestamp (UTC)", "Timestamp (Eastern)", "T Offset"
# - "Transport", "Severity", "Event Type", "Message", "Metadata"
```

#### \_statistics_rows(timeline: MissionTimeline) -> pd.DataFrame

```python
# Converts timeline.statistics to DataFrame, humanizing metric names
# Skips keys starting with "_" (internal only)
```

---

## 8. TIMELINE ADVISORY MODEL

**Location:** `backend/starlink-location/app/mission/models.py`

### TimelineAdvisory Fields

```python
class TimelineAdvisory(BaseModel):
    id: str                              # Unique advisory identifier
    timestamp: datetime                  # When advisory applies (UTC)
    event_type: str                      # e.g., "transition", "azimuth_conflict", "buffer", "aar_window"
    transport: Transport                 # X, Ka, or Ku
    severity: str                        # "info", "warning", or "critical"
    message: str                         # Human-readable advisory message
    metadata: dict                       # Additional context (satellite IDs, reason codes, etc.)
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

## 9. TRANSPORT CONFIGURATION

**Location:** `backend/starlink-location/app/mission/models.py`

### TransportConfig Fields

```python
class TransportConfig(BaseModel):
    initial_x_satellite_id: str          # Initial X satellite (e.g., "X-1")
    initial_ka_satellite_ids: list[str]  # Initial Ka satellites (e.g., ["AOR", "POR", "IOR"])
    x_transitions: list[XTransition]     # Satellite transitions on X
    ka_outages: list[KaOutage]           # Manual Ka outage windows
    aar_windows: list[AARWindow]         # Air-refueling segments
    ku_overrides: list[KuOutageOverride] # Manual Ku outage overrides
```

### XTransition Fields

```python
class XTransition(BaseModel):
    id: str                              # Unique transition identifier
    latitude: float                      # Actual transition latitude
    longitude: float                     # Actual transition longitude
    target_satellite_id: str             # Target satellite ID (e.g., "X-1")
    target_beam_id: Optional[str]        # Optional target beam ID
    is_same_satellite_transition: bool   # True if different beam, same satellite
```

---

## 10. KEY DATA FLOW FOR MAP/CHART GENERATION

### To Build a Map Visualization

1. Get Mission from database
2. Use mission.route_id to fetch ParsedRoute via route manager
3. Extract ParsedRoute.points for route geometry
4. Get associated POIs (route_id filtering)
5. Get MissionTimeline segments
6. Project timeline segments onto route via time-distance analysis

### To Build a Timeline Chart

1. Get MissionTimeline with segments and advisories
2. Use \_mission_start_timestamp() to establish timeline zero
3. Process segments:
   - Extract start_time, end_time, status, transport states
   - Use \_format_seconds_hms() for durations
   - Check impacted_transports for visual highlighting
4. Use \_compose_time_block() for multi-format timestamps
5. Include advisories as overlays on timeline

### To Combine Data

1. Create data structure mapping:
   - Route points (lat/lon/time) → Map geometry
   - Timeline segments (start/end/status) → Timeline bars
   - POIs (lat/lon) → Map markers with ETA data
   - Advisories (timestamp/transport) → Timeline annotations

---

## 11. IMPORTANT NOTES FOR IMPLEMENTATION

### Timezone Handling

- All stored times are UTC (ISO-8601 format)
- Use EASTERN_TZ = ZoneInfo("America/New_York") for Eastern display
- Always use \_ensure_timezone() to make datetimes UTC-aware

### Duration Formatting

- Use \_format_seconds_hms() for all duration displays
- Handles negative values with "-" prefix
- Format: "HH:MM:SS"

### Transport State Visualization

- X-Ku conflict warnings display as "WARNING" even though state is "DEGRADED"
- Use \_segment_is_x_ku_warning() to detect this special case
- Color degraded/offline states using LIGHT_YELLOW (1 transport) or LIGHT_RED
  (2+ transports)

### Route Integration

- ParsedRoute.get_total_distance() returns meters via Haversine formula
- ParsedRoute.get_bounds() returns geographic bounding box
- RoutePoints have expected_arrival_time for timeline alignment
- Use projected_waypoint_index and projected_route_progress to position segments
  on route

### POI Integration

- POI.projected\_\* fields only populated when route is active
- POIWithETA includes route_aware_status for visualization logic
- eta_type switches between "anticipated" (pre-departure) and "estimated"
  (in-flight)
