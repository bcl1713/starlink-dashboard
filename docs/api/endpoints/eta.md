# ETA Route Timing API Endpoints

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

---

## Reorganization Notice

This document has been reorganized into topic-focused files for better
navigation and maintainability.

**Please visit the [ETA Index](./eta/README.md) to access all ETA endpoint
documentation.**

---

## Quick Links

- **[ETA Index](./eta/README.md)** - Complete ETA endpoint overview
- [Waypoint ETA Endpoints](./eta/waypoint-endpoints.md) - Waypoint and location
  ETAs
- [Route Progress Endpoints](./eta/progress-endpoints.md) - Progress tracking
- [Metrics & Cache Endpoints](./eta/metrics-cache-endpoints.md) - Performance
  monitoring
- [Live Mode Endpoints](./eta/live-mode-endpoints.md) - Real-time integration

---

## Quick Examples

### Get Waypoint ETA

```bash
curl "http://localhost:8000/api/routes/route-001/eta/waypoint/5"
```

### Get Route Progress

```bash
curl "http://localhost:8000/api/routes/route-001/progress"
```

### Clear ETA Cache

```bash
curl -X POST http://localhost:8000/api/routes/cache/clear
```

---

## Related Documentation

- [API Reference Index](./README.md) - Complete API overview
- [Core Endpoints](./core.md) - Health and metrics
- [POI Endpoints](./poi.md) - POI-based ETAs
- [Route Timing Guide](../../ROUTE-TIMING-GUIDE.md) - Route timing features

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
