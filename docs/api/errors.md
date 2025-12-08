# API Error Handling

[Back to API Reference](./README.md) | [Back to main docs](../index.md)

---

## Overview

Complete guide to error handling in the Starlink Dashboard API.

**Related Documentation:**

- [Common Scenarios](./errors-scenarios.md) - Examples and solutions
- [Best Practices & Troubleshooting](./errors-handling.md) - Client code and
  debugging

---

## Error Response Format

All endpoints return errors in a consistent JSON format:

```json
{
  "detail": "Error description",
  "error_code": "INVALID_REQUEST",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fields:**

- `detail`: Human-readable error description
- `error_code`: Machine-readable error identifier (when available)
- `timestamp`: When the error occurred (ISO-8601)

---

## HTTP Status Codes

The API uses standard HTTP status codes to indicate success or failure.

### Success Codes (2xx)

| Code  | Name       | Description                              | Use Case                           |
| ----- | ---------- | ---------------------------------------- | ---------------------------------- |
| `200` | OK         | Request successful                       | GET, POST, PUT operations          |
| `201` | Created    | Resource created successfully            | POST operations                    |
| `204` | No Content | Request successful, no content to return | DELETE operations, empty responses |

### Client Error Codes (4xx)

| Code  | Name                 | Description                              | Use Case                                |
| ----- | -------------------- | ---------------------------------------- | --------------------------------------- |
| `400` | Bad Request          | Invalid input data or parameters         | Validation failures, malformed requests |
| `404` | Not Found            | Requested resource doesn't exist         | POI not found, route not found          |
| `409` | Conflict             | Resource conflict (e.g., duplicate name) | POI name already exists                 |
| `422` | Unprocessable Entity | Semantic validation error                | Invalid coordinate ranges, type errors  |

### Server Error Codes (5xx)

| Code  | Name                  | Description             | Use Case                              |
| ----- | --------------------- | ----------------------- | ------------------------------------- |
| `500` | Internal Server Error | Unexpected server error | System failures, unhandled exceptions |

---

## Error Codes by Category

Complete reference of all error codes used by the Starlink Dashboard API.

### Coordinate Errors

| Code                  | Description                     | HTTP Status |
| --------------------- | ------------------------------- | ----------- |
| `INVALID_COORDINATES` | Coordinates outside valid range | 400         |
| `INVALID_LATITUDE`    | Latitude not in -90 to 90       | 400         |
| `INVALID_LONGITUDE`   | Longitude not in -180 to 180    | 400         |

### POI Errors

| Code                  | Description            | HTTP Status |
| --------------------- | ---------------------- | ----------- |
| `POI_NOT_FOUND`       | POI doesn't exist      | 404         |
| `POI_NAME_CONFLICT`   | POI name already taken | 409         |
| `POI_CREATION_FAILED` | Failed to create POI   | 500         |
| `POI_UPDATE_FAILED`   | Failed to update POI   | 500         |
| `POI_DELETE_FAILED`   | Failed to delete POI   | 500         |

### Route Errors

| Code                | Description                     | HTTP Status |
| ------------------- | ------------------------------- | ----------- |
| `ROUTE_NOT_FOUND`   | Route doesn't exist             | 404         |
| `NO_ACTIVE_ROUTE`   | No route is currently active    | 404         |
| `ROUTE_LOAD_FAILED` | Failed to load route            | 500         |
| `NO_TIMING_DATA`    | Route has no timing information | 404         |

### Configuration Errors

| Code                    | Description                     | HTTP Status |
| ----------------------- | ------------------------------- | ----------- |
| `VALIDATION_ERROR`      | Configuration validation failed | 422         |
| `INVALID_CONFIGURATION` | Configuration format invalid    | 400         |
| `CONFIG_UPDATE_FAILED`  | Failed to update configuration  | 500         |

### Request Errors

| Code                | Description                | HTTP Status |
| ------------------- | -------------------------- | ----------- |
| `INVALID_REQUEST`   | Malformed request          | 400         |
| `MISSING_PARAMETER` | Required parameter missing | 400         |
| `INVALID_PARAMETER` | Parameter value invalid    | 400         |
| `INVALID_SPEED`     | Speed value out of range   | 400         |

### Service Errors

| Code                   | Description                      | HTTP Status |
| ---------------------- | -------------------------------- | ----------- |
| `SERVICE_ERROR`        | General service error            | 500         |
| `INITIALIZATION_ERROR` | Service not properly initialized | 500         |
| `CALCULATION_ERROR`    | Calculation failed               | 500         |

---

[Back to API Reference](./README.md) | [Back to main docs](../index.md)
