# API Error Codes Reference

[Back to API Reference](./README.md) | [Back to errors](./errors.md)

---

## Error Codes by Category

Complete reference of all error codes used by the Starlink Dashboard API.

---

## Coordinate Errors

| Code                  | Description                     | HTTP Status |
| --------------------- | ------------------------------- | ----------- |
| `INVALID_COORDINATES` | Coordinates outside valid range | 400         |
| `INVALID_LATITUDE`    | Latitude not in -90 to 90       | 400         |
| `INVALID_LONGITUDE`   | Longitude not in -180 to 180    | 400         |

---

## POI Errors

| Code                  | Description            | HTTP Status |
| --------------------- | ---------------------- | ----------- |
| `POI_NOT_FOUND`       | POI doesn't exist      | 404         |
| `POI_NAME_CONFLICT`   | POI name already taken | 409         |
| `POI_CREATION_FAILED` | Failed to create POI   | 500         |
| `POI_UPDATE_FAILED`   | Failed to update POI   | 500         |
| `POI_DELETE_FAILED`   | Failed to delete POI   | 500         |

---

## Route Errors

| Code                | Description                     | HTTP Status |
| ------------------- | ------------------------------- | ----------- |
| `ROUTE_NOT_FOUND`   | Route doesn't exist             | 404         |
| `NO_ACTIVE_ROUTE`   | No route is currently active    | 404         |
| `ROUTE_LOAD_FAILED` | Failed to load route            | 500         |
| `NO_TIMING_DATA`    | Route has no timing information | 404         |

---

## Configuration Errors

| Code                    | Description                     | HTTP Status |
| ----------------------- | ------------------------------- | ----------- |
| `VALIDATION_ERROR`      | Configuration validation failed | 422         |
| `INVALID_CONFIGURATION` | Configuration format invalid    | 400         |
| `CONFIG_UPDATE_FAILED`  | Failed to update configuration  | 500         |

---

## Request Errors

| Code                | Description                | HTTP Status |
| ------------------- | -------------------------- | ----------- |
| `INVALID_REQUEST`   | Malformed request          | 400         |
| `MISSING_PARAMETER` | Required parameter missing | 400         |
| `INVALID_PARAMETER` | Parameter value invalid    | 400         |
| `INVALID_SPEED`     | Speed value out of range   | 400         |

---

## Service Errors

| Code                   | Description                      | HTTP Status |
| ---------------------- | -------------------------------- | ----------- |
| `SERVICE_ERROR`        | General service error            | 500         |
| `INITIALIZATION_ERROR` | Service not properly initialized | 500         |
| `CALCULATION_ERROR`    | Calculation failed               | 500         |

---

[Back to API Reference](./README.md) | [Back to errors](./errors.md)
