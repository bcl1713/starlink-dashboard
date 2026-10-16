# API cURL Examples

[Back to API Reference](../README.md) | [Examples Index](./README.md)

---

## Health & Status

**Check Service Health:**

```bash
curl http://localhost:8000/health | jq .
```

**Get Current Status:**

```bash
curl http://localhost:8000/api/status | jq .
```

**Get Metrics (JSON):**

```bash
curl http://localhost:8000/api/status | jq .
```

**Get Prometheus Metrics:**

```bash
curl http://localhost:8000/metrics
```

---

## POI Management

**List All POIs:**

```bash
curl http://localhost:8000/api/pois | jq .
```

**Get Specific POI:**

```bash
curl http://localhost:8000/api/pois/poi-1 | jq .
```

**Create New POI:**

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Central Park",
    "latitude": 40.7829,
    "longitude": -73.9654,
    "description": "NYC Central Park"
  }' | jq .
```

**Update POI:**

```bash
curl -X PUT http://localhost:8000/api/pois/poi-1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "LaGuardia Airport (Updated)",
    "description": "LGA - Major NYC airport, departure point"
  }' | jq .
```

**Delete POI:**

```bash
curl -i -X DELETE http://localhost:8000/api/pois/poi-1
```

---

## ETA Calculations

**Get ETAs to All POIs:**

```bash
curl http://localhost:8000/api/pois/etas | jq .
```

**Get ETAs with Custom Position:**

```bash
curl "http://localhost:8000/api/pois/etas?latitude=40.7128&longitude=-74.0060&speed_knots=50" | jq .
```

**Get Route Progress:**

```bash
curl "http://localhost:8000/api/routes/route-001/progress?current_position_lat=40.7&current_position_lon=-74.0" | jq .
```

**Get Waypoint ETA:**

```bash
curl "http://localhost:8000/api/routes/route-001/eta/waypoint/5?current_position_lat=40.7&current_position_lon=-74.0" | jq .
```

---

## Configuration

**Get Current Configuration:**

```bash
curl http://localhost:8000/api/config | jq .
```

For updates, use the [configuration contract](../endpoints/configuration.md).
POST and PUT both replace a complete configuration; neither is a partial merge.

---

## Route & Geography

**Get Route GeoJSON:**

```bash
curl http://localhost:8000/api/route.geojson | jq .
```

---

[Back to API Reference](../README.md) | [Examples Index](./README.md)
