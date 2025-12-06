# Route & Geographic API Endpoints

**Last Updated:** 2025-11-04 **Backend Version:** 0.3.0

## Overview

Endpoints for route data, GeoJSON export, and geographic visualization.

**Related Documentation:**

- [Core Endpoints](./core.md) - Health and metrics
- [POI Endpoints](./poi.md) - POI management
- [ETA Endpoints](./eta.md) - ETA calculations

---

## GeoJSON Endpoints

### GET `/route.geojson`

Get route history as GeoJSON for map display.

**Description:** Returns the position history (route) as a GeoJSON LineString,
suitable for rendering on Grafana Geomap panels.

**Response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [-74.006, 40.7128],
          [-74.005, 40.7138],
          [-74.004, 40.7148]
        ]
      },
      "properties": {
        "name": "Position History"
      }
    }
  ]
}
```

**Status Codes:**

- `200 OK` - Route data available
- `204 No Content` - No route data yet

**Use Case:** Grafana Geomap layer, position history visualization.

---

### GET `/geojson`

Alias for `/route.geojson` (for compatibility).

**Response:** Same as `/route.geojson`

---

## Examples

### cURL Examples

**Get Route GeoJSON:**

```bash
curl http://localhost:8000/route.geojson | jq .
```

**Get GeoJSON (Alias):**

```bash
curl http://localhost:8000/geojson | jq .
```

### Python Examples

```python
import requests

# Get route history
response = requests.get('http://localhost:8000/route.geojson')
geojson = response.json()
print(f"Route has {len(geojson['features'][0]['geometry']['coordinates'])} points")
```

---

## Grafana Integration

The GeoJSON endpoints are designed for use with Grafana Geomap panels:

1. Add a new Geomap panel
2. Configure data source as "Infinity" or "JSON API"
3. Set URL to `http://localhost:8000/route.geojson`
4. Configure refresh interval (e.g., 10 seconds)
5. Style the LineString layer with color and width

---

## Related Documentation

- [API Reference Index](../README.md) - Complete API overview
- [Core Endpoints](./core.md) - Health and metrics
- See [ETA Endpoints](eta.md) for timing details.
- See [Grafana Dashboards](../../grafana-dashboards.md) for visualization details.
