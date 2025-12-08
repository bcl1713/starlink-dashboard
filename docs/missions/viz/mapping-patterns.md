# Timeline to Route & Advisory Patterns

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
            "timeline_status": segment.status.value,           # "nominal", "degraded", "critical"
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

---

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
            "event_type": advisory.event_type,              # "transition", "azimuth_conflict", etc.
            "transport": transport_display,                 # "X-Band", "CommKa", "StarShield"
            "severity": advisory.severity,                  # "info", "warning", "critical"
            "message": advisory.message,
            "metadata": advisory.metadata,
        })

    # Sort by timestamp for chart ordering
    advisory_markers.sort(key=lambda x: x["timestamp"])

    return advisory_markers
```

---

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
            "eta_display": format_eta(poi.eta_seconds),     # "18 min 45 sec", "-1" if no speed
            "eta_type": poi.eta_type,                        # "anticipated" or "estimated"
            "is_pre_departure": poi.is_pre_departure,
            "flight_phase": poi.flight_phase,                # "pre_departure", "in_flight", "post_arrival"

            # Navigation
            "distance_meters": poi.distance_meters,
            "bearing_degrees": poi.bearing_degrees,
            "course_status": poi.course_status,              # "on_course", "slightly_off", etc.

            # Route awareness (only if active route)
            "is_on_active_route": poi.is_on_active_route,
            "route_aware_status": poi.route_aware_status,    # "ahead_on_route", "already_passed", etc.
            "projected_waypoint_index": poi.projected_waypoint_index,
            "projected_route_progress": poi.projected_route_progress,
        }

        poi_markers.append(marker)

    return poi_markers
```
