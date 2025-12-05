# Core API Endpoints

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0 **Base URL:**
`http://localhost:8000`

## Overview

This document covers the core endpoints for service health, status, and metrics.

**Related Documentation:**

- [POI Endpoints](./poi.md) - POI management
- [Route Endpoints](./routes.md) - Route and geography
- [ETA Endpoints](./eta.md) - ETA calculations
- [Configuration Endpoints](./configuration.md) - Service
  configuration

---

## Root Endpoint

### GET `/`

Returns welcome message and API documentation links.

**Response:**

```json
{
  "message": "Welcome to Starlink Location Backend",
  "documentation": "API documentation available at /docs",
  "mode": "simulation",
  "version": "0.2.0"
}
```

**Status Code:** `200 OK`

---

## Health & Status Endpoints

### GET `/health`

Health check endpoint for service availability monitoring.

**Description:** Returns service status, uptime, mode information, and dish
connection status.

**Response:**

```json
{
  "status": "ok",
  "uptime_seconds": 3600.5,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2025-10-31T10:30:00.000000",
  "message": "Service is healthy",
  "dish_connected": true
}
```

**Status Codes:**

- `200 OK` - Service is healthy
- `500 Internal Server Error` - Service error

**Use Case:** Docker health checks, load balancer monitoring, uptime
verification.

---

### GET `/api/status`

Current telemetry status in human-readable JSON format.

**Description:** Returns comprehensive current state of position, network, and
environmental metrics.

**Response:**

```json
{
  "timestamp": "2025-10-31T10:30:00.000000",
  "position": {
    "latitude": 40.7128,
    "longitude": -74.006,
    "altitude": 5000.0,
    "speed": 25.5,
    "heading": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5,
    "temperature_celsius": null
  }
}
```

**Status Codes:**

- `200 OK` - Current status available
- `500 Internal Server Error` - Cannot retrieve status

**Use Case:** Dashboard panels, status monitoring, API clients.

---

## Metrics Endpoints

### GET `/metrics`

Prometheus metrics in standard text format (OpenMetrics 1.0.0).

**Description:** Exports all metrics in Prometheus-compatible format. Compatible
with Prometheus scraper configuration.

**Response:** Text format (sample):

```text
# HELP starlink_dish_latitude_degrees Dish latitude in decimal degrees
# TYPE starlink_dish_latitude_degrees gauge
starlink_dish_latitude_degrees 40.7128

# HELP starlink_dish_longitude_degrees Dish longitude in decimal degrees
# TYPE starlink_dish_longitude_degrees gauge
starlink_dish_longitude_degrees -74.006

# HELP starlink_network_latency_ms Network round-trip latency
# TYPE starlink_network_latency_ms gauge
starlink_network_latency_ms 45.2

# ... (45+ metrics total)
```

**Status Codes:**

- `200 OK` - Metrics available
- `500 Internal Server Error` - Cannot generate metrics

**Configuration:**

- Scrape interval: 1 second (backend update)
- Prometheus interval: 10 seconds (by default)

**Use Case:** Prometheus scraping, time-series database collection.

---

### GET `/api/metrics`

Raw metrics data as JSON (alternative to Prometheus format).

**Response:**

```json
{
  "position": {
    "latitude_degrees": 40.7128,
    "longitude_degrees": -74.006,
    "altitude_meters": 5000.0,
    "speed_knots": 25.5,
    "heading_degrees": 45.0
  },
  "network": {
    "latency_ms": 45.2,
    "throughput_down_mbps": 125.3,
    "throughput_up_mbps": 25.1,
    "packet_loss_percent": 0.5
  },
  "obstruction": {
    "obstruction_percent": 15.0
  },
  "environmental": {
    "signal_quality_percent": 85.0,
    "uptime_seconds": 3600.5
  }
}
```

**Status Codes:**

- `200 OK` - Metrics available

**Use Case:** JSON API clients, custom integrations.

---

## UI Endpoints

### GET `/ui/pois`

POI management web interface.

**Description:** Returns a complete HTML page with interactive POI management
UI, including:

- Interactive map for click-to-place coordinates
- POI creation/editing/deletion form
- Real-time POI list with live ETAs
- Responsive design suitable for Grafana HTML panel

**Response:** HTML/CSS/JavaScript interface

**Status Codes:**

- `200 OK` - UI page loaded

**Use Case:** Grafana HTML text panel, standalone POI management.

---

## Interactive Documentation

For interactive API exploration, visit:

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

These provide:

- Live endpoint testing
- Request/response examples
- Schema validation
- Parameter documentation

---

## Related Documentation

- [API Reference Index](../README.md) - Complete API overview
- [POI Endpoints](./poi.md) - POI management
- [Route Endpoints](./routes.md) - Route and geography
- [ETA Endpoints](./eta.md) - ETA calculations
- [Configuration Endpoints](./configuration.md) - Service
  configuration
- [Error Handling](../errors.md) - Error response formats
