# Timeline Preview API Endpoint

**Purpose**: Recalculate a mission leg timeline in real time without persisting the result to disk.
**Audience**: API consumers, integrators, frontend developers

[Back to API endpoints](./README.md)

---

## POST `/api/v2/missions/{mission_id}/legs/{leg_id}/timeline/preview`

Generate a preview timeline for a mission leg using the current transport configuration and optional adjusted departure time.

The endpoint returns the same timeline structure used by saved legs, plus route samples for preview rendering on the map.
The frontend uses this endpoint whenever the user pauses editing long enough for the preview debounce to settle, so the UI and API stay in lockstep.

### Request Body

The backend accepts a JSON object with these fields:

- `transports` — transport configuration to preview
- `adjusted_departure_time` — optional ISO-8601 timestamp used to shift the timeline

The `transports` object matches the frontend `TimelinePreviewRequest` contract:

- `initial_x_satellite_id` — string
- `initial_ka_satellite_ids` — string array
- `x_transitions[]` — objects with `id`, `latitude`, `longitude`, and `target_satellite_id`
- `ka_outages[]` — objects with `start_time` and `duration_seconds`
- `aar_windows[]` — objects with `id`, `start_waypoint_name`, and `end_waypoint_name`
- `ku_overrides[]` — free-form override objects for Ku behavior

### Response Body

Returns a `MissionLegTimeline` object:

- `mission_leg_id` — leg identifier
- `created_at` — when the preview was generated
- `segments[]` — ordered timeline segments
- `advisories[]` — operator advisories, if any
- `statistics` — summary metrics such as total, nominal, degraded, and critical time
- `samples[]` — route samples used to render the preview map

### Status Codes

- `200 OK` — preview generated successfully
- `400 Bad Request` — invalid transport configuration or malformed `adjusted_departure_time`
- `404 Not Found` — mission, leg, or route missing
- `500 Internal Server Error` — calculation failure

### Notes

- Preview calculations do not write timeline data to disk.
- The endpoint reuses the same timeline calculation engine as saved timelines.
- No rate limiting is currently implemented.
- Route `samples[]` are intended for the color-coded map overlay, not just for
  generic diagnostics.

---

## Example Response

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
  "samples": [
    {
      "timestamp": "2025-10-27T16:45:00Z",
      "latitude": 35.0,
      "longitude": -120.0,
      "altitude": 10000,
      "coverage": ["AOR", "POR"]
    }
  ]
}
```

---

## Related Documentation

- [Timeline Preview Models](../models/timeline-preview.md)
- [Timeline Preview Examples](../examples/timeline-preview.md)
- [Mission Planning Guide](../../missions/planning/overview.md)
