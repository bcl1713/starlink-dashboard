# Mission Data Structures Reference

For Map and Chart Generation in Mission Exporter

---

## Overview

This reference documents the data structures used throughout the mission
planning and monitoring system. These structures are essential for understanding
how mission timelines, routes, communication status, and visualizations are
generated and exported.

**Primary Use Cases:**

- Building map visualizations with route geometry and POI markers
- Creating timeline charts with communication status segments
- Generating mission export documents (PDF, Excel, CSV)
- Understanding data flow for integration and API development

---

## Documentation Contents

### [Mission and Timeline Models](mission-models.md)

Core data structures for mission planning and timeline generation:

- **Mission Model** - Mission configuration and metadata
- **MissionTimeline Model** - Computed timeline with segments and advisories
- **TimelineSegment Model** - Individual time periods with communication status
- **TimelineAdvisory Model** - Operator notifications and warnings
- **TransportConfig** - Satellite and communication system configuration
- **Route Data Structures** - ParsedRoute, RoutePoint, RouteWaypoint, metadata
- **POI Data Structures** - POI and POIWithETA models for point-of-interest data

### [Status Enums and Helper Functions](status-enums.md)

Enumeration types and utility functions used across the system:

- **TimelineStatus** - NOMINAL, DEGRADED, CRITICAL
- **TransportState** - AVAILABLE, DEGRADED, OFFLINE
- **Transport** - X, Ka, Ku communication systems
- **MissionPhase** - Pre-departure, in-flight, post-arrival
- **Exporter Helper Functions** - Time formatting, display mapping, data
  conversion
- **Key Data Flow** - Integration patterns for map and chart generation

---

## Quick Reference

### Key File Locations

```text
backend/starlink-location/app/
├── mission/
│   ├── models.py              # Mission, Timeline, Segment, Advisory models
│   └── exporter.py            # Export helper functions and constants
├── models/
│   ├── route.py               # ParsedRoute, RoutePoint, RouteWaypoint
│   └── poi.py                 # POI, POIWithETA models
```

### Common Integration Patterns

**To Build a Map Visualization:**

1. Get Mission from database
2. Use mission.route_id to fetch ParsedRoute via route manager
3. Extract ParsedRoute.points for route geometry
4. Get associated POIs (route_id filtering)
5. Get MissionTimeline segments
6. Project timeline segments onto route via time-distance analysis

**To Build a Timeline Chart:**

1. Get MissionTimeline with segments and advisories
2. Use `_mission_start_timestamp()` to establish timeline zero
3. Process segments for start_time, end_time, status, transport states
4. Use `_compose_time_block()` for multi-format timestamps
5. Include advisories as overlays on timeline

**To Combine Data:**

1. Create data structure mapping:
   - Route points (lat/lon/time) → Map geometry
   - Timeline segments (start/end/status) → Timeline bars
   - POIs (lat/lon) → Map markers with ETA data
   - Advisories (timestamp/transport) → Timeline annotations

---

## Important Notes

### Timezone Handling

- All stored times are UTC (ISO-8601 format)
- Use `EASTERN_TZ = ZoneInfo("America/New_York")` for Eastern display
- Always use `_ensure_timezone()` to make datetimes UTC-aware

### Duration Formatting

- Use `_format_seconds_hms()` for all duration displays
- Handles negative values with "-" prefix
- Format: "HH:MM:SS"

### Transport State Visualization

- X-Ku conflict warnings display as "WARNING" even though state is "DEGRADED"
- Use `_segment_is_x_ku_warning()` to detect this special case
- Color degraded/offline states using LIGHT_YELLOW (1 transport) or LIGHT_RED
  (2+ transports)

### Route Integration

- `ParsedRoute.get_total_distance()` returns meters via Haversine formula
- `ParsedRoute.get_bounds()` returns geographic bounding box
- RoutePoints have `expected_arrival_time` for timeline alignment
- Use `projected_waypoint_index` and `projected_route_progress` to position
  segments on route

### POI Integration

- POI.projected\_\* fields only populated when route is active
- POIWithETA includes `route_aware_status` for visualization logic
- `eta_type` switches between "anticipated" (pre-departure) and "estimated"
  (in-flight)
