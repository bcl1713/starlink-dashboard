# First-Time Configuration

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)

---

## Overview

Optional configuration steps to enhance your Starlink Dashboard experience after
installation.

---

## Upload Sample Routes

Sample routes are available in `/data/sample_routes/`:

**Via UI:**

```bash
open http://localhost:8000/ui/routes
```

**Or via API:**

```bash
curl -X POST \
  -F "file=@data/sample_routes/simple-circular.kml" \
  http://localhost:8000/api/routes/upload
```

---

## Create POIs

**Via UI:**

```bash
open http://localhost:8000/ui/pois
```

**Via API:**

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New York City",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "description": "NYC Downtown"
  }'
```

---

## View Dashboards

Open Mission Planner at <http://localhost:5173>:

1. **Overview** - Globe, position history, and network metrics
2. **Missions** - Mission planning
3. **Configuration** - Display and history settings

---

## Next Steps

1. **[Configuration](./configuration.md)** - Customize for your use case
2. **[API Reference](../api/README.md)** - Explore available endpoints
3. **[Route Management](../route-api-endpoints.md)** - Upload flight routes

---

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)
