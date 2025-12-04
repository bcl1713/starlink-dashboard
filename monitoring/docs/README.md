# Monitoring Stack Configuration

This directory contains Prometheus and Grafana configuration for the Starlink
monitoring system.

---

## Documentation Topics

- **[Services Overview](./services-overview.md)** - Prometheus and Grafana setup
- **[Mission Features](./mission-features.md)** - Mission communication planning
- **[Dashboard Management](./dashboard-management.md)** - Managing Grafana
  dashboards
- **[Performance Tuning](./performance-tuning.md)** - Optimization tips
- **[Troubleshooting](./troubleshooting.md)** - Common display issues

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

- **Prometheus:** <http://localhost:9090>
- **Grafana:** <http://localhost:3000> (default: admin/admin)

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

1. Open Grafana: <http://localhost:3000>
2. Login: admin/admin
3. Navigate to Dashboards → Fullscreen Overview

---

[Back to project root](../../README.md)
