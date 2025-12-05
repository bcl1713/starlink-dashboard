# POI Management API Endpoints

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Reorganization Notice

This document has been reorganized into operation-focused files for better
navigation and maintainability.

**Please visit the [POI Index](./poi/README.md) to access all POI endpoint
documentation.**

---

## Quick Links

- **[POI Index](./poi/README.md)** - Complete POI endpoint overview
- [List & Query Endpoints](./poi/list-query-endpoints.md) - List and retrieve
  POIs
- [ETA Endpoints](./poi/eta-endpoints.md) - Calculate ETAs to POIs
- [Management Endpoints](./poi/management-endpoints.md) - Create, update, delete

---

## Quick Examples

### List All POIs

```bash
curl http://localhost:8000/api/pois | jq .
```

### Create a POI

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654,
    "description": "NYC Central Park"
  }'
```

### Get ETAs

```bash
curl http://localhost:8000/api/pois/etas | jq .
```

---

## Related Documentation

- [API Reference Index](./README.md) - Complete API overview
- [Core Endpoints](./core.md) - Health and metrics
- [ETA Endpoints](./eta.md) - Route-based ETA calculations
- [Error Handling](../errors.md) - Error response formats

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
