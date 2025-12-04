# ETA Models

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## WaypointETA

Response from `/api/routes/{route_id}/eta/waypoint/{waypoint_index}`.

```json
{
  "waypoint_index": 5,
  "waypoint_name": "Departure Point",
  "eta_seconds": 3600,
  "eta_minutes": 60.0,
  "distance_meters": 150000,
  "distance_km": 150.0,
  "estimated_speed_knots": 150.0,
  "has_timing_data": true
}
```

**Fields:**

- `waypoint_index`: Waypoint sequence number
- `waypoint_name`: Name of waypoint (if available)
- `eta_seconds`: Time to reach waypoint (seconds)
- `eta_minutes`: Time to reach waypoint (minutes)
- `distance_meters`: Distance to waypoint
- `distance_km`: Distance to waypoint (km)
- `estimated_speed_knots`: Speed used for calculation
- `has_timing_data`: Whether route has timing information

---

## LocationETA

Response from `/api/routes/{route_id}/eta/location`.

```json
{
  "target_location": {
    "latitude": 40.7128,
    "longitude": -74.006
  },
  "eta_seconds": 1800,
  "eta_minutes": 30.0,
  "distance_meters": 75000,
  "distance_km": 75.0,
  "estimated_speed_knots": 150.0,
  "route_id": "route-001"
}
```

**Fields:**

- `target_location`: Target coordinates
- `eta_seconds`: Time to reach target (seconds)
- `eta_minutes`: Time to reach target (minutes)
- `distance_meters`: Distance to target
- `distance_km`: Distance to target (km)
- `estimated_speed_knots`: Speed used for calculation
- `route_id`: Associated route

---

## ETACacheMetrics

Response from `/api/routes/metrics/eta-cache`.

```json
{
  "cache_enabled": true,
  "ttl_seconds": 5,
  "total_cache_hits": 1250,
  "total_cache_misses": 342,
  "hit_rate_percent": 78.5,
  "cached_entries": 23,
  "average_calculation_time_ms": 12.5,
  "last_cleanup": "2025-11-04T10:30:00Z"
}
```

**Fields:**

- `cache_enabled`: Whether caching is active
- `ttl_seconds`: Time-to-live for cache entries
- `total_cache_hits`: Total successful cache lookups
- `total_cache_misses`: Total cache misses
- `hit_rate_percent`: Cache hit percentage
- `cached_entries`: Current number of cached items
- `average_calculation_time_ms`: Average time per calculation
- `last_cleanup`: Last cache cleanup time

---

## ETAAccuracyMetrics

Response from `/api/routes/metrics/eta-accuracy`.

```json
{
  "total_predictions": 150,
  "total_arrivals": 127,
  "accuracy_stats": {
    "average_error_seconds": 45.3,
    "min_error_seconds": -120,
    "max_error_seconds": 240,
    "median_error_seconds": 30.0,
    "std_deviation_seconds": 67.5
  },
  "recent_predictions": [
    {
      "predicted_time": "2025-11-04T10:30:00Z",
      "actual_arrival_time": "2025-11-04T10:31:30Z",
      "error_seconds": 90,
      "destination": "waypoint_5"
    }
  ]
}
```

**Fields:**

- `total_predictions`: Total ETA predictions made
- `total_arrivals`: Total actual arrivals recorded
- `accuracy_stats`: Statistical accuracy metrics
- `recent_predictions`: Recent prediction accuracy samples

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
