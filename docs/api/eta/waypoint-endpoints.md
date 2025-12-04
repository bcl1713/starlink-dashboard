# Waypoint ETA Endpoints

[Back to API Reference](../README.md) | [ETA Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## GET `/api/routes/{route_id}/eta/waypoint/{waypoint_index}`

Calculate ETA to a specific waypoint on the active route.

**Description:** Returns estimated time to arrive at a waypoint, considering
current position and available timing data.

**Parameters:**

- `route_id` (path, required): Route identifier
- `waypoint_index` (path, required): Index of waypoint (0-based)
- `current_position_lat` (query, optional): Current latitude
- `current_position_lon` (query, optional): Current longitude

**Response:**

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

**Status Codes:**

- `200 OK` - ETA calculated
- `400 Bad Request` - Invalid parameters
- `404 Not Found` - Route not found

**Use Case:** Real-time waypoint ETAs, flight plan tracking, progress
monitoring.

---

## GET `/api/routes/{route_id}/eta/location`

Calculate ETA to an arbitrary geographic location.

**Description:** Returns estimated time to reach any specified coordinate,
supporting routes with or without timing data.

**Parameters:**

- `route_id` (path, required): Route identifier
- `target_lat` (query, required): Target latitude
- `target_lon` (query, required): Target longitude
- `current_position_lat` (query, optional): Current latitude
- `current_position_lon` (query, optional): Current longitude

**Response:**

```json
{
  "target_location": { "latitude": 40.7128, "longitude": -74.006 },
  "eta_seconds": 1800,
  "eta_minutes": 30.0,
  "distance_meters": 75000,
  "distance_km": 75.0,
  "estimated_speed_knots": 150.0,
  "route_id": "route-001"
}
```

**Status Codes:**

- `200 OK` - ETA calculated
- `400 Bad Request` - Invalid coordinates
- `404 Not Found` - Route not found

**Use Case:** POI arrival predictions, arbitrary destination ETAs, navigation
planning.

---

## Examples

### cURL Examples

**Get Waypoint ETA:**

```bash
curl "http://localhost:8000/api/routes/route-001/eta/waypoint/5?current_position_lat=40.7128&current_position_lon=-74.006"
```

**Get Location ETA:**

```bash
curl "http://localhost:8000/api/routes/route-001/eta/location?target_lat=40.7769&target_lon=-73.874"
```

### Python Examples

```python
import requests

# Get waypoint ETA
params = {
    'current_position_lat': 40.7128,
    'current_position_lon': -74.006
}
response = requests.get(
    'http://localhost:8000/api/routes/route-001/eta/waypoint/5',
    params=params
)
eta = response.json()
print(f"ETA to waypoint: {eta['eta_minutes']} minutes")
```

---

[Back to API Reference](../README.md) | [ETA Index](./README.md)
