# Common Error Scenarios

[Back to API Reference](./README.md) | [Back to errors](./errors.md)

---

## Overview

Common error scenarios you may encounter when using the Starlink Dashboard API,
with examples and solutions.

---

## Invalid Coordinates

**Scenario:** Coordinates outside valid range.

**Request:**

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "latitude": 100, "longitude": -74.0}'
```

**Response (400 Bad Request):**

```json
{
  "detail": "Invalid latitude: must be between -90 and 90",
  "error_code": "INVALID_COORDINATES",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Ensure latitude is -90 to 90, longitude is -180 to 180.

---

## POI Not Found

**Scenario:** Attempting to access non-existent POI.

**Request:**

```bash
curl http://localhost:8000/api/pois/nonexistent-poi-id
```

**Response (404 Not Found):**

```json
{
  "detail": "POI 'nonexistent-poi-id' not found",
  "error_code": "POI_NOT_FOUND",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Verify POI ID exists by listing all POIs first.

---

## Duplicate POI Name

**Scenario:** Creating POI with name that already exists.

**Request:**

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{"name": "LaGuardia Airport", "latitude": 40.77, "longitude": -73.87}'
```

**Response (409 Conflict):**

```json
{
  "detail": "POI with name 'LaGuardia Airport' already exists",
  "error_code": "POI_NAME_CONFLICT",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Use a unique name or update the existing POI instead.

---

## Configuration Validation Error

**Scenario:** Invalid configuration values.

**Request:**

```bash
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"route": {"radius_km": -50}}'
```

**Response (422 Unprocessable Entity):**

```json
{
  "detail": "Configuration validation failed",
  "error_code": "VALIDATION_ERROR",
  "errors": [
    {
      "field": "route.radius_km",
      "message": "must be > 0"
    }
  ],
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Ensure all configuration values meet validation requirements.

---

## Route Not Found

**Scenario:** Attempting to access non-existent route.

**Request:**

```bash
curl http://localhost:8000/api/routes/nonexistent-route/progress
```

**Response (404 Not Found):**

```json
{
  "detail": "Route 'nonexistent-route' not found",
  "error_code": "ROUTE_NOT_FOUND",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Verify route ID exists or use the active route endpoint.

---

## No Active Route

**Scenario:** Requesting active route information when no route is active.

**Request:**

```bash
curl http://localhost:8000/api/routes/active/timing
```

**Response (404 Not Found):**

```json
{
  "detail": "No active route",
  "error_code": "NO_ACTIVE_ROUTE",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Activate a route first before accessing active route endpoints.

---

## Missing Required Parameter

**Scenario:** Required query parameter not provided.

**Request:**

```bash
curl "http://localhost:8000/api/routes/route-001/eta/location"
```

**Response (400 Bad Request):**

```json
{
  "detail": "Missing required parameter: target_lat",
  "error_code": "MISSING_PARAMETER",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Include all required parameters in the request.

---

## Invalid Speed Value

**Scenario:** Speed parameter out of valid range.

**Request:**

```bash
curl "http://localhost:8000/api/pois/etas?speed_knots=-50"
```

**Response (400 Bad Request):**

```json
{
  "detail": "Invalid speed: must be non-negative",
  "error_code": "INVALID_SPEED",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Ensure speed is >= 0.

---

## Service Unavailable

**Scenario:** Backend service experiencing issues.

**Request:**

```bash
curl http://localhost:8000/api/status
```

**Response (500 Internal Server Error):**

```json
{
  "detail": "Cannot retrieve status: simulation coordinator not initialized",
  "error_code": "SERVICE_ERROR",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fix:** Check service logs and ensure backend is properly initialized.

---

[Back to API Reference](./README.md) | [Back to errors](./errors.md)
