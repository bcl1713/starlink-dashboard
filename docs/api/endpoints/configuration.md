# Configuration API Endpoints

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

## Overview

Endpoints for retrieving and updating service configuration at runtime.

**Related Documentation:**

- [Core Endpoints](./core.md) - Health and metrics
- [POI Endpoints](./poi.md) - POI management
- [Setup Guide](../../setup/configuration.md) - Configuration details

---

## Configuration Endpoints

### GET `/api/config`

Retrieve current service configuration.

**Response:**

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

**Status Codes:**

- `200 OK` - Configuration retrieved

**Use Case:** Configuration verification, admin dashboards.

---

### POST `/api/config`

Update service configuration at runtime.

**Request Body:**

```json
{
  "route": {
    "pattern": "straight",
    "radius_km": 150.0
  },
  "network": {
    "latency_max_ms": 100.0
  }
}
```

**Response:** Updated configuration (same as GET)

**Status Codes:**

- `200 OK` - Configuration updated
- `400 Bad Request` - Invalid configuration
- `422 Unprocessable Entity` - Validation error

**Use Case:** Runtime configuration adjustment, testing different parameters.

---

### PUT `/api/config`

Replace entire service configuration.

**Request Body:** Complete configuration object (same structure as GET response)

**Response:** Updated configuration

**Status Codes:**

- `200 OK` - Configuration replaced
- `400 Bad Request` - Invalid configuration
- `422 Unprocessable Entity` - Validation error

**Use Case:** Full configuration reset, environment-specific setup.

---

## Configuration Structure

### Route Configuration

Controls the simulation route pattern:

- `pattern` (string): "circular", "straight", or "figure8"
- `latitude_start` (float): Starting latitude
- `longitude_start` (float): Starting longitude
- `radius_km` (float): Route radius for circular patterns
- `distance_km` (float): Total route distance

### Network Configuration

Controls network performance simulation:

- `latency_min_ms` (float): Minimum latency (best case)
- `latency_typical_ms` (float): Typical latency
- `latency_max_ms` (float): Maximum latency (worst case)
- `throughput_down_min_mbps` (float): Minimum download throughput
- `throughput_down_max_mbps` (float): Maximum download throughput
- `throughput_up_min_mbps` (float): Minimum upload throughput
- `throughput_up_max_mbps` (float): Maximum upload throughput

### Obstruction Configuration

Controls obstruction simulation:

- `min_percent` (float): Minimum obstruction percentage
- `max_percent` (float): Maximum obstruction percentage
- `variation_rate` (float): Rate of obstruction changes

---

## Examples

### cURL Examples

**Get Current Configuration:**

```bash
curl http://localhost:8000/api/config | jq .
```

**Update Configuration (Partial):**

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "route": {"pattern": "straight"}
  }'
```

**Replace Configuration (Full):**

```bash
curl -X PUT http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
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
  }'
```

### Python Examples

```python
import requests

# Get current configuration
response = requests.get('http://localhost:8000/api/config')
config = response.json()
print(f"Current mode: {config['mode']}")

# Update configuration
update = {
    "route": {"pattern": "straight", "radius_km": 150.0}
}
response = requests.post('http://localhost:8000/api/config', json=update)
new_config = response.json()
print(f"Updated pattern: {new_config['route']['pattern']}")
```

---

## Configuration Validation

The API validates all configuration updates to ensure:

- Values are within acceptable ranges
- Required fields are present
- Data types are correct
- Relationships between fields are valid

**Example Validation Error:**

```json
{
  "detail": "Configuration validation failed",
  "error_code": "VALIDATION_ERROR",
  "errors": [{ "field": "route.radius_km", "message": "must be > 0" }]
}
```

---

## Related Documentation

- [API Reference Index](../README.md) - Complete API overview
- [Core Endpoints](./core.md) - Health and metrics
- [Setup Guide](../../setup/configuration.md) - Environment configuration
- [Error Handling](../errors.md) - Error response formats
