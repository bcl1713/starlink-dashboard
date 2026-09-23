# API Endpoints

**Purpose**: Technical reference for REST API endpoints **Audience**: API
consumers, integrators, developers

[Back to API documentation](../README.md)

---

## Endpoint Categories

### Core System Endpoints

- **[Core Endpoints](./core.md)** - Health, status, and system endpoints
- **[Configuration Endpoints](./configuration.md)** - System configuration and
  settings
- **[Overview Clock Settings](./overview-clock-settings.md)** - Persistent
  dashboard clocks and Mission V2 lifecycle behavior
- **[Overview Upcoming POIs](./overview-upcoming-pois.md)** - Active-route
  generated POI projection, timing provenance, retention, and Top 5 queue

### Mission V2 activation

`/api/missions` has been removed and now returns 404. There are no supported
operator or API commands under that retired path. The sole supported activation
operation is `POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate`.

### Feature Endpoints

- **[ETA Endpoints](./eta.md)** - Estimated time of arrival calculations
- **[POI Endpoints](./poi.md)** - Point of interest management
- **[Route Endpoints](./routes.md)** - Route management and tracking
- **[Timeline Preview](./timeline-preview.md)** - Real-time mission leg preview
- **[Additional Endpoints](./additional.md)** - Flight status, GPS, CSV export,
  POI stats, GeoJSON variants, position table

---

## Quick Reference

All endpoints are documented with:

- **Path and method**: HTTP method and URL path
- **Parameters**: Query parameters, path parameters, request body
- **Response format**: Expected response schema and status codes
- **Examples**: Sample requests and responses
- **Error handling**: Possible error conditions

---

## Related Documentation

- [Models & Schemas](../models/README.md) - Data structure definitions
- [Code Examples](../examples/README.md) - Language-specific usage examples -See
  [Error Reference](../errors.md) for standard error responses. and handling

---

[Back to API documentation](../README.md)
