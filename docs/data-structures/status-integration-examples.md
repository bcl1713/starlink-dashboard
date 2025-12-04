# Status Integration Examples

Practical examples for integrating mission status data into visualizations and
exports.

---

## Example: Build Map Visualization Data

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

---

## Example: Format Timeline Display

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
    duration = (segment.end_time - segment.start_time).total_seconds()
    duration_display = _format_seconds_hms(duration)

    print(f"Segment: {segment.status.value}")
    print(f"Start: {start_block}")
    print(f"End: {end_block}")
    print(f"Duration: {duration_display}")
```

---

## Example: Generate Timeline Export

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
