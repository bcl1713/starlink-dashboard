# Installation Verification

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

---

## Overview

This guide helps you verify that all services are running correctly and data is
flowing properly.

---

## Service Health Checks

### 1. Backend API

```bash
curl http://localhost:8000/health | jq .
```

✅ Should return `"status": "ok"`

---

### 2. Prometheus Targets

```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'
```

✅ Should return `"up"` for all targets

---

### 3. Grafana

```bash
curl -s http://localhost:3000/api/health | jq .
```

✅ Should return `"database": "ok"`

---

## Data Flow Verification

### 1. Backend Generating Metrics

```bash
curl http://localhost:8000/api/status | jq '.position'
```

✅ Should show current position data

---

### 2. Prometheus Scraping Backend

```bash
curl 'http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees' | jq .
```

✅ Should return metric value

---

### 3. Container Logs

```bash
docker compose logs --tail=20 starlink-location
```

✅ Should show simulation updates

---

## Quick Diagnostics

Run all checks at once:

```bash
echo "=== Backend Health ==="
curl -s http://localhost:8000/health | jq .status

echo "=== Prometheus Targets ==="
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'

echo "=== Grafana Health ==="
curl -s http://localhost:3000/api/health | jq .database

echo "=== Current Position ==="
curl -s http://localhost:8000/api/status | jq '.position | {latitude, longitude}'
```

---

## Next Steps

If all checks pass:

1. **[First-Time Configuration](./installation-first-time.md)** - Optional setup
2. **[Configuration](./configuration.md)** - Customize for your use case
3. **[API Reference](../api/README.md)** - Explore available endpoints

If checks fail:

- **[Troubleshooting](./installation-troubleshooting.md)** - Fix common issues

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
