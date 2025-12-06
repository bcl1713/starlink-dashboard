# ETA Route Timing API Index

[Back to API Reference](../README.md) | [Back to main docs](../../index.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Overview

Advanced ETA calculation endpoints for route-based timing, waypoint tracking,
and live position updates.

---

## Endpoint Categories

### [Waypoint ETA Endpoints](./waypoint-endpoints.md)

Calculate ETAs to specific waypoints and locations:

- `/api/routes/{route_id}/eta/waypoint/{waypoint_index}` - Waypoint ETA
- `/api/routes/{route_id}/eta/location` - Location ETA

**Use cases:** Real-time navigation, waypoint tracking, arrival predictions

---

### [Route Progress Endpoints](./progress-endpoints.md)

Track overall route progress and timing:

- `/api/routes/{route_id}/progress` - Route progress
- `/api/routes/active/timing` - Active route timing profile

**Use cases:** Progress dashboards, flight monitoring, completion tracking

---

### [Metrics & Cache Endpoints](./metrics-cache-endpoints.md)

Monitor ETA performance and manage cache:

- `/api/routes/metrics/eta-cache` - Cache performance metrics
- `/api/routes/metrics/eta-accuracy` - Accuracy statistics
- `/api/routes/cache/cleanup` - Cache cleanup
- `/api/routes/cache/clear` - Clear cache

**Use cases:** Performance monitoring, accuracy tracking, system maintenance

---

### [Live Mode Endpoints](./live-mode-endpoints.md)

Real-time position integration:

- `/api/routes/live-mode/active-route-eta` - Live position ETA

**Use cases:** Real-time tracking, Starlink integration, live updates

---

## Quick Examples

### Get Waypoint ETA (cURL)

```bash
curl "http://localhost:8000/api/routes/route-001/eta/waypoint/5"
```

### Get Route Progress (Python)

```python
import requests

response = requests.get('http://localhost:8000/api/routes/route-001/progress')
progress = response.json()
print(f"Progress: {progress['progress_percent']}%")
```

### Monitor Cache Performance (JavaScript)

```javascript
const response = await fetch(
  "http://localhost:8000/api/routes/metrics/eta-cache",
);
const metrics = await response.json();
console.log(`Cache hit rate: ${metrics.hit_rate_percent}%`);
```

---

## Related Documentation

- [API Reference Index](../README.md) - Complete API overview
- [Core Endpoints](../endpoints/core.md) - Health and metrics
- [POI Endpoints](../endpoints/poi.md) - POI-based ETAs
- [Route Timing Guide](../../route-timing-guide.md) - Route timing features

---

[Back to API Reference](../README.md) | [Back to main docs](../../index.md)
