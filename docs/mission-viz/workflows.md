# Mission Visualization Workflows

This guide covers complete workflows for extracting and aligning mission data
for visualization purposes.

## Timeline to Route Mapping Pattern

To overlay timeline information on a map:

```python
def align_timeline_to_route(
    timeline: MissionTimeline,
    route: ParsedRoute
) -> list[dict]:
    """Align timeline segments to route points for map visualization."""

    aligned_segments = []
    mission_start = _mission_start_timestamp(timeline)

    for segment in timeline.segments:
        start_time = _ensure_timezone(segment.start_time)

        # Find route position at segment start
        route_position = find_route_position_at_time(
            route,
            start_time,
            mission_start
        )

        if route_position is None:
            continue

        # Calculate segment duration
        end_time = _ensure_timezone(segment.end_time)
        duration_seconds = (end_time - start_time).total_seconds()

        # Create visualization object
        aligned_segments.append({
            "segment_id": segment.id,
            # "nominal", "degraded", "critical"
            "timeline_status": segment.status.value,
            "duration_seconds": duration_seconds,
            "duration_display": _format_seconds_hms(duration_seconds),

            # Position on route
            "waypoint_index": route_position["waypoint_index"],
            "route_progress_percent": route_position["progress_percent"],
            "latitude": route_position["latitude"],
            "longitude": route_position["longitude"],

            # Transport states for stacked bar chart
            "x_state": segment.x_state.value,
            "ka_state": segment.ka_state.value,
            "ku_state": segment.ku_state.value,

            # Metadata for tooltips
            "impacted_transports": [t.value for t in segment.impacted_transports],
            "reasons": segment.reasons,
            "satellites": segment.metadata.get("satellites", {}),
        })

    return aligned_segments
```

## Advisory Timeline Overlay Pattern

```python
def extract_advisories_for_timeline(
    timeline: MissionTimeline,
    mission: Mission | None
) -> list[dict]:
    """Extract advisories for overlay on timeline chart."""

    mission_start = _mission_start_timestamp(timeline)
    advisory_markers = []

    for advisory in timeline.advisories:
        ts_utc = _ensure_timezone(advisory.timestamp)

        # Calculate position relative to mission start
        offset = ts_utc - mission_start
        t_offset = _format_offset(offset)  # "T+HH:MM" or "T-HH:MM"

        # Map transport to display name
        transport_display = TRANSPORT_DISPLAY.get(advisory.transport, advisory.transport.value)

        # Create marker
        advisory_markers.append({
            "id": advisory.id,
            "timestamp": ts_utc,
            "t_offset": t_offset,
            # "transition", "azimuth_conflict", etc.
            "event_type": advisory.event_type,
            # "X-Band", "CommKa", "StarShield"
            "transport": transport_display,
            # "info", "warning", "critical"
            "severity": advisory.severity,
            "message": advisory.message,
            "metadata": advisory.metadata,
        })

    # Sort by timestamp for chart ordering
    advisory_markers.sort(key=lambda x: x["timestamp"])

    return advisory_markers
```

## POI Integration Pattern

```python
def extract_pois_for_visualization(
    pois_with_eta: list[POIWithETA],
    route: ParsedRoute | None
) -> list[dict]:
    """Extract POI data for map markers and ETA labels."""

    poi_markers = []

    for poi in pois_with_eta:
        marker = {
            # Core identification
            "id": poi.poi_id,
            "name": poi.name,
            "category": poi.category,
            "icon": poi.icon,

            # Position on map
            "latitude": poi.latitude,
            "longitude": poi.longitude,

            # ETA information
            "eta_seconds": poi.eta_seconds,
            # "18 min 45 sec", "-1" if no speed
            "eta_display": format_eta(poi.eta_seconds),
            # "anticipated" or "estimated"
            "eta_type": poi.eta_type,
            "is_pre_departure": poi.is_pre_departure,
            # "pre_departure", "in_flight", "post_arrival"
            "flight_phase": poi.flight_phase,

            # Navigation
            "distance_meters": poi.distance_meters,
            "bearing_degrees": poi.bearing_degrees,
            # "on_course", "slightly_off", etc.
            "course_status": poi.course_status,

            # Route awareness (only if active route)
            "is_on_active_route": poi.is_on_active_route,
            # "ahead_on_route", "already_passed", etc.
            "route_aware_status": poi.route_aware_status,
            "projected_waypoint_index": poi.projected_waypoint_index,
            "projected_route_progress": poi.projected_route_progress,
        }

        poi_markers.append(marker)

    return poi_markers
```

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
        "total_duration_seconds": (
            timeline.statistics.get("total_duration_seconds", 0)
        ),
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
