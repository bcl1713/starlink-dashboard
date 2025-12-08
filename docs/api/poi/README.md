# POI Management API Index

[Back to API Reference](../README.md) | [Back to main docs](../../index.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Overview

POI (Point of Interest) management endpoints for creating, reading, updating,
and deleting geographic points and calculating ETAs.

---

## Endpoint Categories

### [List & Query Endpoints](./list-query-endpoints.md)

Retrieve POI information:

- `/api/pois` - List all POIs
- `/api/pois/count/total` - Get POI count
- `/api/pois/{poi_id}` - Get specific POI

**Use cases:** POI display, dashboard queries, detail views

---

### [ETA Endpoints](./eta-endpoints.md)

Calculate ETAs to POIs:

- `/api/pois/etas` - Real-time ETA to all POIs

**Use cases:** Navigation, real-time ETA updates, route planning

**Calculation:** Haversine distance formula with speed-based ETA

---

### [Management Endpoints](./management-endpoints.md)

Create, update, and delete POIs:

- `POST /api/pois` - Create new POI
- `PUT /api/pois/{poi_id}` - Update POI
- `DELETE /api/pois/{poi_id}` - Delete POI

**Use cases:** POI editing, form submissions, configuration management

---

## Quick Examples

### List POIs (cURL)

```bash
curl http://localhost:8000/api/pois | jq .
```

### Create POI (Python)

```python
import requests

poi_data = {
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654
}
response = requests.post('http://localhost:8000/api/pois', json=poi_data)
```

### Get ETAs (JavaScript)

```javascript
const response = await fetch("http://localhost:8000/api/pois/etas");
const etas = await response.json();
```

---

## Related Documentation

- [API Reference Index](../README.md) - Complete API overview
- [Core Endpoints](../endpoints/core.md) - Health and metrics
- [ETA Endpoints](../endpoints/eta.md) - Route-based ETA calculations
- [Error Handling](../errors.md) - Error response formats

---

[Back to API Reference](../README.md) | [Back to main docs](../../index.md)
