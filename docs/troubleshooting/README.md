# Starlink Dashboard Troubleshooting Guide

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Quick Diagnostics

Before diving into specific issues, run these checks:

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

## Troubleshooting Categories

- **[Service Issues](./service-issues.md)** - Container startup, port conflicts,
  Docker problems
- **[Backend Issues](./backend-issues.md)** - Backend health, metrics,
  configuration
- **[Data Issues](./data-issues.md)** - POI management, storage, persistence
- **[Quick Diagnostics](./quick-diagnostics.md)** - Fast diagnostic commands and
  verification steps

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
