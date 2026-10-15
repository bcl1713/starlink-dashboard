# Services Overview

[Back to Monitoring Docs](./README.md)

---

## Prometheus

Prometheus scrapes metrics from the backend service on a configurable interval
(default: 1 second).

### Configuration

**File:** `prometheus/prometheus.yml`

**Access:** <http://localhost:9090>

### Key Features

- 1-second scrape interval for real-time data
- Configurable retention period (default: 1 year, ~2.4 GB)
- Alert rules support for mission-critical windows

### Common Operations

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'

# Query a metric
curl 'http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees'

# Check health
curl http://localhost:9090/-/healthy
```

---

## Mission Planner

Mission Planner provides the native Overview and mission planning interface at
<http://localhost:5173>. Its Nginx proxy serves backend APIs from the same
origin. The backend queries Prometheus for Overview network history.

```bash
curl --fail http://localhost:5173/api/status
```

[Back to Monitoring Docs](./README.md)
