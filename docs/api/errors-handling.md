# Error Handling Best Practices & Troubleshooting

[Back to API Reference](./README.md) | [Back to errors](./errors.md)

---

## Error Handling Best Practices

Best practices for handling errors when working with the Starlink Dashboard API.

### Error Handling in Client Code

#### Python Example

```python
import requests

try:
    response = requests.post(
        'http://localhost:8000/api/pois',
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

#### JavaScript Example

```javascript
async function createPOI(data) {
  try {
    const response = await fetch("http://localhost:8000/api/pois", {
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

    response = requests.post('http://localhost:8000/api/pois', json=data)
    response.raise_for_status()
    return response.json()
```

---

## Troubleshooting Guide

Diagnostic steps and solutions for persistent or unexplained API errors.

### Check Service Health

Always start by checking service health:

```bash
curl http://localhost:8000/health
```

If this fails, the backend may be down or unreachable.

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

### Common Solutions

#### "Service is healthy" but endpoints fail

**Cause:** Initialization issue with specific components.

**Solution:**

```bash
# Check logs for errors
docker compose logs starlink-location | rg -i error

# Restart service
docker compose restart starlink-location
```

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

#### Validation errors on valid data

**Cause:** Type mismatch or encoding issues.

**Solution:**

```bash
# Ensure JSON is properly formatted
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d @poi_data.json  # Use file input for complex data

# Check request headers
curl -v http://localhost:8000/api/pois  # Verbose output
```

#### 404 errors on existing resources

**Cause:** Incorrect ID or resource was deleted.

**Solution:**

```bash
# List all POIs to get correct IDs
curl http://localhost:8000/api/pois | jq '.[] | {id, name}'

# Check active routes
curl http://localhost:8000/api/routes
```

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

[Back to API Reference](./README.md) | [Back to errors](./errors.md)
