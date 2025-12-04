# API Error Handling

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

---

## Table of Contents

1. [Error Response Format](#error-response-format)
2. [HTTP Status Codes](#http-status-codes)
3. [Common Error Scenarios](#common-error-scenarios)
4. [Error Codes Reference](#error-codes-reference)
5. [Troubleshooting Guide](#troubleshooting-guide)

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

## Common Error Scenarios

### Invalid Coordinates

**Scenario:** Coordinates outside valid range.

**Request:**

```bash
curl -X POST <http://localhost:8000/api/pois> \
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

### POI Not Found

**Scenario:** Attempting to access non-existent POI.

**Request:**

```bash
curl <http://localhost:8000/api/pois/nonexistent-poi-id>
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

### Duplicate POI Name

**Scenario:** Creating POI with name that already exists.

**Request:**

```bash
curl -X POST <http://localhost:8000/api/pois> \
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

### Configuration Validation Error

**Scenario:** Invalid configuration values.

**Request:**

```bash
curl -X POST <http://localhost:8000/api/config> \
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

### Route Not Found

**Scenario:** Attempting to access non-existent route.

**Request:**

```bash
curl <http://localhost:8000/api/routes/nonexistent-route/progress>
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

### No Active Route

**Scenario:** Requesting active route information when no route is active.

**Request:**

```bash
curl <http://localhost:8000/api/routes/active/timing>
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

### Missing Required Parameter

**Scenario:** Required query parameter not provided.

**Request:**

```bash
curl "<http://localhost:8000/api/routes/route-001/eta/location">
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

### Invalid Speed Value

**Scenario:** Speed parameter out of valid range.

**Request:**

```bash
curl "<http://localhost:8000/api/pois/etas?speed_knots=-50">
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

### Service Unavailable

**Scenario:** Backend service experiencing issues.

**Request:**

```bash
curl <http://localhost:8000/api/status>
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

## Error Codes Reference

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

## Troubleshooting Guide

### Check Service Health

Always start by checking service health:

```bash
curl <http://localhost:8000/health>
```

If this fails, the backend may be down or unreachable.

---

### Enable Debug Logging

For detailed error information:

```bash
# Edit .env
LOG_LEVEL=DEBUG

# Restart services
docker compose down
docker compose up -d

# View logs
docker compose logs -f starlink-location
```

---

### Common Solutions

#### "Service is healthy" but endpoints fail

**Cause:** Initialization issue with specific components.

**Solution:**

```bash
# Check logs for errors
docker compose logs starlink-location | grep -i error

# Restart service
docker compose restart starlink-location
```

---

#### Persistent 500 errors

**Cause:** Backend configuration or data file issues.

**Solution:**

```bash
# Check POI file
cat backend/starlink-location/data/pois.json | jq .

# Reset if corrupted
echo '[]' > backend/starlink-location/data/pois.json

# Restart
docker compose restart starlink-location
```

---

#### Validation errors on valid data

**Cause:** Type mismatch or encoding issues.

**Solution:**

```bash
# Ensure JSON is properly formatted
curl -X POST <http://localhost:8000/api/pois> \
  -H "Content-Type: application/json" \
  -d @poi_data.json  # Use file input for complex data

# Check request headers
curl -v <http://localhost:8000/api/pois>  # Verbose output
```

---

#### 404 errors on existing resources

**Cause:** Incorrect ID or resource was deleted.

**Solution:**

```bash
# List all POIs to get correct IDs
curl <http://localhost:8000/api/pois> | jq '.[] | {id, name}'

# Check active routes
curl <http://localhost:8000/api/routes>
```

---

### Getting Help

If errors persist:

1. **Collect error information:**
   - Full error response (JSON)
   - Request that triggered error
   - Service logs

2. **Check documentation:**
   - [Troubleshooting Guide](../troubleshooting/README.md)
   - [Setup Guide](../setup/README.md)
   - Interactive API docs at `/docs`

3. **Common issues:**
   - Docker container not running
   - Port conflicts
   - File permission issues
   - Missing environment variables

---

## Best Practices

### Error Handling in Client Code

**Python example:**

```python
import requests

try:
    response = requests.post(
        '<http://localhost:8000/api/pois',>
        json={
            "name": "Test POI",
            "latitude": 40.7128,
            "longitude": -74.0060
        }
    )
    response.raise_for_status()  # Raises exception for 4xx/5xx
    poi = response.json()
    print(f"Created POI: {poi['id']}")

except requests.exceptions.HTTPError as e:
    error_data = e.response.json()
    print(f"Error: {error_data['detail']}")
    print(f"Code: {error_data.get('error_code', 'UNKNOWN')}")

except requests.exceptions.RequestException as e:
    print(f"Request failed: {e}")
```

**JavaScript example:**

```javascript
async function createPOI(data) {
  try {
    const response = await fetch("<http://localhost:8000/api/pois",> {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(`${error.error_code}: ${error.detail}`);
    }

    return await response.json();
  } catch (error) {
    console.error("POI creation failed:", error);
    throw error;
  }
}
```

---

### Retry Logic

For transient errors (500, 503), implement exponential backoff:

```python
import time
import requests

def retry_request(url, max_retries=3, backoff=2):
    for attempt in range(max_retries):
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code >= 500 and attempt < max_retries - 1:
                wait_time = backoff ** attempt
                print(f"Retry {attempt + 1} after {wait_time}s")
                time.sleep(wait_time)
            else:
                raise
```

---

### Validation Before Requests

Validate data client-side before sending to API:

```python
def validate_coordinates(lat, lon):
    """Validate coordinates before API request."""
    if not (-90 <= lat <= 90):
        raise ValueError(f"Invalid latitude: {lat}")
    if not (-180 <= lon <= 180):
        raise ValueError(f"Invalid longitude: {lon}")

def create_poi(name, lat, lon, description=None):
    """Create POI with client-side validation."""
    validate_coordinates(lat, lon)

    data = {
        "name": name,
        "latitude": lat,
        "longitude": lon
    }
    if description:
        data["description"] = description

    response = requests.post('<http://localhost:8000/api/pois',> json=data)
    response.raise_for_status()
    return response.json()
```

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
