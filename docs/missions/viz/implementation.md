# Visualization Implementation & Logic

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

---

## Complete Data Flow Example

```python
async def generate_mission_visualization(mission_id: str) -> dict:
    """Complete flow for map and chart generation."""

    # 1. Fetch core data
    mission = await mission_service.get_mission(mission_id)
    timeline = await mission_service.get_timeline(mission_id)
    route = await route_manager.get_route(mission.route_id)
    pois = await poi_service.list_pois(route_id=mission.route_id)

    # 2. Prepare timeline base
    mission_start = _mission_start_timestamp(timeline)

    # 3. Extract visualization data
    timeline_segments = []
    for segment in timeline.segments:
        timeline_segments.append({
            "id": segment.id,
            "start": _ensure_timezone(segment.start_time),
            "end": _ensure_timezone(segment.end_time),
            "duration_seconds": (
                _ensure_timezone(segment.end_time) -
                _ensure_timezone(segment.start_time)
            ).total_seconds(),
            "status": segment.status.value,
            "x_state": segment.x_state.value,
            "ka_state": segment.ka_state.value,
            "ku_state": segment.ku_state.value,
            "reasons": segment.reasons,
            "satellites": segment.metadata.get("satellites", {}),
        })

    advisories = []
    for advisory in timeline.advisories:
        advisories.append({
            "id": advisory.id,
            "timestamp": _ensure_timezone(advisory.timestamp),
            "event_type": advisory.event_type,
            "transport": TRANSPORT_DISPLAY[advisory.transport],
            "severity": advisory.severity,
            "message": advisory.message,
        })

    # 4. Prepare route geometry
    route_bounds = route.get_bounds()
    route_line = [
        {"lat": p.latitude, "lon": p.longitude}
        for p in route.points
    ]

    # 5. Prepare POI data
    poi_list = [
        {
            "id": poi.poi_id,
            "name": poi.name,
            "latitude": poi.latitude,
            "longitude": poi.longitude,
            "eta_seconds": poi.eta_seconds,
            "course_status": poi.course_status,
        }
        for poi in pois
    ]

    # 6. Prepare statistics
    stats = {
        "total_duration_seconds": timeline.statistics.get("total_duration_seconds", 0),
        "nominal_percent": (
            timeline.statistics.get("nominal_seconds", 0) /
            max(timeline.statistics.get("total_duration_seconds", 1), 1) * 100
        ),
        "degraded_percent": (
            timeline.statistics.get("degraded_seconds", 0) /
            max(timeline.statistics.get("total_duration_seconds", 1), 1) * 100
        ),
        "critical_percent": (
            timeline.statistics.get("critical_seconds", 0) /
            max(timeline.statistics.get("total_duration_seconds", 1), 1) * 100
        ),
    }

    # 7. Return unified visualization object
    return {
        "mission": {
            "id": mission.id,
            "name": mission.name,
            "description": mission.description,
        },
        "timeline": {
            "mission_start": mission_start.isoformat(),
            "segments": timeline_segments,
            "advisories": advisories,
            "statistics": stats,
        },
        "route": {
            "bounds": route_bounds,
            "line": route_line,
            "distance_km": route.get_total_distance() / 1000.0,
        },
        "pois": poi_list,
    }
```

---

## Summary

Key takeaways for map/chart visualization implementation:

1. Always use `_ensure_timezone()` on all datetime values
2. Use `_mission_start_timestamp()` to establish timeline zero point
3. Segments are the primary data source for timeline visualization
4. Route points provide geographic data for mapping
5. Advisories layer operational context over the timeline
6. POIs add location markers to maps
7. Statistics provide high-level overview metrics
8. Special case: X-Ku conflict warnings display as "WARNING"
9. Color coding: Green (NOMINAL), Yellow (DEGRADED), Red (CRITICAL)
10. Transport display names: X→"X-Band", Ka→"CommKa", Ku→"StarShield"
