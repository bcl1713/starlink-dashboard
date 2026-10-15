# Route Models

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## Route progress

`GET /api/routes/{route_id}/progress` requires explicit current-position query
coordinates and returns a calculator dictionary. See the canonical
[progress contract](../eta/progress-endpoints.md) for its fields and timing
availability; it does not return a nested `timing_profile`.

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

Response from `/api/route.geojson` endpoint.

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
        "name": "Planned Route"
      }
    }
  ]
}
```

**Note:** Coordinates are in `[longitude, latitude]` order (GeoJSON standard).

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
