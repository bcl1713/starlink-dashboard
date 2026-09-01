# Monitoring Stack Configuration

This directory contains Prometheus and Grafana configuration for the Starlink
monitoring system.

---

## Documentation Topics

- **[Services Overview](./services-overview.md)** - Prometheus and Grafana setup
- **[React Operations Overview](../../docs/operations-overview.md)** - Canonical
  operator view, safe fallback, and troubleshooting

---

## Quick Reference

### Directory Structure

```text
monitoring/
├── prometheus/          # Prometheus configuration
│   ├── prometheus.yml   # Main Prometheus config
│   └── rules/           # Alert rules (if any)
├── grafana/             # Grafana provisioning
│   └── provisioning/    # Dashboard and datasource provisioning
└── README.md            # This file
```

### Service Access

- **React Operations Overview:** `<http://localhost:5173/overview>` in local
  frontend development (or deployed Mission Planner origin plus `/overview`) —
  canonical operator view
- **Prometheus:** <http://localhost:9090>
- **Grafana:** <http://localhost:3000> (default: admin/admin) — supported
  dual-run fallback

Use `/overview` for normal operations. Retain Grafana for existing dashboards,
dashboard-specific functions not verified in React, and immediate fallback. For
overview monitoring, radar, or CSP faults, follow the linked operations runbook
instead of exposing Prometheus to browser configuration. Grafana has no approved
retirement date; rollback keeps it and Prometheus available.

### Key Features

**Prometheus:**

- 1-second scrape interval for real-time data
- Configurable retention period (default: 1 year, ~2.4 GB)
- Alert rules support for mission-critical windows

**Grafana:**

- Pre-configured Prometheus datasource
- Fullscreen Overview dashboard with real-time tracking
- Mission communication planning visualization

---

## Quick Start

### Verify Services Running

```bash
# Check all containers
docker compose ps

# Test Prometheus
curl http://localhost:9090/-/healthy

# Test Grafana
curl http://localhost:3000/api/health
```

### Access Dashboards

1. Open the React overview at `/overview` on the Mission Planner origin.
2. Use Grafana at <http://localhost:3000> for existing dashboard-specific work
   or if the overview is interrupted.
3. For Grafana, login with the configured credentials and navigate to the
   required existing dashboard.

---

[Back to project root](../../README.md)
