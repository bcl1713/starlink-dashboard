# Timeline Preview Models

**Purpose**: Data contracts for the real-time mission leg timeline preview API.
**Audience**: API consumers, frontend developers, integrators

[Back to Models index](./README.md) | [Back to API reference](../README.md)

---

## Request Schema: `TimelinePreviewRequest`

```json
{
  "transports": {
    "initial_x_satellite_id": "X-1",
    "initial_ka_satellite_ids": ["AOR", "POR"],
    "x_transitions": [
      {
        "id": "x-transition-1",
        "latitude": 35.0,
        "longitude": -120.0,
        "target_satellite_id": "X-2"
      }
    ],
    "ka_outages": [
      {
        "start_time": "2025-10-27T17:00:00Z",
        "duration_seconds": 600
      }
    ],
    "aar_windows": [
      {
        "id": "aar-1",
        "start_waypoint_name": "WP12",
        "end_waypoint_name": "WP16"
      }
    ],
    "ku_overrides": []
  },
  "adjusted_departure_time": "2025-10-27T17:25:00Z"
}
```

### Request Fields

- `transports.initial_x_satellite_id` — active X-Band satellite ID
- `transports.initial_ka_satellite_ids` — Ka coverage regions or satellite IDs to seed the preview
- `transports.x_transitions[]` — X-Band handoff points and target satellite IDs
- `transports.ka_outages[]` — manual Ka outage windows used to simulate degraded service
- `transports.aar_windows[]` — AAR windows that can suppress X-Band coverage
- `transports.ku_overrides[]` — optional override objects for Ku behavior
- `adjusted_departure_time` — optional ISO-8601 timestamp used to shift the timeline calculation

---

## Response Schema: `MissionLegTimeline`

The preview endpoint returns the standard mission-leg timeline structure, with route samples included for preview rendering.

### Top-Level Fields

- `mission_leg_id` — associated leg ID
- `created_at` — preview generation timestamp (UTC)
- `segments[]` — ordered list of `TimelineSegment` objects
- `advisories[]` — operator advisories, if any
- `statistics` — summary metrics for the preview
- `samples[]` — optional route samples used by the map overlay

### `TimelineSegment`

- `id` — unique segment identifier
- `start_time` — segment start time in UTC
- `end_time` — segment end time in UTC
- `status` — `nominal`, `degraded`, or `critical`
- `x_state` — `available`, `degraded`, or `offline`
- `ka_state` — `available`, `degraded`, or `offline`
- `ku_state` — `available`, `degraded`, or `offline`
- `reasons[]` — machine-readable reason codes for the segment status
- `impacted_transports[]` — transport list that contributed to degradation
- `metadata` — additional context such as satellite IDs or trigger data

### `RouteSampleData`

- `timestamp` — UTC sample timestamp
- `latitude` — decimal degrees
- `longitude` — decimal degrees
- `altitude` — optional altitude in meters
- `coverage[]` — Ka coverage set for that sample

The frontend turns these samples into the green/yellow/red route overlay shown
in the preview panel.

### Statistics

Typical preview statistics include:

- `total_duration_seconds`
- `nominal_seconds`
- `degraded_seconds`
- `critical_seconds`

Those values are what the user compares while deciding whether to keep
experimenting or save the leg.

---

## Example Response Shape

```json
{
  "mission_leg_id": "mission-leg-001",
  "created_at": "2025-10-27T10:00:00Z",
  "segments": [
    {
      "id": "segment-001",
      "start_time": "2025-10-27T16:45:00Z",
      "end_time": "2025-10-27T18:25:00Z",
      "status": "nominal",
      "x_state": "available",
      "ka_state": "available",
      "ku_state": "available",
      "reasons": [],
      "impacted_transports": [],
      "metadata": {}
    }
  ],
  "advisories": [],
  "statistics": {
    "total_duration_seconds": 19800,
    "nominal_seconds": 18000,
    "degraded_seconds": 1200,
    "critical_seconds": 600
  },
  "samples": []
}
```
