# Mission Data Structures Documentation - Index

This collection of documents provides comprehensive reference material for understanding and implementing map and chart generation using mission data.

## Document Overview

### 1. MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md (Start Here!)
**Best for:** Quick lookups, implementation jumpstart
- One-page cheat sheet with all enum values
- Quick extraction patterns for common tasks
- Helper function signatures
- Import statements
- Critical notes and data validation rules

**Read this first** if you're implementing map/chart functions.

### 2. MISSION-DATA-STRUCTURES.md (Comprehensive Reference)
**Best for:** Deep understanding, complete field listings
- Full class definitions with all field descriptions
- Enum complete reference (TimelineStatus, TransportState, Transport, MissionPhase)
- Transport configuration details (XTransition, KaOutage, AARWindow, KuOutageOverride)
- Timeline advisory model
- Exporter helper function specifications
- Key data flow patterns

**Read this** when you need to understand relationships and complete data models.

### 3. MISSION-DATA-STRUCTURES-SUMMARY.txt (Executive Summary)
**Best for:** High-level overview, architectural understanding
- Structured text format for quick scanning
- 1-2 sentence descriptions of each section
- Key insights highlighted
- Recommended data structures for visualization
- Important caveats and edge cases

**Read this** to understand the big picture and data flow.

### 4. MISSION-VISUALIZATION-GUIDE.md (Implementation Patterns)
**Best for:** Writing actual visualization code, seeing examples
- Complete data model tree diagram
- Status and color mapping tables
- `_segment_rows()` implementation example (the canonical extraction pattern)
- Timeline-to-route mapping pattern with code examples
- Advisory overlay pattern
- POI integration pattern
- Statistics extraction pattern
- Route geometry pattern
- Complete end-to-end data flow example
- Timezone format examples
- Special case handling

**Read this** when implementing actual visualization functions.

---

## Document Dependencies

```
Start: MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md
   |
   +-> Need deep dive? MISSION-DATA-STRUCTURES-SUMMARY.txt
   |       |
   |       +-> Need complete spec? MISSION-DATA-STRUCTURES.md
   |
   +-> Implementing code? MISSION-VISUALIZATION-GUIDE.md
```

---

## Key Concepts Quick Links

### Core Data Models
| Model | Purpose | Key Fields |
|-------|---------|-----------|
| **Mission** | Flight plan wrapper | id, name, route_id, transports, is_active |
| **MissionTimeline** | Communication state timeline | mission_id, segments, advisories, statistics |
| **TimelineSegment** | Fixed-duration state block | start_time, end_time, status, x/ka/ku_state |
| **ParsedRoute** | Geographic flight path | points (ordered waypoints), timing_profile |
| **POI/POIWithETA** | Points of interest | name, lat/lon, eta_seconds, route_aware_status |

### Core Enums
| Enum | Values | Purpose |
|------|--------|---------|
| **TimelineStatus** | NOMINAL, DEGRADED, CRITICAL | Overall segment health |
| **TransportState** | AVAILABLE, DEGRADED, OFFLINE | Per-transport status |
| **Transport** | X, KA, KU | Transport type identifiers |
| **MissionPhase** | PRE_DEPARTURE, IN_FLIGHT, POST_ARRIVAL | Flight state |

### Helper Functions by Category

**Time Handling:**
- `_ensure_timezone()` - Make datetimes UTC-aware
- `_mission_start_timestamp()` - Get mission T+0
- `_format_utc()`, `_format_eastern()`, `_format_offset()` - Format times
- `_compose_time_block()` - Get all three time formats

**Data Processing:**
- `_format_seconds_hms()` - Duration to "HH:MM:SS"
- `_serialize_transport_list()` - List to "X-Band, HCX"
- `_segment_rows()` - DataFrame conversion (canonical pattern)
- `_segment_at_time()` - Find segment at time T
- `_segment_is_x_ku_warning()` - Detect special warning case

---

## Recommended Reading Path by Use Case

### Case 1: Building a Timeline Bar Chart
1. Read: MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md (sections: Core Classes, Helper Functions)
2. Read: MISSION-VISUALIZATION-GUIDE.md (section: Data Extraction Pattern)
3. Reference: MISSION-DATA-STRUCTURES.md (TimelineSegment class)

### Case 2: Building a Route Map with Overlay
1. Read: MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md (all sections)
2. Read: MISSION-VISUALIZATION-GUIDE.md (sections: Route Geometry Pattern, Timeline to Route Mapping)
3. Reference: MISSION-DATA-STRUCTURES.md (ParsedRoute, RoutePoint classes)

### Case 3: Building an Integrated Dashboard
1. Read: MISSION-DATA-STRUCTURES-SUMMARY.txt (entire document)
2. Read: MISSION-VISUALIZATION-GUIDE.md (section: Complete Data Flow Example)
3. Reference: MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md (as needed during implementation)

### Case 4: Understanding Transport States and Colors
1. Read: MISSION-VISUALIZATION-GUIDE.md (section: Timeline Segment Status Visualization)
2. Reference: MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md (Enum Values table)

### Case 5: Handling Special Cases and Edge Conditions
1. Read: MISSION-DATA-STRUCTURES-SUMMARY.txt (section 10: Important Caveats)
2. Read: MISSION-VISUALIZATION-GUIDE.md (section: Special Cases and Edge Handling)
3. Reference: MISSION-DATA-STRUCTURES.md (Special notes within class descriptions)

---

## Implementation Checklists

### Implementing a Segment-to-Chart Function
- [ ] Import `_mission_start_timestamp`, `_ensure_timezone`, `_format_seconds_hms`
- [ ] Call `mission_start = _mission_start_timestamp(timeline)`
- [ ] For each segment:
  - [ ] Call `_ensure_timezone()` on start_time and end_time
  - [ ] Calculate duration: `(end - start).total_seconds()`
  - [ ] Get status: `segment.status.value.upper()`
  - [ ] Check if X-Ku warning: `_segment_is_x_ku_warning(segment)`
  - [ ] Extract transport states: `x_state.value`, `ka_state.value`, `ku_state.value`
  - [ ] Extract satellites: `segment.metadata.get("satellites", {})`

### Implementing a Route Map Function
- [ ] Import `ParsedRoute` and `_ensure_timezone`
- [ ] Call `route.get_bounds()` for map pan/zoom
- [ ] Extract line: `[(p.latitude, p.longitude) for p in route.points]`
- [ ] Extract waypoints: iterate `route.waypoints`, extract name, lat, lon, role
- [ ] If `route.timing_profile.has_timing_data`, use `expected_arrival_time` for positioning

### Implementing a POI Marker Function
- [ ] Import `POIWithETA` model
- [ ] For each POI:
  - [ ] Show: id, name, latitude, longitude, icon, category
  - [ ] Show ETA: `eta_seconds` formatted with `_format_seconds_hms()`
  - [ ] Show status: `route_aware_status` ("ahead_on_route", "already_passed", etc.)
  - [ ] Show type: `eta_type` ("anticipated" or "estimated")

---

## Common Questions and Answers

**Q: What's the primary data source for timeline visualization?**
A: `MissionTimeline.segments` - it's a list of `TimelineSegment` objects ordered by time, each with status, transport states, and duration.

**Q: How do I position timeline segments on a map?**
A: Use `segment.metadata["satellites"]` and time-matching to route waypoints via `expected_arrival_time`. See MISSION-VISUALIZATION-GUIDE.md section "Timeline to Route Mapping Pattern".

**Q: What color should each status show?**
A: NOMINAL=Green, DEGRADED=Yellow (use LIGHT_YELLOW), CRITICAL=Red (use LIGHT_RED). See color mapping table in MISSION-VISUALIZATION-GUIDE.md.

**Q: How do I handle X-Ku conflict warnings?**
A: Call `_segment_is_x_ku_warning(segment)`. If True, display as "WARNING" even though status is DEGRADED. See MISSION-DATA-STRUCTURES-SUMMARY.txt section 10.

**Q: Are all datetimes in UTC?**
A: Yes. Always call `_ensure_timezone()` to make them UTC-aware. Use `_format_eastern()` for display. Use `EASTERN_TZ` from exporter.

**Q: What are the transport display names?**
A: X→"X-Band", Ka→"HCX", Ku→"StarShield". See TRANSPORT_DISPLAY constant in MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md.

**Q: Where do advisory events come from?**
A: `MissionTimeline.advisories` - it's a list of `TimelineAdvisory` objects with timestamp, event_type, transport, severity, and message.

**Q: What route information is available?**
A: From `ParsedRoute`: points (lat/lon/alt), waypoints (named), timing_profile (departure/arrival), metadata (name/description). Use `get_total_distance()` and `get_bounds()` methods.

**Q: Are projected POI fields always populated?**
A: No, only when route is active. Check `projected_route_progress` to see if populated. Always validate before using.

---

## Files Location

All documentation files are in: `/home/brian/Projects/starlink-dashboard-dev/docs/`

**Related Mission Planning Documents:**
- `MISSION-PLANNING-GUIDE.md` - Mission planning workflow and features
- `MISSION-COMM-SOP.md` - Communication procedures and best practices

---

## Quick Navigation

**Looking for enum values?** → MISSION-DATA-STRUCTURES-QUICK-REFERENCE.md

**Looking for implementation example?** → MISSION-VISUALIZATION-GUIDE.md

**Looking for complete field list?** → MISSION-DATA-STRUCTURES.md

**Looking for summary/architecture?** → MISSION-DATA-STRUCTURES-SUMMARY.txt

**Looking for this index?** → You're reading it!

---

## Document Maintenance

Created: 2025-11-17
Last Updated: 2025-11-17

These documents are auto-generated from source code inspection and should be reviewed if code changes are made to:
- `backend/starlink-location/app/mission/models.py`
- `backend/starlink-location/app/mission/exporter.py`
- `backend/starlink-location/app/models/route.py`
- `backend/starlink-location/app/models/poi.py`

