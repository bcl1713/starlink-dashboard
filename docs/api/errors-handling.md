# Error Handling Best Practices

[Back to API Reference](./README.md) | [Back to errors](./errors.md)

---

## Overview

Best practices for handling errors when working with the Starlink Dashboard API.

---

## Error Handling in Client Code

### Python Example

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

### JavaScript Example

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

---

## Retry Logic

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

## Validation Before Requests

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

[Back to API Reference](./README.md) | [Back to errors](./errors.md)
