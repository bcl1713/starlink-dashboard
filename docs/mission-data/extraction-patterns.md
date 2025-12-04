# Mission Data Extraction Patterns

Common patterns for extracting and processing mission data for visualization
and export.

## Quick Extraction Patterns

### Extract segment for chart

```python
mission_start = _mission_start_timestamp(timeline)
for segment in timeline.segments:
    start = _ensure_timezone(segment.start_time)
    end = _ensure_timezone(segment.end_time)
    duration = _format_seconds_hms((end - start).total_seconds())
    status = segment.status.value.upper()
    time_block = _compose_time_block(start, mission_start)
```

### Extract POI markers

```python
for poi in pois:
    marker = {
        "id": poi.poi_id,
        "name": poi.name,
        "lat": poi.latitude,
        "lon": poi.longitude,
        "eta": _format_seconds_hms(poi.eta_seconds) if poi.eta_seconds > 0 else "-",
        "status": poi.route_aware_status,
    }
```

### Get route geometry

```python
route_bounds = route.get_bounds()
route_distance_m = route.get_total_distance()
route_line = [(p.latitude, p.longitude) for p in route.points]
```

### Extract timeline statistics

```python
stats = {
    "total": timeline.statistics.get("total_duration_seconds", 0),
    "nominal": timeline.statistics.get("nominal_seconds", 0),
    "degraded": timeline.statistics.get("degraded_seconds", 0),
    "critical": timeline.statistics.get("critical_seconds", 0),
}
```

---

## Visualization Data Flows

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

## Complete Integration Examples

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

---

## Next Steps for Implementation

### For map visualization

1. Extract route geometry: `route.points` for line, `route.waypoints` for
   markers
2. Add POI markers from `pois_with_eta` list
3. Project timeline segments onto route using time/distance alignment
4. Color segments by `segment.status`

### For chart visualization

1. Create timeline axis from `mission_start` to final segment end
2. For each segment, draw bar: `start_time` to `end_time`, colored by status
3. Add advisory markers at their timestamps
4. Stack transport states (X-Band, CommKa, StarShield) for degraded/critical
5. Display statistics summary above chart
