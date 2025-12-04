# Starlink Dashboard Troubleshooting Guide

**This document has been reorganized into multiple focused files.**

Please see: **[docs/troubleshooting/](./troubleshooting/README.md)**

## Quick Links

- **[Troubleshooting Index](./troubleshooting/README.md)** - Start here
- **[Service Issues](./troubleshooting/service-issues.md)** - Container startup,
  ports, Docker
- **[Backend Issues](./troubleshooting/backend-issues.md)** - Backend health,
  metrics, config
- **[Data Issues](./troubleshooting/data-issues.md)** - POI management, storage
- **[Quick Diagnostics](./troubleshooting/quick-diagnostics.md)** - Fast
  diagnostic commands

---

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

[Go to Full Troubleshooting Guide →](./troubleshooting/README.md)
