# Monitoring Stack Configuration

**This document has been reorganized into multiple focused files.**

Please see: **[Monitoring Documentation](./docs/README.md)**

---

## Quick Links

- **[Monitoring Index](./docs/README.md)** - Complete documentation
- **[Services Overview](./docs/services-overview.md)** - Prometheus and Grafana
- **[React Operations Overview](../docs/operations-overview.md)** - Canonical
  operator view, API boundary, fallback, and rollback guidance

---

## Directory Structure

```text
monitoring/
├── prometheus/          # Prometheus configuration
│   ├── prometheus.yml   # Main Prometheus config
│   └── rules/           # Alert rules (if any)
├── grafana/             # Grafana provisioning
│   └── provisioning/    # Dashboard and datasource provisioning
├── docs/                # Documentation
└── README.md            # This file
```

---

## Quick Reference

### Service Access

- **React Operations Overview:** `<http://localhost:5173/overview>` in local
  frontend development (or the deployed Mission Planner origin plus `/overview`)
  — canonical day-to-day operator view
- **Prometheus:** <http://localhost:9090>
- **Grafana:** <http://localhost:3000> (default: admin/admin) — supported
  dual-run fallback for existing dashboards and unverified React equivalents

Use `/overview` for current operations, telemetry, history, clocks, and map
controls. Keep Grafana procedures available for dashboard-specific work or an
immediate overview fallback. If overview monitoring, radar, or CSP fails, use
the linked operations runbook; do not expose Prometheus to the browser. There is
no approved Grafana retirement date, and rollback keeps Grafana and Prometheus
available.

### Verify Services

```bash
# Check all containers
docker compose ps

# Test Prometheus
curl http://localhost:9090/-/healthy

# Test Grafana
curl http://localhost:3000/api/health
```

---

[Go to Full Monitoring Documentation →](./docs/README.md)

[Back to project root](../README.md)
