# Starlink Dashboard Troubleshooting Guide

**Purpose**: Help users diagnose and resolve problems
**Audience**: Users, operators, support staff

[Back to main docs](../INDEX.md)

---

## Quick Diagnostics

**Start here first** - Run these checks before diving into specific issues:

**[Quick Diagnostics Guide →](./quick-diagnostics.md)**

```bash
# 1. Check all services running
docker compose ps

# 2. Check backend health
curl http://localhost:8000/health

# 3. Check logs for errors
docker compose logs --tail=50

# 4. Check resource usage
docker stats --no-stream
```

---

## Troubleshooting by Symptom

### Services Won't Start

- **[Service Issues](./service-issues.md)** - Container startup, port
  conflicts, Docker problems
- **[Docker Services](./services/docker.md)** - Docker-specific
  configuration and issues
- **[Backend Service](./services/backend.md)** - Backend health, metrics,
  configuration
- **[Grafana Service](./services/grafana.md)** - Grafana configuration and
  connectivity
- **[Prometheus Service](./services/prometheus.md)** - Prometheus targets
  and scraping

### Connectivity Problems

- **[Live Mode](./connectivity/live-mode.md)** - Connection to Starlink
  dish
- **[Data Issues](./connectivity/data.md)** - Network issues and data flow
- **[Data Storage](./connectivity/data-storage.md)** - Persistence and
  storage problems
- **[POI Management](./connectivity/poi-management.md)** - Points of
  interest issues
- **[Performance](./connectivity/performance.md)** - Speed and resource
  issues

### Data & Metrics

- **[Data Issues](./data-issues.md)** - POI management, storage,
  persistence
- **[Metrics & Monitoring](./metrics-monitoring.md)** - Prometheus and Grafana
  data collection

### Network & Performance

- **[Network Configuration](./services/network.md)** - Network connectivity
  between services
- **[Performance Tuning](./services/performance.md)** - Resource usage and
  optimization

---

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

---

## Getting Help

### Before asking for help, gather

1. **Log output:**

   ```bash
   docker compose logs > debug-logs.txt
   ```

2. **System info:**

   ```bash
   docker --version
   docker compose version
   uname -a
   ```

3. **Configuration:**

   ```bash
   cat .env | rg -v "PASSWORD"
   docker compose config | head -50
   ```

4. **Current state:**

   ```bash
   docker compose ps
   docker stats --no-stream
   curl http://localhost:8000/health
   curl http://localhost:9090/api/v1/targets
   ```

### Resources

- [API Reference](../api/README.md)
- [Setup Guide](../setup/README.md)
- [Design Document](../design-document.md)
- [Backend README](../../backend/starlink-location/README.md)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Still Need Help?

Check:

1. Related documentation files
2. Backend/Prometheus/Grafana container logs
3. System resource usage
4. Network connectivity between containers
5. File permissions
6. .env configuration values
7. Docker version compatibility

---

[Back to main docs](../INDEX.md)
