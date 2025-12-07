# Mission Data Structures - Quick Reference Card

Quick reference for core mission data structures and their relationships.

## Core Classes at a Glance

### Mission

```python
id: str
name: str
route_id: str                    # Use to fetch ParsedRoute
transports: TransportConfig      # Contains satellite transitions
is_active: bool
created_at, updated_at: datetime
```

### MissionTimeline

```python
mission_id: str
segments: list[TimelineSegment]  # Primary visualization data
advisories: list[TimelineAdvisory]
statistics: dict                 # Totals: nominal/degraded/critical seconds
created_at: datetime
```

### TimelineSegment

```python
id, start_time, end_time: datetime
status: TimelineStatus           # NOMINAL | DEGRADED | CRITICAL
x_state, ka_state, ku_state: TransportState  # AVAILABLE | DEGRADED | OFFLINE
impacted_transports: list[Transport]
reasons: list[str]               # Reason codes
metadata: dict                   # Contains satellites: {X: "X-1", Ka: ["AOR", "POR", "IOR"]}
```

### ParsedRoute

```python
metadata: RouteMetadata
points: list[RoutePoint]         # Ordered [lat, lon, alt, sequence, expected_arrival_time, speed]
waypoints: list[RouteWaypoint]   # Named points [name, lat, lon, role, expected_arrival_time]
timing_profile: RouteTimingProfile  # [departure_time, arrival_time, has_timing_data, flight_status]
```

### POI / POIWithETA

```python
# POI
id, name: str
latitude, longitude: float
icon, category: str
route_id, mission_id: str (optional)
projected_*: Optional[float]     # Only when route is active

# POIWithETA (adds)
eta_seconds: float
eta_type: str                    # "anticipated" | "estimated"
distance_meters: float
bearing_degrees: Optional[float]
course_status: str               # "on_course" | "slightly_off" | "off_track" | "behind"
route_aware_status: str          # "ahead_on_route" | "already_passed" | "not_on_route"
```

---

## Enum Values

### TimelineStatus

| Value        | Meaning          | Color  |
| ------------ | ---------------- | ------ |
| `"nominal"`  | All available    | Green  |
| `"degraded"` | One unavailable  | Yellow |
| `"critical"` | Two+ unavailable | Red    |

### TransportState

| Value         | Meaning               |
| ------------- | --------------------- |
| `"available"` | Transport is up       |
| `"degraded"`  | Transport is impaired |
| `"offline"`   | Transport is down     |

### Transport (Display Mapping)

| Enum           | Value  | Display Name   |
| -------------- | ------ | -------------- |
| `Transport.X`  | `"X"`  | `"X-Band"`     |
| `Transport.KA` | `"Ka"` | `"CommKa"`     |
| `Transport.KU` | `"Ku"` | `"StarShield"` |

### Flight Status

| Value             | Meaning          |
| ----------------- | ---------------- |
| `"pre_departure"` | Before departure |
| `"in_flight"`     | Currently flying |
| `"post_arrival"`  | After landing    |

---

## Data Flow Diagram

```text
User Request
    |
    ├─> Fetch Mission
    |       └─> mission.route_id
    |           └─> Fetch ParsedRoute
    |               ├─> route.points (line geometry)
    |               ├─> route.waypoints (named points)
    |               └─> route.timing_profile (flight times)
    |
    ├─> Fetch MissionTimeline
    |       ├─> timeline.segments (bar chart)
    |       ├─> timeline.advisories (annotations)
    |       └─> timeline.statistics (summary)
    |
    ├─> Fetch POIs (filtered by route_id)
    |       └─> POIWithETA (map markers + ETA)
    |
    └─> Render
        ├─> Map (route line + POI markers + segment positions)
        ├─> Timeline Chart (status bars + advisories)
        └─> Statistics Panel (percentages and totals)
```

---

## Critical Implementation Notes

### Timezone Handling

- All datetimes are UTC (ISO-8601)
- Always use `_ensure_timezone()` before operations
- Eastern display: use EASTERN_TZ from exporter
- Format: `_compose_time_block()` returns all three formats at once

### Color Coding

```text
NOMINAL  → Green (#00AA00)
DEGRADED → Yellow (#FFCC00, use LIGHT_YELLOW)
CRITICAL → Red (#FF0000, use LIGHT_RED)
```

### Special Cases

- **X-Ku Warnings**: Check `_segment_is_x_ku_warning(segment)` - shows as
  "WARNING"
- **Missing Timing**: If `has_timing_data=False`, use distance-based alignment
  instead of time
- **AAR Windows**: In `timeline.statistics["_aar_blocks"]` (underscore =
  internal only)
- **Missing Arrival**: If `expected_arrival_time=None`, skip time-based
  positioning

### Data Validation

- RoutePoints: `expected_arrival_time` may be None
- TimelineSegment: `impacted_transports` may be empty
- ParsedRoute: `timing_profile` may be None
- POI: `projected_*` fields only populated when route is active

---

## Import Statements Needed

```python
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.mission.models import (
    Mission,
    MissionTimeline,
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportState,
)
from app.mission.exporter import (
    _ensure_timezone,
    _mission_start_timestamp,
    _format_utc,
    _format_eastern,
    _format_offset,
    _compose_time_block,
    _format_seconds_hms,
    _serialize_transport_list,
    _segment_rows,
    _segment_at_time,
    _segment_is_x_ku_warning,
    TRANSPORT_DISPLAY,
    LIGHT_YELLOW,
    LIGHT_RED,
    STATE_COLUMNS,
    EASTERN_TZ,
)
from app.models.route import ParsedRoute, RoutePoint, RouteWaypoint
from app.models.poi import POI, POIWithETA
```

---

| `"pre_departure"` | Before departure
