# Route Models

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## RouteProgress

Response from `/api/routes/{route_id}/progress`.

```json
{
  "route_id": "route-001",
  "progress_percent": 35.5,
  "current_waypoint_index": 12,
  "total_waypoints": 34,
  "waypoints_remaining": 22,
  "distance_traveled_meters": 45000,
  "distance_remaining_meters": 84000,
  "total_distance_meters": 129000,
  "eta_to_destination_seconds": 2400,
  "average_speed_knots": 150.0,
  "has_timing_data": true,
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z",
    "total_expected_duration_seconds": 6300,
    "segment_count_with_timing": 28
  }
}
```

**Fields:**

- `route_id`: Route identifier
- `progress_percent`: Progress along route (0-100)
- `current_waypoint_index`: Index of current/next waypoint
- `total_waypoints`: Total number of waypoints
- `waypoints_remaining`: How many waypoints left
- `distance_traveled_meters`: Distance covered so far
- `distance_remaining_meters`: Distance left to destination
- `total_distance_meters`: Total route distance
- `eta_to_destination_seconds`: Estimated time to final waypoint
- `average_speed_knots`: Current average speed
- `has_timing_data`: Whether route has timing information
- `timing_profile`: Timing data (if available)

---

## RouteTimingProfile

```json
{
  "departure_time": "2025-10-27T16:45:00Z",
  "arrival_time": "2025-10-27T18:30:00Z",
  "total_expected_duration_seconds": 6300,
  "segment_count_with_timing": 28
}
```

**Fields:**

- `departure_time`: Expected departure time (ISO-8601)
- `arrival_time`: Expected arrival time (ISO-8601)
- `total_expected_duration_seconds`: Flight duration
- `segment_count_with_timing`: Number of segments with timing data

---

## GeoJSON Feature Collection

Response from `/route.geojson` endpoint.

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-74.006, 40.7128],
          [-74.005, 40.7138]
        ]
      },
      "properties": {
        "name": "Position History"
      }
    }
  ]
}
```

**Note:** Coordinates are in `[longitude, latitude]` order (GeoJSON standard).

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
