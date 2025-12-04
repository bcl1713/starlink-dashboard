# API Examples

**Note:** This is a redirect file. The full examples documentation has been
preserved.

For complete API examples (453 lines), see: **[examples.md](./examples.md)**

---

## Quick Examples

### Upload and Activate Route

```bash
# Upload KML file
curl -X POST \
  -F "file=@route.kml" \
  http://localhost:8000/api/routes/upload

# Activate route
curl -X POST \
  http://localhost:8000/api/routes/{route_id}/activate
```

### Get ETAs to POIs

```bash
# List all POIs with ETAs
curl http://localhost:8000/api/pois/etas | jq .

# Get ETA to specific POI
curl http://localhost:8000/api/pois/{poi_id}/eta | jq .
```

### Create and Activate Mission

```bash
# Create mission
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Mission",
    "departure_time": "2025-12-04T10:00:00Z",
    "arrival_time": "2025-12-04T18:00:00Z"
  }' \
  http://localhost:8000/api/missions

# Activate mission
curl -X POST \
  http://localhost:8000/api/missions/{mission_id}/activate
```

---

[Full Examples Documentation →](./examples.md)

[Back to API Reference](./README.md)
