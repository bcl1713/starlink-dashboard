# Status Data Flow Patterns

Key data flow patterns for map and chart generation using mission status data.

---

## Data Flow for Map Visualization

1. Get Mission from database
2. Use mission.route_id to fetch ParsedRoute via route manager
3. Extract ParsedRoute.points for route geometry
4. Get associated POIs (route_id filtering)
5. Get MissionTimeline segments
6. Project timeline segments onto route via time-distance analysis

---

## Data Flow for Timeline Chart

1. Get MissionTimeline with segments and advisories
2. Use `_mission_start_timestamp()` to establish timeline zero
3. Process segments:
   - Extract start_time, end_time, status, transport states
   - Use `_format_seconds_hms()` for durations
   - Check impacted_transports for visual highlighting
4. Use `_compose_time_block()` for multi-format timestamps
5. Include advisories as overlays on timeline

---

## Combined Data Structure

1. Create data structure mapping:
   - Route points (lat/lon/time) → Map geometry
   - Timeline segments (start/end/status) → Timeline bars
   - POIs (lat/lon) → Map markers with ETA data
   - Advisories (timestamp/transport) → Timeline annotations
