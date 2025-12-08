# API Reference Index

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0 **Base URL:**
`http://localhost:8000`

## Overview

Complete API reference for the Starlink Dashboard backend service. This index
provides quick navigation to all endpoint categories.

**Interactive Documentation:**

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

---

## Quick Start

1. **Check service health:** `GET /health`
2. **View current status:** `GET /api/status`
3. **Access Prometheus metrics:** `GET /metrics`
4. **Explore interactive docs:** `http://localhost:8000/docs`

---

## Endpoint Categories

### Core Endpoints

Health, status, and metrics endpoints.

**Document:** [Core Endpoints](./api/endpoints/core.md)

**Key Endpoints:**

- `GET /` - Welcome message
- `GET /health` - Service health check
- `GET /api/status` - Current telemetry status
- `GET /metrics` - Prometheus metrics
- `GET /api/metrics` - Metrics as JSON
- `GET /ui/pois` - POI management UI

---

### POI Management

Create, read, update, and delete Points of Interest with ETA calculations.

**Document:** [POI Endpoints](./api/endpoints/poi.md)

**Key Endpoints:**

- `GET /api/pois` - List all POIs
- `GET /api/pois/{poi_id}` - Get POI details
- `POST /api/pois` - Create POI
- `PUT /api/pois/{poi_id}` - Update POI
- `DELETE /api/pois/{poi_id}` - Delete POI
- `GET /api/pois/etas` - Calculate ETAs to all POIs
- `GET /api/pois/count/total` - Get POI count

---

### Route & Geography

Route history and GeoJSON export for map visualization.

**Document:** [Route Endpoints](./api/endpoints/routes.md)

**Key Endpoints:**

- `GET /route.geojson` - Route history as GeoJSON
- `GET /geojson` - Alias for route.geojson

---

### ETA Route Timing

Advanced route-based ETA calculations with timing profiles.

**Document:** [ETA Endpoints](./api/endpoints/eta.md)

**Key Endpoints:**

- `GET /api/routes/{route_id}/eta/waypoint/{waypoint_index}` - Waypoint ETA
- `GET /api/routes/{route_id}/eta/location` - Location ETA
- `GET /api/routes/{route_id}/progress` - Route progress
- `GET /api/routes/active/timing` - Active route timing
- `GET /api/routes/metrics/eta-cache` - Cache metrics
- `GET /api/routes/metrics/eta-accuracy` - Accuracy stats
- `POST /api/routes/cache/cleanup` - Clean cache
- `POST /api/routes/cache/clear` - Clear cache
- `POST /api/routes/live-mode/active-route-eta` - Live mode ETA

---

### Configuration

Service configuration management at runtime.

**Document:** [Configuration Endpoints](./api/endpoints/configuration.md)

**Key Endpoints:**

- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration (partial)
- `PUT /api/config` - Replace configuration (full)

---

## Usage Examples

Practical examples with cURL, Python, and JavaScript.

**Document:** [API Examples](./api/examples/README.md)

**Covers:**

- Health and status checks
- POI management operations
- ETA calculations
- Configuration updates
- Route monitoring
- [Error Handling](./api/errors.md) - Standard error responses, formats, and
  common error scenarios.

---

## Error Handling

Standard error response formats and common error scenarios.

**Document:** [Error Handling](./api/errors.md)

**HTTP Status Codes:**

- `200 OK` - Successful GET, POST, PUT
- `201 Created` - Resource created
- `204 No Content` - Empty response
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `409 Conflict` - Duplicate resource
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

---

## Data Models

Request and response data structures.

**Document:** [Data Models](./api/models/README.md)

**Covers:**

- Position data
- Network metrics
- POI structures
- Route data
- Configuration objects
- Error responses

---

## Quick Reference Tables

### Core Endpoints (Summary)

| Endpoint         | Method | Purpose            |
| ---------------- | ------ | ------------------ |
| `/`              | GET    | Welcome message    |
| `/health`        | GET    | Health check       |
| `/api/status`    | GET    | Current status     |
| `/metrics`       | GET    | Prometheus metrics |
| `/api/metrics`   | GET    | Metrics as JSON    |
| `/ui/pois`       | GET    | POI management UI  |
| `/route.geojson` | GET    | Route GeoJSON      |

### POI Endpoints

| Endpoint                | Method | Purpose        |
| ----------------------- | ------ | -------------- |
| `/api/pois`             | GET    | List POIs      |
| `/api/pois/{poi_id}`    | GET    | Get POI        |
| `/api/pois`             | POST   | Create POI     |
| `/api/pois/{poi_id}`    | PUT    | Update POI     |
| `/api/pois/{poi_id}`    | DELETE | Delete POI     |
| `/api/pois/etas`        | GET    | Calculate ETAs |
| `/api/pois/count/total` | GET    | Get POI count  |

### ETA Endpoints

| Endpoint                                 | Method | Purpose             |
| ---------------------------------------- | ------ | ------------------- |
| `/api/routes/{id}/eta/waypoint/{index}`  | GET    | Waypoint ETA        |
| `/api/routes/{id}/eta/location`          | GET    | Location ETA        |
| `/api/routes/{id}/progress`              | GET    | Route progress      |
| `/api/routes/active/timing`              | GET    | Active route timing |
| `/api/routes/metrics/eta-cache`          | GET    | Cache metrics       |
| `/api/routes/metrics/eta-accuracy`       | GET    | Accuracy stats      |
| `/api/routes/cache/cleanup`              | POST   | Clean cache         |
| `/api/routes/cache/clear`                | POST   | Clear cache         |
| `/api/routes/live-mode/active-route-eta` | POST   | Live ETA            |

### Configuration Endpoints

| Endpoint      | Method | Purpose               |
| ------------- | ------ | --------------------- |
| `/api/config` | GET    | Get configuration     |
| `/api/config` | POST   | Update configuration  |
| `/api/config` | PUT    | Replace configuration |

---

## Authentication & Security

**Current Version:** No authentication required (v0.3.0)

The API is designed for internal network use. For production deployments:

- Use reverse proxy with authentication (e.g., nginx with Basic Auth)
- Implement network-level security (firewall rules, VPN)
- Consider API keys for external access
- Enable HTTPS/TLS for encrypted communication

---

## Rate Limiting

**Current Version:** No rate limiting (v0.3.0)

For production deployments, consider implementing rate limiting at:

- Reverse proxy level (nginx, Caddy)
- Application level (FastAPI middleware)
- Infrastructure level (API Gateway)

---

## API Versioning

**Current Version:** 0.3.0

API versioning strategy:

- Major version in URL path (future: `/v1/api/...`)
- Backward compatibility within major versions
- Deprecation warnings for breaking changes
- Migration guides for major version upgrades

---

## Related Documentation

- [Backend README](../backend/starlink-location/README.md) - Service overview
- [CLAUDE.md](../CLAUDE.md) - Development configuration
- [Setup Guide](./setup/README.md) - Installation instructions
- [Metrics Reference](./metrics/overview.md) - Prometheus metrics details
- [Grafana Setup](./grafana-dashboards.md) - Dashboard configuration
- [Route Timing Guide](./route-timing-guide.md) - Route timing features

---

## Support & Feedback

- Interactive API docs: `http://localhost:8000/docs`
- OpenAPI specification: `http://localhost:8000/openapi.json`
- Service health: `http://localhost:8000/health`

---

**Last Updated:** 2025-11-04 **Status:** Complete with ETA Route Timing
endpoints
