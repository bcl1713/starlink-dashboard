# API Usage Examples

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Reorganization Notice

This document has been reorganized into language-specific files for better
navigation and maintainability.

**Please visit the [Examples Index](./examples/README.md) to access all example
code.**

---

## Quick Links

- **[Examples Index](./examples/README.md)** - Complete examples overview
- [cURL Examples](./examples/curl-examples.md) - Command-line examples
- [Python Examples](./examples/python-examples.md) - Python requests library
- [JavaScript Examples](./examples/javascript-examples.md) - Browser and Node.js

---

## Quick Start

### cURL (Command Line)

```bash
# Check service health
curl http://localhost:8000/health | jq .

# List all POIs
curl http://localhost:8000/api/pois | jq .

# Get ETAs
curl http://localhost:8000/api/pois/etas | jq .
```

### Python

```python
import requests

# Get service health
response = requests.get('http://localhost:8000/health')
print(response.json())

# Create POI
poi_data = {"name": "Central Park", "latitude": 40.7829, "longitude": -73.9654}
response = requests.post('http://localhost:8000/api/pois', json=poi_data)
```

### JavaScript

```javascript
// Get service health
const response = await fetch("http://localhost:8000/health");
const health = await response.json();

// Get ETAs
const etas = await fetch("http://localhost:8000/api/pois/etas");
const data = await etas.json();
```

---

## Related Documentation

- [API Reference Index](./README.md) - Complete API overview
- [Core Endpoints](./core-endpoints.md) - Health and metrics
- [POI Endpoints](./poi-endpoints.md) - POI management
- [ETA Endpoints](./eta-endpoints.md) - ETA calculations

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
