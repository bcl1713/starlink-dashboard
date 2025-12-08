# Data Extraction & Format Patterns

## Statistics Summary Pattern

```python
def extract_timeline_statistics(
    timeline: MissionTimeline
) -> dict:
    """Extract summary statistics for dashboard display."""

    stats_df = _statistics_rows(timeline)  # Uses existing exporter function

    # Custom interpretation
    stats = {
        "total_duration_seconds": timeline.statistics.get("total_duration_seconds", 0),
        "total_duration_display": _format_seconds_hms(
            timeline.statistics.get("total_duration_seconds", 0)
        ),

        "nominal_seconds": timeline.statistics.get("nominal_seconds", 0),
        "nominal_percent": (
            timeline.statistics.get("nominal_seconds", 0) /
            max(timeline.statistics.get("total_duration_seconds", 1), 1) * 100
        ),

        "degraded_seconds": timeline.statistics.get("degraded_seconds", 0),
        "degraded_percent": (
            timeline.statistics.get("degraded_seconds", 0) /
            max(timeline.statistics.get("total_duration_seconds", 1), 1) * 100
        ),

        "critical_seconds": timeline.statistics.get("critical_seconds", 0),
        "critical_percent": (
            timeline.statistics.get("critical_seconds", 0) /
            max(timeline.statistics.get("total_duration_seconds", 1), 1) * 100
        ),
    }

    return stats
```

---

## Route Geometry Pattern

```python
def extract_route_for_map(route: ParsedRoute) -> dict:
    """Extract route geometry and metadata for map rendering."""

    # Get route bounds
    bounds = route.get_bounds()

    # Get total distance
    total_distance_m = route.get_total_distance()
    total_distance_km = total_distance_m / 1000.0

    # Extract all points for linestring
    route_line = [
        {
            "latitude": point.latitude,
            "longitude": point.longitude,
            "altitude": point.altitude,
            "sequence": point.sequence,
            "expected_arrival_time": point.expected_arrival_time.isoformat() if point.expected_arrival_time else None,
            "expected_speed_knots": point.expected_segment_speed_knots,
        }
        for point in route.points
    ]

    # Extract waypoints for markers
    waypoint_markers = [
        {
            "name": wp.name,
            "latitude": wp.latitude,
            "longitude": wp.longitude,
            "role": wp.role,
            "expected_arrival_time": wp.expected_arrival_time.isoformat() if wp.expected_arrival_time else None,
        }
        for wp in route.waypoints
    ]

    return {
        "name": route.metadata.name,
        "description": route.metadata.description,
        "point_count": route.metadata.point_count,
        "total_distance_meters": total_distance_m,
        "total_distance_km": total_distance_km,
        "bounds": bounds,
        "line": route_line,
        "waypoints": waypoint_markers,
        "timing": {
            "departure_time": route.timing_profile.departure_time.isoformat() if route.timing_profile and route.timing_profile.departure_time else None,
            "arrival_time": route.timing_profile.arrival_time.isoformat() if route.timing_profile and route.timing_profile.arrival_time else None,
            "has_timing_data": route.timing_profile.has_timing_data if route.timing_profile else False,
        } if route.timing_profile else None,
    }
```

---

## Timezone Format Examples

All examples use UTC input (as stored in database):

```text
Input datetime: 2025-10-27T18:25:00Z (UTC)
Mission start: 2025-10-27T16:45:00Z

_format_utc(input)
  → "2025-10-27 18:25Z"

_format_eastern(input)
  → "2025-10-27 14:25EDT"  (DST-aware)

_format_offset(input - mission_start)
  → "T+01:40"

_compose_time_block(input, mission_start)
  → "2025-10-27 18:25Z
     2025-10-27 14:25EDT
     T+01:40"
```
