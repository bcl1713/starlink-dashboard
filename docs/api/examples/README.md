# API Usage Examples Index

[Back to API Reference](../README.md) | [Back to main docs](../../index.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Overview

Practical examples for using the Starlink Dashboard API with different tools and
languages.

---

## Available Examples

### [cURL Examples](./curl-examples.md)

Command-line examples for quick testing:

- Health and status checks
- POI management (create, update, delete)
- ETA calculations
- Configuration management
- Route queries

**Best for:** Quick testing, shell scripts, debugging

---

### [Python Examples](./python-examples.md)

Python requests library examples:

- Basic API usage
- POI management workflows
- ETA calculations
- Route progress monitoring
- Configuration updates
- Error handling patterns

**Best for:** Backend integrations, data analysis, automation scripts

---

### [JavaScript Examples](./javascript-examples.md)

Browser and Node.js examples:

- Fetch API (browser)
- Axios (Node.js)
- Async/await patterns
- Real-time monitoring
- Error handling

**Best for:** Frontend applications, web dashboards, Node.js services

---

## Quick Start Examples

### Check Service Health (cURL)

```bash
curl http://localhost:8000/health | jq .
```

### Create a POI (Python)

```python
import requests

response = requests.post('http://localhost:8000/api/pois', json={
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654
})
poi = response.json()
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
- [POI Endpoints](../endpoints/poi.md) - POI management
- [ETA Endpoints](../endpoints/eta.md) - ETA calculations
-See the [Error Reference](../errors.md) for details on handling errors.mats

---

[Back to API Reference](../README.md) | [Back to main docs](../../index.md)
