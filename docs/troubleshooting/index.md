# Starlink Dashboard Troubleshooting Guide

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Overview

This troubleshooting guide helps you diagnose and resolve common issues with the
Starlink Dashboard system. The guide is organized into three main areas:

- **[Docker Services](./services/docker.md)** - Container startup, port
  conflicts, and Docker-specific issues
- **[Metrics & Monitoring](./metrics-monitoring.md)** - Prometheus and Grafana
  configuration and data collection
- **[Connectivity & Data](./connectivity/data.md)** - Network issues, live mode,
  data storage, and POI management

## Quick Diagnostics

Before diving into specific issues, run these checks:

```bash
# 1. Check all services running
docker compose ps

# 2. Check backend health
curl <http://localhost:8000/health>

# 3. Check logs for errors
docker compose logs --tail=50

# 4. Check resource usage
docker stats --no-stream
```

## Common Issues Quick Links

### Service Won't Start

- [Container exits immediately](./services/docker.md#container-exits-immediately)
- [Failed to connect to Docker daemon](./services/docker.md#failed-to-connect-to-docker-daemon)
- [Port conflicts](./services/docker.md#port-conflicts)

### Data Issues

- [Metrics not updating](./services/docker.md#metrics-not-updating)
- [Dashboards empty or no data](./metrics-monitoring.md#dashboards-empty)
- [POI list empty or missing](./connectivity/data.md#poi-list-empty-or-missing)

### Connectivity Issues

- [Live mode won't connect to dish](./connectivity/data.md#live-mode-wont-connect-to-dish)
- [Services can't communicate](./connectivity/data.md#services-cant-communicate)

### Performance Issues

- [High CPU usage](./connectivity/data.md#high-cpu-usage)
- [High memory usage](./connectivity/data.md#high-memory-usage)
- [Slow dashboard loading](./connectivity/data.md#slow-dashboard-loading)

## Debug Logging

### Enable debug mode

```bash
# Edit .env
LOG_LEVEL=DEBUG
JSON_LOGS=true

# Restart
docker compose down
docker compose up -d

# View detailed logs
docker compose logs -f starlink-location
```

### View all component logs

```bash
# All services
docker compose logs -f

# Specific service with timestamps
docker compose logs -f --timestamps starlink-location

# Last N lines
docker compose logs --tail=100 starlink-location

# Search for errors
docker compose logs | rg -i "error"
```

### Save logs to file

```bash
# Save all logs
docker compose logs > logs.txt

# Save specific service logs
docker compose logs starlink-location > backend.log
docker compose logs prometheus > prometheus.log
docker compose logs grafana > grafana.log
```

## Getting Help

### Before asking for help, gather

1. **Log output:**

   ```bash
   docker compose logs > debug-logs.txt
   ```

1. **System info:**

   ```bash
   docker --version
   docker compose version
   uname -a
   ```

1. **Configuration:**

   ```bash
   cat .env | rg -v "PASSWORD"
   docker compose config | head -50
   ```

1. **Current state:**

   ```bash
   docker compose ps
   docker stats --no-stream
   curl <http://localhost:8000/health>
   curl <http://localhost:9090/api/v1/targets>
   ```

### Resources

- [API Reference](../api/README.md)
- [Setup Guide](../setup/installation.md)
- [Design Document](../architecture/design-document.md)
- [Backend README](../../backend/starlink-location/README.md)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

## Still Need Help?

Check:

1. Related documentation files
2. Backend/Prometheus/Grafana container logs
3. System resource usage
4. Network connectivity between containers
5. File permissions and permissions
6. .env configuration values
7. Docker version compatibility
