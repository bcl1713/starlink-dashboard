# Mission Visualization Components

This guide covers the data models, status hierarchies, and display patterns used
in mission visualization.

## Timeline Segment Status Visualization

### Status Hierarchy

```text
TimelineStatus (overall segment status)
├── NOMINAL     → All three transports AVAILABLE
├── DEGRADED    → One transport DEGRADED/OFFLINE
└── CRITICAL    → Two+ transports DEGRADED/OFFLINE

Transport States (per-transport detail)
├── AVAILABLE   → Transport is up
├── DEGRADED    → Transport is impaired
└── OFFLINE     → Transport is down
```

### Color Mapping

```text
Status     Recommended Color  LIGHT_* Constant
───────────────────────────────────────────────────────────
NOMINAL    Green (#00AA00)    N/A
DEGRADED   Yellow (#FFCC00)   LIGHT_YELLOW (RGB: 1.0, 1.0, 0.85)
CRITICAL   Red (#FF0000)      LIGHT_RED (RGB: 1.0, 0.85, 0.85)
```

### Transport State Display Names

```text
Transport Enum          Display Name
──────────────────────────────────────
Transport.X = "X"       "X-Band"
Transport.KA = "Ka"     "CommKa"
Transport.KU = "Ku"     "StarShield"

State Enum              Display Value
──────────────────────────────────────
TransportState.AVAILABLE   "AVAILABLE"
TransportState.DEGRADED    "DEGRADED"
                           (or "WARNING" for X-Ku warnings)
TransportState.OFFLINE     "OFFLINE"
```

## Data Extraction Pattern: _segment_rows() Example

The exporter's `_segment_rows()` function (lines 271-331) demonstrates the
proper way to extract timeline data:

```python
def extract_timeline_data(timeline: MissionTimeline, mission: Mission | None):
    """Template for extracting timeline data for visualization."""

    mission_start = _mission_start_timestamp(timeline)  # Get zero point

    # Sort segments chronologically
    for segment in timeline.segments:
        start_utc = _ensure_timezone(segment.start_time)
        end_utc = _ensure_timezone(segment.end_time)

        # Calculate duration
        duration_seconds = max((end_utc - start_utc).total_seconds(), 0)
        duration_hms = _format_seconds_hms(duration_seconds)

        # Get status
        # "NOMINAL", "DEGRADED", "CRITICAL"
        status = segment.status.value.upper()

        # Check for special cases (X-Ku warnings)
        if _segment_is_x_ku_warning(segment):
            status = "WARNING"  # Override display status
            impacted = ""  # Don't show impacted transports
        else:
            impacted = _serialize_transport_list(segment.impacted_transports)

        # Format timestamps (three formats)
        time_block = _compose_time_block(start_utc, mission_start)
        # Returns: "2025-10-27 18:25Z\n2025-10-27 14:25EDT\nT+01:40"

        # Extract transport states
        # "AVAILABLE", "DEGRADED", "OFFLINE"
        x_state = segment.x_state.value.upper()
        ka_state = segment.ka_state.value.upper()
        ku_state = segment.ku_state.value.upper()

        # Get reasons and metadata
        # Comma-separated reason codes
        reasons_text = ", ".join(segment.reasons)
        # Serialize for export
        metadata_json = json.dumps(segment.metadata)

        # Access satellite information
        satellites = segment.metadata.get("satellites", {})
        current_x_satellite = satellites.get("X")
        current_ka_satellites = satellites.get("Ka", [])
```

## Statistics Summary Pattern

```python
def extract_timeline_statistics(
    timeline: MissionTimeline
) -> dict:
    """Extract summary statistics for dashboard display."""

    stats_df = _statistics_rows(timeline)  # Uses existing exporter function

    # Custom interpretation
    stats = {
        "total_duration_seconds": (
            timeline.statistics.get("total_duration_seconds", 0)
        ),
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
            "expected_arrival_time": (
                point.expected_arrival_time.isoformat()
                if point.expected_arrival_time else None
            ),
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
            "expected_arrival_time": (
                wp.expected_arrival_time.isoformat()
                if wp.expected_arrival_time else None
            ),
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
            "departure_time": (
                route.timing_profile.departure_time.isoformat()
                if route.timing_profile and
                   route.timing_profile.departure_time else None
            ),
            "arrival_time": (
                route.timing_profile.arrival_time.isoformat()
                if route.timing_profile and
                   route.timing_profile.arrival_time else None
            ),
            "has_timing_data": (
                route.timing_profile.has_timing_data
                if route.timing_profile else False
            ),
        } if route.timing_profile else None,
    }
```

## Special Cases and Edge Handling

### X-Ku Conflict Warnings

```python
# When segment.x_state == DEGRADED and only reason is "X-Ku Conflict*"
# Display as "WARNING" instead of "DEGRADED"
# Don't show impacted_transports

if _segment_is_x_ku_warning(segment):
    display_status = "WARNING"
    display_impacted = ""
else:
    display_status = segment.status.value.upper()
    display_impacted = _serialize_transport_list(segment.impacted_transports)
```

### Missing Route Timing

```python
# If route doesn't have timing_profile or has_timing_data = False
# Cannot use expected_arrival_time for time-position mapping
# Fall back to distance-based interpolation

if route.timing_profile and route.timing_profile.has_timing_data:
    # Use expected_arrival_time on RoutePoints
    use_timing_aware_alignment()
else:
    # Use distance-based alignment instead
    use_distance_based_alignment()
```

### AAR Windows

```python
# AAR blocks are stored in timeline.statistics["_aar_blocks"]
# They're internal (underscore prefix) and not included in standard statistics

aar_windows = timeline.statistics.get("_aar_blocks", [])
for aar in aar_windows:
    start = _parse_iso_timestamp(aar.get("start"))
    end = _parse_iso_timestamp(aar.get("end"))
    # Insert as special row in timeline export/visualization
```
