# First-Time Configuration

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

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

Open Grafana and explore:

1. **Starlink Overview** - Main dashboard with map
2. **Network Metrics** - Latency, throughput
3. **Position & Movement** - Position history

---

## Next Steps

1. **[Configuration](./configuration.md)** - Customize for your use case
2. **[API Reference](../api/README.md)** - Explore available endpoints
3. **[Route Management](../../CLAUDE.md#route-management)** - Upload flight
   routes

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
