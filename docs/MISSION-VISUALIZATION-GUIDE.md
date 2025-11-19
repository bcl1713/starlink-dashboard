# Mission Visualization Guide
## Data Structures and Implementation Patterns for Map/Chart Generation

---

## Visual Data Model Overview

```
Mission
  ├── route_id ──> ParsedRoute
  │                  ├── metadata (name, point_count)
  │                  ├── points[RoutePoint]
  │                  │    └── [lat, lon, alt, expected_arrival_time, speed]
  │                  ├── waypoints[RouteWaypoint]
  │                  │    └── [name, lat, lon, role, expected_arrival_time]
  │                  └── timing_profile
  │                       └── [departure, arrival, duration, flight_status]
  │
  ├── transports ──> TransportConfig
  │                  ├── initial_x_satellite_id
  │                  ├── initial_ka_satellite_ids
  │                  ├── x_transitions[XTransition]
  │                  ├── ka_outages[KaOutage]
  │                  └── aar_windows[AARWindow]
  │
  └── (related) ──> MissionTimeline
                     ├── segments[TimelineSegment]
                     │    └── [start_time, end_time, status, x_state, ka_state, ku_state, reasons, metadata]
                     ├── advisories[TimelineAdvisory]
                     │    └── [timestamp, event_type, transport, severity, message]
                     └── statistics
                          └── [total_duration, nominal_seconds, degraded_seconds, critical_seconds, _aar_blocks]
```

---

## Timeline Segment Status Visualization

### Status Hierarchy
```
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
```
Status          Recommended Color    LIGHT_* Constant
─────────────────────────────────────────────────────
NOMINAL         Green (#00AA00)      N/A
DEGRADED        Yellow (#FFCC00)     LIGHT_YELLOW (RGB: 1.0, 1.0, 0.85)
CRITICAL        Red (#FF0000)        LIGHT_RED (RGB: 1.0, 0.85, 0.85)
```

### Transport State Display Names
```
Transport Enum          Display Name
──────────────────────────────────────
Transport.X = "X"       "X-Band"
Transport.KA = "Ka"     "HCX"
Transport.KU = "Ku"     "StarShield"

State Enum              Display Value
──────────────────────────────────────
TransportState.AVAILABLE   "AVAILABLE"
TransportState.DEGRADED    "DEGRADED" (or "WARNING" for X-Ku warnings)
TransportState.OFFLINE     "OFFLINE"
```

---

## Data Extraction Pattern: _segment_rows() Example

The exporter's `_segment_rows()` function (lines 271-331) demonstrates the proper way to extract timeline data:

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
        status = segment.status.value.upper()  # "NOMINAL", "DEGRADED", "CRITICAL"
        
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
        x_state = segment.x_state.value.upper()      # "AVAILABLE", "DEGRADED", "OFFLINE"
        ka_state = segment.ka_state.value.upper()
        ku_state = segment.ku_state.value.upper()
        
        # Get reasons and metadata
        reasons_text = ", ".join(segment.reasons)  # Comma-separated reason codes
        metadata_json = json.dumps(segment.metadata)  # Serialize for export
        
        # Access satellite information
        satellites = segment.metadata.get("satellites", {})
        current_x_satellite = satellites.get("X")
        current_ka_satellites = satellites.get("Ka", [])
```

---

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
            "transport": transport_display,                 # "X-Band", "HCX", "StarShield"
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

---

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

```
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

---

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
10. Transport display names: X→"X-Band", Ka→"HCX", Ku→"StarShield"

