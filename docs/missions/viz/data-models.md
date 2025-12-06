# Visual Data Models & Extraction

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
                     │    └── [start_time, end_time, status, x_state, ka_state, ku_state, reasons, metadata]
                     ├── advisories[TimelineAdvisory]
                     │    └── [timestamp, event_type, transport, severity, message]
                     └── statistics
                          └── [total_duration, nominal_seconds, degraded_seconds, critical_seconds, _aar_blocks]
```

---

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
Status          Recommended Color    LIGHT_* Constant
─────────────────────────────────────────────────────
NOMINAL         Green (#00AA00)      N/A
DEGRADED        Yellow (#FFCC00)     LIGHT_YELLOW (RGB: 1.0, 1.0, 0.85)
CRITICAL        Red (#FF0000)        LIGHT_RED (RGB: 1.0, 0.85, 0.85)
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
TransportState.DEGRADED    "DEGRADED" (or "WARNING" for X-Ku warnings)
TransportState.OFFLINE     "OFFLINE"
```

---

## Data Extraction Pattern: \_segment_rows() Example

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
