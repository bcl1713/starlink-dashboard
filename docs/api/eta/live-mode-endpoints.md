# Live Mode ETA Endpoints

[Back to API Reference](../README.md) | [ETA Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## POST `/api/routes/live-mode/active-route-eta`

Get ETA for active route using real-time position (live mode).

**Description:** Calculates ETA for the active route based on a real-time
position update, ideal for Starlink terminal position feeds.

**Parameters (JSON Body):**

```json
{
  "latitude": 40.7128,
  "longitude": -74.006,
  "altitude": 5000.0,
  "timestamp": "2025-11-04T10:30:00Z"
}
```

**Response:**

```json
{
  "current_position": { "latitude": 40.7128, "longitude": -74.006 },
  "route_progress": {
    "progress_percent": 45.5,
    "waypoints_remaining": 20,
    "distance_remaining_km": 75.0
  },
  "next_waypoint": {
    "index": 15,
    "name": "Waypoint 15",
    "eta_seconds": 1800,
    "distance_meters": 75000
  },
  "timing_profile": {
    "departure_time": "2025-10-27T16:45:00Z",
    "arrival_time": "2025-10-27T18:30:00Z"
  }
}
```

**Status Codes:**

- `200 OK` - ETA calculated
- `400 Bad Request` - Invalid position data
- `404 Not Found` - No active route

**Use Case:** Live aircraft tracking, real-time ETA updates, Starlink
integration.

---

## Examples

### cURL Example

```bash
curl -X POST http://localhost:8000/api/routes/live-mode/active-route-eta \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": 40.7128,
    "longitude": -74.006,
    "altitude": 5000.0,
    "timestamp": "2025-11-04T10:30:00Z"
  }' | jq .
```

### Python Example

```python
import requests
from datetime import datetime

# Real-time position update
position = {
    "latitude": 40.7128,
    "longitude": -74.006,
    "altitude": 5000.0,
    "timestamp": datetime.utcnow().isoformat() + "Z"
}

response = requests.post(
    'http://localhost:8000/api/routes/live-mode/active-route-eta',
    json=position
)

eta_data = response.json()
print(f"Progress: {eta_data['route_progress']['progress_percent']}%")
print(f"Next waypoint ETA: {eta_data['next_waypoint']['eta_seconds']} seconds")
```

---

[Back to API Reference](../README.md) | [ETA Index](./README.md)
