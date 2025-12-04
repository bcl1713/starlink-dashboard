# Configuration Models

[Back to API Reference](../README.md) | [Models Index](./README.md)

---

## Configuration

Response from `/api/config` endpoint.

```json
{
  "mode": "simulation",
  "update_interval_seconds": 1.0,
  "route": {
    "pattern": "circular",
    "latitude_start": 40.7128,
    "longitude_start": -74.006,
    "radius_km": 100.0,
    "distance_km": 500.0
  },
  "network": {
    "latency_min_ms": 20.0,
    "latency_typical_ms": 50.0,
    "latency_max_ms": 80.0,
    "throughput_down_min_mbps": 50.0,
    "throughput_down_max_mbps": 200.0
  },
  "obstruction": {
    "min_percent": 0.0,
    "max_percent": 30.0,
    "variation_rate": 0.5
  }
}
```

**Top-Level Fields:**

- `mode`: "simulation" or "live"
- `update_interval_seconds`: How often metrics update

---

## Route Configuration

- `pattern`: "circular" or "straight"
- `latitude_start`: Starting latitude
- `longitude_start`: Starting longitude
- `radius_km`: Circular route radius
- `distance_km`: Straight route distance

---

## Network Configuration

- `latency_min_ms`: Minimum latency
- `latency_typical_ms`: Typical latency
- `latency_max_ms`: Maximum latency
- `throughput_down_min_mbps`: Minimum download speed
- `throughput_down_max_mbps`: Maximum download speed

---

## Obstruction Configuration

- `min_percent`: Minimum obstruction percentage
- `max_percent`: Maximum obstruction percentage
- `variation_rate`: How quickly obstruction changes

---

[Back to API Reference](../README.md) | [Models Index](./README.md)
