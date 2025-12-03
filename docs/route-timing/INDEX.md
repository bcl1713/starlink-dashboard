# Route Timing Feature Guide

**Version:** 0.4.0
**Last Updated:** 2025-11-05
**Status:** Complete - All 451 tests passing

## Overview

The Route Timing feature enables realistic simulation and tracking of timed
flight paths with expected waypoint arrival times. This guide is organized into
three sections:

- **[Concepts](./concepts.md)** - ETA modes, flight phases, and timing logic
- **[Implementation](./implementation.md)** - How to use the feature, API
  examples, and KML format
- **[Troubleshooting](./troubleshooting.md)** - Common issues and solutions

## Key Features

- **Automatic Timing Extraction:** Parse expected waypoint arrival times from
  KML files
- **Speed Calculations:** Calculate expected segment speeds between consecutive
  waypoints
- **Real-time ETAs:** Get accurate estimates to waypoints and arbitrary
  locations
- **Realistic Simulation:** Simulator respects timing data and expected speeds
  for authentic movement
- **Performance Optimization:** Intelligent caching reduces calculation load
- **Accuracy Tracking:** Monitor how accurate your ETA predictions are

### Core Capabilities

- Extracts timing from KML descriptions: `Time Over Waypoint: YYYY-MM-DD
  HH:MM:SSZ`
- Calculates distances using haversine formula for Earth-based accuracy
- Provides granular (waypoint-level) and aggregate (route-level) timing metrics
- Exposes timing data through REST API and Prometheus metrics
- Integrates seamlessly with existing route and POI systems
- Works with or without timing data (graceful degradation)

## Quick Start

### 1. Prepare a KML File with Timing Data

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Flight Route KADW-PHNL</name>
      <LineString>
        <coordinates>
          -76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z
          -75.0,38.0,2000 Time Over Waypoint: 2025-10-27 16:51:00Z
          -74.0,37.5,2500 Time Over Waypoint: 2025-10-27 17:05:00Z
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

### 2. Upload the Route

```bash
curl -X POST \
  -F "file=@your-timed-route.kml" \
  http://localhost:8000/api/routes/upload
```

Response includes `has_timing_data: true` if timing was found.

### 3. Activate the Route

```bash
curl -X POST http://localhost:8000/api/routes/{route_id}/activate
```

### 4. Check Timing Profile

```bash
curl http://localhost:8000/api/routes/active/timing | jq .
```

## What's Next?

- **Learn the concepts:** Read about [ETA modes and flight
  phases](./concepts.md)
- **Start using it:** See [implementation examples](./implementation.md)
- **Having issues?:** Check the [troubleshooting guide](./troubleshooting.md)

## Performance Considerations

### Cache Statistics

```bash
curl http://localhost:8000/api/routes/metrics/eta-cache
```

Typical output:

```json
{
  "cache_enabled": true,
  "ttl_seconds": 5,
  "total_cache_hits": 1250,
  "total_cache_misses": 342,
  "hit_rate_percent": 78.5
}
```

**Optimization Tips:**

- Cache hit rate above 70% is good
- Hit rate depends on position update frequency
- For dashboards updating every 1-2 seconds, expect 70-80% hit rate

### Large Route Handling

For routes with 1000+ waypoints:

1. **Upload time:** <2 seconds (parsing is efficient)
2. **Calculation time:** <50ms per ETA query
3. **Storage:** ~100KB per 1000 waypoints
4. **Memory:** Cache limited to 100 entries by default

---

**Feature Status:** Complete and Production Ready
**Test Coverage:** 451 tests passing (100%)
