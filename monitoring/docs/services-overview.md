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

`/overview` is the canonical React operator view for day-to-day monitoring.
Grafana remains deployed and supported as the dual-run fallback for existing
dashboards and functions not explicitly verified in React. Use the overview for
current operations; use Grafana for dashboard-specific workflows or immediate
fallback. There is no approved Grafana retirement date.

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

For overview monitoring, radar, or CSP troubleshooting, use the
[operations overview runbook](../../docs/operations-overview.md#troubleshooting-and-escalation).
Do not expose the Prometheus service endpoint in browser configuration; the
browser accesses monitoring through same-origin backend API routes. During a
rollback, keep Grafana and Prometheus available.

---

[Back to Monitoring Docs](./README.md)
