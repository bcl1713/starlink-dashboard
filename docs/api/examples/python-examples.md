# API Python Examples

[Back to API Reference](../README.md) | [Examples Index](./README.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Basic Usage

```python
import requests
import json

BASE_URL = 'http://localhost:8000'

# Get service health
response = requests.get(f'{BASE_URL}/health')
health = response.json()
print(f"Service status: {health['status']}")
print(f"Uptime: {health['uptime_seconds']} seconds")

# Get current status
response = requests.get(f'{BASE_URL}/api/status')
status = response.json()
print(f"Position: {status['position']['latitude']}, {status['position']['longitude']}")
print(f"Latency: {status['network']['latency_ms']} ms")
```

---

## POI Management

```python
import requests

BASE_URL = 'http://localhost:8000'

# List all POIs
response = requests.get(f'{BASE_URL}/api/pois')
pois = response.json()
print(f"Total POIs: {len(pois)}")

# Create a new POI
poi_data = {
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654,
    "description": "NYC Central Park"
}
response = requests.post(f'{BASE_URL}/api/pois', json=poi_data)
if response.status_code == 201:
    poi = response.json()
    print(f"Created POI: {poi['id']}")
else:
    print(f"Error: {response.json()}")

# Update POI
update_data = {
    "name": "Central Park (Updated)",
    "description": "NYC Central Park - Updated description"
}
response = requests.put(f'{BASE_URL}/api/pois/{poi["id"]}', json=update_data)
updated_poi = response.json()
print(f"Updated: {updated_poi['name']}")

# Delete POI
response = requests.delete(f'{BASE_URL}/api/pois/{poi["id"]}')
result = response.json()
print(f"Deleted: {result['message']}")
```

---

## ETA Calculations

```python
import requests

BASE_URL = 'http://localhost:8000'

# Get ETAs to all POIs
response = requests.get(f'{BASE_URL}/api/pois/etas')
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
response = requests.get(f'{BASE_URL}/api/pois/etas', params=params)
custom_etas = response.json()
```

---

## Route Progress Monitoring

```python
import requests
import time

BASE_URL = 'http://localhost:8000'
route_id = 'route-001'

def monitor_progress():
    while True:
        response = requests.get(f'{BASE_URL}/api/routes/{route_id}/progress')
        progress = response.json()

        print(f"Progress: {progress['progress_percent']:.1f}%")
        print(f"Waypoint: {progress['current_waypoint_index']}/{progress['total_waypoints']}")
        print(f"Distance remaining: {progress['distance_remaining_meters']/1000:.1f} km")
        print(f"ETA: {progress['eta_to_destination_seconds']/60:.1f} minutes")
        print("-" * 40)

        time.sleep(10)  # Update every 10 seconds

# Start monitoring
monitor_progress()
```

---

## Configuration Management

```python
import requests

BASE_URL = 'http://localhost:8000'

# Get current configuration
response = requests.get(f'{BASE_URL}/api/config')
config = response.json()
print(f"Current mode: {config['mode']}")
print(f"Route pattern: {config['route']['pattern']}")

# Update configuration
update = {
    "route": {
        "pattern": "straight",
        "radius_km": 150.0
    },
    "network": {
        "latency_max_ms": 100.0
    }
}
response = requests.post(f'{BASE_URL}/api/config', json=update)
new_config = response.json()
print(f"Updated pattern: {new_config['route']['pattern']}")
```

---

## Error Handling

```python
import requests

BASE_URL = 'http://localhost:8000'

def create_poi_safe(poi_data):
    try:
        response = requests.post(f'{BASE_URL}/api/pois', json=poi_data)
        response.raise_for_status()  # Raise exception for 4xx/5xx
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 409:
            print(f"POI already exists: {e.response.json()}")
        elif e.response.status_code == 400:
            print(f"Invalid data: {e.response.json()}")
        else:
            print(f"HTTP error: {e}")
    except requests.exceptions.ConnectionError:
        print("Cannot connect to service")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None
```

---

[Back to API Reference](../README.md) | [Examples Index](./README.md)
