# Starlink Dashboard API Reference

**Purpose**: Technical reference for REST API endpoints, models, and contracts
**Audience**: API consumers, integrators, developers

[Back to main docs](../index.md)

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

## Quick Navigation

- **[Endpoints](./endpoints/README.md)** - Complete endpoint reference by
  category
- **[Models & Schemas](./models/README.md)** - Request/response data structures
- **[Code Examples](./examples/README.md)** - cURL, Python, JavaScript examples
- **[Error Reference](./errors.md)** - Error codes and handling

---

## Documentation Structure

This API documentation is organized by functional area:

### 1. Endpoints by Category

**[View All Endpoints →](./endpoints/README.md)**

- **[Core Endpoints](./endpoints/core.md)** - Health, status, metrics
- **[Configuration](./endpoints/configuration.md)** - System configuration
- **[POI Management](./endpoints/poi.md)** - Points of Interest
- **[Routes](./endpoints/routes.md)** - Route management
- **[ETA Calculations](./endpoints/eta.md)** - Estimated time of arrival

### 2. Data Models & Schemas

**[View All Models →](./models/README.md)**

- Request/response structures
- Validation rules
- Type definitions
- Example payloads

### 3. Code Examples

**[View All Examples →](./examples/README.md)**

- **[cURL Examples](./examples/curl-examples.md)** - Command-line usage
- **[Python Examples](./examples/python-examples.md)** - Python integration
- **[JavaScript Examples](./examples/javascript-examples.md)** - Web/Node.js
  usage

### 4. Error Handling

**[View Error Reference →](./errors.md)**

- Error response format
- HTTP status codes
- Common scenarios
- Troubleshooting

---

## Adding New API Documentation

**For Contributors:** When adding or updating API endpoints:

### 1. Document the Endpoint

Add to appropriate file in **[endpoints/](./endpoints/)**:

- **Core/health endpoints** → `endpoints/core.md`
- **Configuration** → `endpoints/configuration.md`
- **POI management** → `endpoints/poi.md`
- **Routes** → `endpoints/routes.md`
- **ETA calculations** → `endpoints/eta.md`

Include:

- Endpoint path and HTTP method
- Request parameters (query, path, body)
- Request example (cURL, Python)
- Response example (JSON)
- Possible error codes

### 2. Document Data Models

Add to appropriate file in **[models/](./models/)**:

- Model name and purpose
- Field definitions with types
- Validation rules
- Example JSON

### 3. Add Code Examples

Update **[examples/](./examples/)** with usage examples:

- cURL examples for testing
- Python examples for integration
- JavaScript examples for web apps

### 4. Document Errors

Add new error codes to **[errors.md](./errors.md)**

### 5. Update Indexes

- Update category README in `endpoints/`, `models/`, or `examples/`
- Update this README if creating new category

---

## Getting Started with the API

### 1. Verify Service is Running

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "mode": "simulation",
  "dish_connected": true
}
```

### 2. Explore Interactive Documentation

The API provides auto-generated interactive documentation:

- **Swagger UI:** <http://localhost:8000/docs>
- **ReDoc:** <http://localhost:8000/redoc>

These interfaces provide:

- Live endpoint testing (try requests directly)
- Request/response examples
- Schema validation
- Parameter documentation

### 3. Try a Simple Request

Get current telemetry status:

```bash
curl http://localhost:8000/api/status | jq .
```

### 4. Common Workflows

- **POI Management:** See [POI Endpoints](./endpoints/poi.md)
- **ETA Calculations:** See [ETA Endpoints](./endpoints/eta.md)
- **Configuration:** See [Configuration Endpoints](./endpoints/configuration.md)

### Base Configuration

Default service ports:

- Backend API: `8000`
- Prometheus: `9090`
- Grafana: `3000`

Change in `.env` file if needed.

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

- [Development Guidelines](../../CLAUDE.md) - Coding standards
- [SETUP-GUIDE](../setup/README.md) - Installation and setup
- [METRICS](../metrics/overview.md) - Prometheus metrics reference
- [Backend README](../../backend/starlink-location/README.md) - Service details

---

**Need Help?** Check the [Troubleshooting Guide](../troubleshooting/README.md)
or review the interactive documentation at `/docs`.
