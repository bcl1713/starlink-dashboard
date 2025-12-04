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

## Grafana

Grafana visualizes Prometheus metrics with interactive dashboards.

### Grafana Configuration

**Directory:** `grafana/provisioning/`

**Access:** <http://localhost:3000> (default: admin/admin)

### Grafana Features

- Pre-configured Prometheus datasource
- Fullscreen Overview dashboard with real-time tracking
- Mission communication planning visualization

### Grafana Operations

```bash
# Check Grafana health
curl http://localhost:3000/api/health

# Reset admin password
docker compose exec grafana grafana-cli admin reset-admin-password newpassword
```

---

[Back to Monitoring Docs](./README.md)
