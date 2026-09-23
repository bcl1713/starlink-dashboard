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

`is_active` is returned server-managed lifecycle state on all other V2 writes.
Mission creation, adding a leg, and package import accept legacy omitted or
explicit flag values but persist every incoming leg inactive. A full `PUT`
may update ordinary active-leg fields, but it preserves that leg's persisted
route binding and active state; deactivate, replace the route, then activate
again to change an active leg's route. Re-importing an existing mission with
an active leg returns 409; deactivate it first. Deleting an active leg or a
mission containing an active leg also returns 409: deactivate first, then
repeat the deletion.

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
