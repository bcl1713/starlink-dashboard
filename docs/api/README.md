# Starlink Dashboard API Reference

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0 **Base URL:**
`<http://localhost:8000`> **Status:** Complete with ETA Route Timing endpoints

[Back to main docs](../INDEX.md)

---

## Overview

The Starlink Dashboard backend provides a comprehensive REST API for:

- Health monitoring and service status
- Real-time telemetry metrics (Prometheus-compatible)
- Configuration management
- POI (Points of Interest) management
- Route and geographic data
- ETA calculations and route timing
- Mission planning and visualization

All endpoints return JSON unless otherwise specified (except `/metrics` which
returns Prometheus text format).

---

## Quick Links

- **[Endpoints](./endpoints.md)** - Complete endpoint reference
- **[Models](./models.md)** - Request/response data models
- **[Errors](./errors.md)** - Error codes and handling

---

## Documentation Structure

This API documentation is organized into three main sections:

### 1. Endpoints Reference

Complete listing of all available endpoints with:

- Request methods and paths
- Query parameters
- Request/response examples
- Status codes
- Use cases

**[View Endpoints →](./endpoints.md)**

### 2. Data Models

Detailed documentation of request and response structures:

- POI models
- Route models
- ETA calculation models
- Configuration models
- Health check models

**[View Models →](./models.md)**

### 3. Error Handling

Comprehensive error documentation:

- Error response format
- HTTP status codes
- Common error scenarios
- Troubleshooting guides

**[View Error Handling →](./errors.md)**

---

## Getting Started

### Quick Test

Verify the backend is running:

```bash
curl <http://localhost:8000/health>
```

### Interactive Documentation

For live API exploration:

- **Swagger UI:** `<http://localhost:8000/docs`>
- **ReDoc:** `<http://localhost:8000/redoc`>

These provide:

- Live endpoint testing
- Request/response examples
- Schema validation
- Parameter documentation

### Base Configuration

Default service ports:

- Backend API: `8000`
- Prometheus: `9090`
- Grafana: `3000`

These can be changed in `.env` file.

---

## Authentication

Currently, no authentication is required for local development. For production
deployments, implement authentication at the reverse proxy level.

---

## Rate Limiting

No rate limiting is currently implemented. The service is designed for internal
use on trusted networks.

---

## API Versioning

The API currently uses implicit versioning. Breaking changes will be
communicated via version updates in this documentation.

---

## Common Patterns

### Timestamps

All timestamps use ISO-8601 format in UTC:

```text
2025-10-31T10:30:00.000000
```

### Coordinates

Geographic coordinates use decimal degrees:

- Latitude: -90 to 90 (negative = South)
- Longitude: -180 to 180 (negative = West)
- Altitude: Meters above sea level

### Distance Units

- Distances: meters
- Speed: knots
- Altitude: meters

### HTTP Methods

- `GET` - Retrieve data
- `POST` - Create or trigger actions
- `PUT` - Replace entire resource
- `DELETE` - Remove resource

---

## Related Documentation

- [CLAUDE.md](/CLAUDE.md) - Development configuration
- [SETUP-GUIDE](../setup/README.md) - Installation and setup
- [METRICS](../METRICS.md) - Prometheus metrics reference
- [Backend README](../../backend/starlink-location/README.md) - Service details

---

**Need Help?** Check the [Troubleshooting Guide](../troubleshooting/README.md)
or review the interactive documentation at `/docs`.
