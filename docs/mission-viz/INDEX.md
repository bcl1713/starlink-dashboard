# Mission Visualization Guide

## Data Structures and Implementation Patterns for Map/Chart Generation

This guide provides comprehensive documentation for extracting and visualizing
mission data, including timelines, routes, and POIs. The guide is organized into
two main sections:

- **[Components](./components.md)** - Data models, status hierarchies, and color
  mapping
- **[Workflows](./workflows.md)** - Complete extraction patterns and examples

## Visual Data Model Overview

```text
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
                     │    └── [start_time, end_time, status,
                     │         x_state, ka_state, ku_state,
                     │         reasons, metadata]
                     ├── advisories[TimelineAdvisory]
                     │    └── [timestamp, event_type, transport, severity, message]
                     └── statistics
                          └── [total_duration, nominal_seconds,
                               degraded_seconds, critical_seconds,
                               _aar_blocks]
```

## Quick Reference

### Timeline Segment Status

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

### Transport Display Names

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

## What's Next?

- **Understand the components:** Read about
  [data structures and status hierarchies](./components.md)
- **Build visualizations:** Follow
  [extraction patterns and workflows](./workflows.md)

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
