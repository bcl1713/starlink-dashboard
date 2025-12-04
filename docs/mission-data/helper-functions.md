# Mission Data Helper Functions

Reference guide for helper functions in the mission system exporter.

## Time Formatting Functions

**Location:** `backend/starlink-location/app/mission/exporter.py`

### \_ensure_timezone(value: datetime) -> datetime

Ensures datetime is UTC-aware; converts to UTC if needed

### \_mission_start_timestamp(timeline: MissionTimeline) -> datetime

Returns mission's zero point (earliest segment start or timeline.created_at)

### \_format_utc(dt: datetime) -> str

Returns "YYYY-MM-DD HH:MZ" (no seconds, Z suffix indicates UTC)

### \_format_eastern(dt: datetime) -> str

Returns "YYYY-MM-DD HH:MMTZE" (with DST-aware timezone abbreviation)

### \_format_offset(delta: timedelta) -> str

Formats as "T+/-HH:MM"

```python
# Example: timedelta(minutes=100) -> "T+01:40"
# Example: timedelta(minutes=-30) -> "T-00:30"
```

### \_compose_time_block(moment: datetime, mission_start: datetime) -> str

Returns multiline string: "UTC time\nEastern time\nT+/-HH:MM"

```python
# Example output:
# "2025-10-27 18:25Z
#  2025-10-27 14:25EDT
#  T+01:40"
```

---

## Data Processing Functions

### \_format_seconds_hms(value: float | int) -> str

Formats seconds as HH:MM:SS (handles negative values)

```python
# Example: 3661 -> "01:01:01"
# Example: -3661 -> "-01:01:01"
```

### \_serialize_transport_list(transports: Iterable[Transport]) -> str

Converts Transport enums to display names, joined by ", "

```python
# Example: [Transport.X, Transport.KA] -> "X-Band, CommKa"
```

### \_segment_at_time

```python
_segment_at_time(timeline: MissionTimeline, timestamp: datetime)
    -> TimelineSegment | None
```

Returns segment containing the given timestamp, or last segment if not found

### \_segment_is_x_ku_warning

```python
_segment_is_x_ku_warning(segment: TimelineSegment) -> bool
```

Checks if segment represents X-Ku warning case (special warning case)

---

## Export Functions

### \_segment_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame

**Lines 271-331** - Converts segments to exportable rows

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

### \_advisory_rows(timeline: MissionTimeline, mission: Mission | None) -> pd.DataFrame

Converts advisories to DataFrame with columns:

- "Mission ID", "Timestamp (UTC)", "Timestamp (Eastern)", "T Offset"
- "Transport", "Severity", "Event Type", "Message", "Metadata"

### \_statistics_rows(timeline: MissionTimeline) -> pd.DataFrame

Converts timeline.statistics to DataFrame, humanizing metric names. Skips keys
starting with "\_" (internal only)

---

## Constants

### Transport Display Mapping

```python
TRANSPORT_DISPLAY = {
    Transport.X: "X-Band",
    Transport.KA: "CommKa",
    Transport.KU: "StarShield",
}

STATE_COLUMNS = ["X-Band", "CommKa", "StarShield"]
```

### Color Constants

```python
LIGHT_YELLOW = colors.Color(1.0, 1.0, 0.85)    # Degraded
LIGHT_RED = colors.Color(1.0, 0.85, 0.85)      # Critical
```

---

## Usage Examples

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
