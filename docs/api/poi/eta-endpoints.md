# POI ETA Endpoints

[Back to API Reference](../README.md) | [POI Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## GET `/api/pois/etas`

Calculate real-time ETA to all POIs.

**Query Parameters:**

- `latitude` (float, optional) - Current latitude (default: from telemetry)
- `longitude` (float, optional) - Current longitude (default: from telemetry)
- `speed_knots` (float, optional) - Current speed (default: from telemetry)

**Response:**

```json
[
  {
    "poi_id": "poi-1",
    "name": "LaGuardia Airport",
    "latitude": 40.7769,
    "longitude": -73.874,
    "distance_meters": 8500,
    "eta_seconds": 2640,
    "bearing_degrees": 45.5,
    "calculated_at": "2025-10-31T10:30:00.000000"
  },
  {
    "poi_id": "poi-2",
    "name": "Newark Airport",
    "distance_meters": 12000,
    "eta_seconds": 3720
  }
]
```

**Status Codes:**

- `200 OK` - ETAs calculated
- `400 Bad Request` - Invalid coordinates/speed
- `500 Internal Server Error` - Calculation error

---

## Calculation Method

- **Distance:** Haversine formula (great-circle distance)
- **Bearing:** Inverse bearing calculation
- **ETA:** distance_meters / (speed_knots \* 0.51444) seconds
- **Speed Default:** 67 knots (fallback if not available)

**Use Case:** Grafana ETA tooltips, real-time navigation.

---

## Examples

### cURL Examples

**Get ETAs to All POIs:**

```bash
curl http://localhost:8000/api/pois/etas | jq .
```

**Get ETAs with Custom Location:**

```bash
curl "http://localhost:8000/api/pois/etas?latitude=40.7128&longitude=-74.0060&speed_knots=50" | jq .
```

---

### Python Examples

```python
import requests

# Get ETAs to all POIs
response = requests.get('http://localhost:8000/api/pois/etas')
etas = response.json()

for poi in etas:
    eta_minutes = poi['eta_seconds'] / 60
    distance_km = poi['distance_meters'] / 1000
    print(f"{poi['name']}: {eta_minutes:.1f} min ({distance_km:.1f} km)")

# Get ETAs with custom position
params = {
    'latitude': 40.7128,
    'longitude': -74.0060,
    'speed_knots': 50
}
response = requests.get('http://localhost:8000/api/pois/etas', params=params)
custom_etas = response.json()
```

---

[Back to API Reference](../README.md) | [POI Index](./README.md)
