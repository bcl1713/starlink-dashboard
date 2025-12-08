# Route Timing Feature Guide

**This document has been reorganized into multiple focused files.**

Please see: **[Route Timing Documentation](./route-timing/README.md)**

---

**Version:** 0.4.0 **Last Updated:** 2025-11-05 **Status:** Complete - All 451
tests passing

## Quick Links

- **[Overview](./route-timing/README.md)** - Feature overview and capabilities
- **[Quick Start Guide](./route-timing/README.md#quick-start)** - Get started in
  5 minutes
- **[KML Format Reference](./route-timing/README.md#quick-start)** - Timing data
  format
- **[API Usage](./api/endpoints/routes.md)** - Route timing endpoints
- **[Troubleshooting](./troubleshooting/README.md)** - Common issues

---

## What is Route Timing?

The Route Timing feature allows you to:

- **Automatic Timing Extraction:** Parse expected waypoint arrival times from
  KML files
- **Speed Calculations:** Calculate expected segment speeds between consecutive
  waypoints
- **Real-time ETAs:** Get accurate estimates to waypoints and arbitrary
  locations
- **Realistic Simulation:** Simulator respects timing data for authentic
  movement
- **Performance Optimization:** Intelligent caching reduces calculation load
- **Accuracy Tracking:** Monitor ETA prediction accuracy

---

## Quick Start

### 1. Prepare KML with Timing

```xml
<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Flight Route</name>
      <LineString>
        <coordinates>
          -76.9,38.8,1000 Time Over Waypoint: 2025-10-27 16:45:00Z
          -75.0,38.0,2000 Time Over Waypoint: 2025-10-27 16:51:00Z
        </coordinates>
      </LineString>
    </Placemark>
  </Document>
</kml>
```

### 2. Upload and Activate

```bash
# Upload
curl -X POST -F "file=@route.kml" http://localhost:8000/api/routes/upload

# Activate
curl -X POST http://localhost:8000/api/routes/{route_id}/activate

# Check timing
curl http://localhost:8000/api/routes/active/timing | jq .
```

---

[Go to Full Route Timing Guide →](./route-timing/README.md)

[Back to main docs](./index.md)
