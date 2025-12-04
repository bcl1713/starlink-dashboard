# Route Progress Endpoints

[Back to API Reference](../README.md) | [ETA Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## GET `/api/routes/{route_id}/progress`

Get overall route progress and timing metrics.

**Description:** Returns current progress along the route, next waypoint
information, and timing profile.

**Parameters:**

- `route_id` (path, required): Route identifier
- `current_position_lat` (query, optional): Current latitude
- `current_position_lon` (query, optional): Current longitude

**Response:**

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

**Status Codes:**

- `200 OK` - Progress retrieved
- `404 Not Found` - Route not found

**Use Case:** Progress dashboards, ETA updates, route completion monitoring.

---

## GET `/api/routes/active/timing`

Get timing profile of the currently active route.

**Description:** Returns detailed timing information for the active route, if
available.

**Response:**

```json
{
  "route_id": "route-001",
  "has_timing_data": true,
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z",
    "total_expected_duration_seconds": 6300,
    "segment_count_with_timing": 28
  },
  "segments": [
    {
      "waypoint_index": 0,
      "waypoint_name": "Departure Point",
      "expected_arrival_time": "2025-10-27T16:45:00Z",
      "expected_segment_speed_knots": 150.0
    }
  ]
}
```

**Status Codes:**

- `200 OK` - Timing profile available
- `404 Not Found` - No active route or no timing data

**Use Case:** Timing visualization, speed profile analysis, flight plan review.

---

## Examples

### cURL Examples

**Get Route Progress:**

```bash
curl "http://localhost:8000/api/routes/route-001/progress"
```

**Get Active Route Timing:**

```bash
curl "http://localhost:8000/api/routes/active/timing"
```

### Python Examples

```python
import requests

# Get route progress
response = requests.get('http://localhost:8000/api/routes/route-001/progress')
progress = response.json()
print(f"Progress: {progress['progress_percent']}%")
```

---

[Back to API Reference](../README.md) | [ETA Index](./README.md)
