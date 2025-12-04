# Monitoring Stack Configuration

**This document has been reorganized into multiple focused files.**

Please see: **[Monitoring Documentation](./docs/README.md)**

---

## Quick Links

- **[Monitoring Index](./docs/README.md)** - Complete documentation
- **[Services Overview](./docs/services-overview.md)** - Prometheus and Grafana
- **[Performance Tuning](./docs/performance-tuning.md)** - Optimization tips
- **[Troubleshooting](./docs/troubleshooting.md)** - Common display issues

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

- **Prometheus:** <http://localhost:9090>
- **Grafana:** <http://localhost:3000> (default: admin/admin)

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
