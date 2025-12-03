# Status Enums and Helper Functions

This document describes the enumeration types, constants, and utility functions
used throughout the mission system.

---

## Enums

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

## Exporter Constants and Mappings

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

---

## Helper Functions

**Location:** `backend/starlink-location/app/mission/exporter.py`

### _format_seconds_hms(value: float | int) -> str

Formats seconds as HH:MM:SS (handles negative values)

```python
# Example: 3661 -> "01:01:01"
# Example: -3661 -> "-01:01:01"
```

### _serialize_transport_list(transports: Iterable[Transport]) -> str

Converts Transport enums to display names, joined by ", "

```python
# Example: [Transport.X, Transport.KA] -> "X-Band, CommKa"
```

### _compose_time_block(moment: datetime, mission_start: datetime) -> str

Returns multiline string: "UTC time\nEastern time\nT+/-HH:MM"

```python
# Example output:
# "2025-10-27 18:25Z
#  2025-10-27 14:25EDT
#  T+01:40"
```

### _format_utc(dt: datetime) -> str

Returns "YYYY-MM-DD HH:MZ" (no seconds, Z suffix indicates UTC)

### _format_eastern(dt: datetime) -> str

Returns "YYYY-MM-DD HH:MMTZE" (with DST-aware timezone abbreviation)

### _format_offset(delta: timedelta) -> str

Formats as "T+/-HH:MM"

```python
# Example: timedelta(minutes=100) -> "T+01:40"
# Example: timedelta(minutes=-30) -> "T-00:30"
```

### _ensure_timezone(value: datetime) -> datetime

Ensures datetime is UTC-aware; converts to UTC if needed

### _mission_start_timestamp(timeline: MissionTimeline) -> datetime

Returns mission's zero point (earliest segment start or timeline.created_at)

### _segment_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame

#### Lines 271-331 - Converts segments to exportable rows

Returns DataFrame with columns:

- "Segment #", "Mission ID", "Mission Name", "Status"
- "Start Time", "End Time", "Duration"
- "X-Band", "CommKa", "StarShield" (transport states)
- "Impacted Transports", "Reasons", "Metadata"

Special handling for export:

- X-Ku warning conflicts shown as WARNING but not degraded
- Duration formatted as HH:MM:SS
- Time blocks show UTC, Eastern, and T+/- offset
- Metadata serialized as JSON
- AAR rows inserted in order

### _segment_at_time

```python
_segment_at_time(timeline: MissionTimeline, timestamp: datetime)
    -> TimelineSegment | None
```

Returns segment containing the given timestamp, or last segment if not found

### _advisory_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame

Converts advisories to DataFrame with columns:

- "Mission ID", "Timestamp (UTC)", "Timestamp (Eastern)", "T Offset"
- "Transport", "Severity", "Event Type", "Message", "Metadata"

### _statistics_rows(timeline: MissionTimeline) -> pd.DataFrame

Converts timeline.statistics to DataFrame, humanizing metric names. Skips keys
starting with "_" (internal only)

---

## Key Data Flow for Map and Chart Generation

### To Build a Map Visualization

1. Get Mission from database
2. Use mission.route_id to fetch ParsedRoute via route manager
3. Extract ParsedRoute.points for route geometry
4. Get associated POIs (route_id filtering)
5. Get MissionTimeline segments
6. Project timeline segments onto route via time-distance analysis

### To Build a Timeline Chart

1. Get MissionTimeline with segments and advisories
2. Use `_mission_start_timestamp()` to establish timeline zero
3. Process segments:
   - Extract start_time, end_time, status, transport states
   - Use `_format_seconds_hms()` for durations
   - Check impacted_transports for visual highlighting
4. Use `_compose_time_block()` for multi-format timestamps
5. Include advisories as overlays on timeline

### To Combine Data

1. Create data structure mapping:
   - Route points (lat/lon/time) → Map geometry
   - Timeline segments (start/end/status) → Timeline bars
   - POIs (lat/lon) → Map markers with ETA data
   - Advisories (timestamp/transport) → Timeline annotations

---

## Integration Examples

### Example: Generate Timeline Export

```python
from app.mission.exporter import (
    _segment_rows,
    _advisory_rows,
    _statistics_rows,
    _mission_start_timestamp
)

# Get timeline data
timeline = get_mission_timeline(mission_id)
mission = get_mission(mission_id)

# Convert to DataFrames
segments_df = _segment_rows(timeline, mission)
advisories_df = _advisory_rows(timeline, mission)
stats_df = _statistics_rows(timeline)

# Export to Excel/CSV
segments_df.to_excel("timeline_segments.xlsx")
advisories_df.to_excel("timeline_advisories.xlsx")
stats_df.to_excel("timeline_statistics.xlsx")
```

### Example: Build Map Visualization Data

```python
# Get route and timeline
route = route_manager.get_route(mission.route_id)
timeline = get_mission_timeline(mission.id)
pois = get_pois_for_route(mission.route_id)

# Extract route geometry
route_coords = [
    {"lat": point.latitude, "lon": point.longitude}
    for point in route.points
]

# Extract POI markers
poi_markers = [
    {
        "name": poi.name,
        "lat": poi.latitude,
        "lon": poi.longitude,
        "icon": poi.icon,
        "category": poi.category
    }
    for poi in pois
]

# Map timeline status to route segments
status_segments = []
for segment in timeline.segments:
    status_segments.append({
        "start_time": segment.start_time,
        "end_time": segment.end_time,
        "status": segment.status.value,
        "x_state": segment.x_state.value,
        "ka_state": segment.ka_state.value,
        "ku_state": segment.ku_state.value
    })

# Combine for visualization
map_data = {
    "route": route_coords,
    "pois": poi_markers,
    "status_timeline": status_segments
}
```

### Example: Format Timeline Display

```python
from app.mission.exporter import (
    _compose_time_block,
    _format_seconds_hms,
    _mission_start_timestamp
)

timeline = get_mission_timeline(mission_id)
mission_start = _mission_start_timestamp(timeline)

# Format each segment for display
for segment in timeline.segments:
    # Multi-format time display
    start_block = _compose_time_block(segment.start_time, mission_start)
    end_block = _compose_time_block(segment.end_time, mission_start)

    # Duration in HH:MM:SS
    duration_seconds = (segment.end_time - segment.start_time).total_seconds()
    duration_display = _format_seconds_hms(duration_seconds)

    print(f"Segment: {segment.status.value}")
    print(f"Start: {start_block}")
    print(f"End: {end_block}")
    print(f"Duration: {duration_display}")
```
