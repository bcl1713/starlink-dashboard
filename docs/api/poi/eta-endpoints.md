# POI ETA Endpoints

[Back to API Reference](../README.md) | [POI Index](./README.md)

---

## GET `/api/pois/etas`

Get all POIs with real-time ETA and distance data.
Returns a wrapped response object (not a flat array).

**Query Parameters:**

- `route_id` (string, optional) - Filter by route ID
- `latitude` (float, optional) - Current latitude
  (default: from telemetry)
- `longitude` (float, optional) - Current longitude
  (default: from telemetry)
- `speed_knots` (float, optional) - Current speed
  (default: from telemetry)
- `status_filter` (string, optional) - Filter by course
  status (comma-separated: `on_course`, `slightly_off`,
  `off_track`, `behind`)
- `category` (string, optional) - Filter by POI category
  (comma-separated: `departure`, `arrival`, `waypoint`,
  `alternate`)
- `active_only` (bool, optional, default: true) - Filter
  to show only active POIs

**Response:**

```json
{
  "pois": [
    {
      "poi_id": "jfk-airport",
      "name": "JFK Airport",
      "latitude": 40.6413,
      "longitude": -73.7781,
      "category": "airport",
      "icon": "airport",
      "active": true,
      "eta_seconds": 1080.0,
      "eta_type": "estimated",
      "is_pre_departure": false,
      "flight_phase": "in_flight",
      "distance_meters": 45000.0,
      "bearing_degrees": 125.0,
      "course_status": "on_course",
      "is_on_active_route": true,
      "projected_latitude": 40.64,
      "projected_longitude": -73.78,
      "projected_waypoint_index": 42,
      "projected_route_progress": 45.5,
      "route_aware_status": "ahead_on_route"
    }
  ],
  "total": 1,
  "timestamp": "2025-10-31T10:30:00.000000Z"
}
```

### Response Fields

**Top-level:**

- `pois` (array) - List of POIs with ETA data
- `total` (int) - Total number of POIs returned
- `timestamp` (string) - ISO-8601 calculation timestamp

**Per-POI fields (`POIWithETA`):**

- `poi_id` (string) - POI identifier
- `name` (string) - POI name
- `latitude` (float) - POI latitude
- `longitude` (float) - POI longitude
- `category` (string?) - POI category
- `icon` (string) - Icon identifier (default: `marker`)
- `active` (bool) - Whether POI is currently active
- `eta_seconds` (float) - ETA in seconds (-1 if no speed)
- `eta_type` (string) - `anticipated` or `estimated`
- `is_pre_departure` (bool) - True when flight has not
  yet departed
- `flight_phase` (string?) - `pre_departure`,
  `in_flight`, or `post_arrival`
- `distance_meters` (float) - Distance to POI in meters
- `bearing_degrees` (float?) - Bearing in degrees
  (0=North)
- `course_status` (string?) - `on_course`,
  `slightly_off`, `off_track`, or `behind`
- `is_on_active_route` (bool) - Whether POI projects to
  active route
- `projected_latitude` (float?) - Projected point on
  route
- `projected_longitude` (float?) - Projected point on
  route
- `projected_waypoint_index` (int?) - Index of closest
  route point
- `projected_route_progress` (float?) - Progress % where
  POI projects on route
- `route_aware_status` (string?) - `ahead_on_route`,
  `already_passed`, `not_on_route`, or `pre_departure`

**Status Codes:**

- `200 OK` - ETAs calculated
- `400 Bad Request` - Failed to calculate ETA
- `500 Internal Server Error` - POI manager not
  initialized

---

## Calculation Method

- **Distance:** Haversine formula (great-circle distance)
- **Bearing:** Inverse bearing calculation
- **ETA (estimated):** distance / (speed \* 0.51444) sec
- **ETA (anticipated):** Route-aware calculation using
  flight plan timing
- **Speed Default:** 67 knots (fallback if not available)

**Dual-mode ETA:** The endpoint supports two ETA modes
based on flight phase:

- **Anticipated** (pre-departure): ETAs based on flight
  plan schedule
- **Estimated** (in-flight): ETAs based on current
  telemetry speed/position

**Use Case:** Real-time navigation, POI tracking, mission
monitoring.

---

## Examples

### cURL Examples

**Get ETAs to All POIs:**

```bash
curl http://localhost:8000/api/pois/etas | jq .
```

**Get ETAs with Custom Location:**

```bash
curl "http://localhost:8000/api/pois/etas?\
latitude=40.7128&longitude=-74.0060&speed_knots=50" \
  | jq .
```

**Filter by Course Status:**

```bash
curl "http://localhost:8000/api/pois/etas?\
status_filter=on_course,slightly_off" | jq .
```

---

### Python Examples

```python
import requests

# Get ETAs to all POIs
response = requests.get(
    'http://localhost:8000/api/pois/etas'
)
data = response.json()

for poi in data['pois']:
    eta_minutes = poi['eta_seconds'] / 60
    distance_km = poi['distance_meters'] / 1000
    print(
        f"{poi['name']}: "
        f"{eta_minutes:.1f} min "
        f"({distance_km:.1f} km)"
    )

# Get ETAs with custom position
params = {
    'latitude': 40.7128,
    'longitude': -74.0060,
    'speed_knots': 50
}
response = requests.get(
    'http://localhost:8000/api/pois/etas',
    params=params
)
data = response.json()
```

---

[Back to API Reference](../README.md) |
[POI Index](./README.md)
