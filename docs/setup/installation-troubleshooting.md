# Installation Troubleshooting

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)

---

## Overview

Common issues encountered during installation and their solutions.

---

## Services Won't Start

**Check logs:**

```bash
docker compose logs
```

**Common issues:**

- Port conflicts →See [Prerequisites](prerequisites-verification.md) for more
  info.
- Insufficient disk space → `df -h`
- Docker not running → `sudo systemctl start docker`

---

## Container Exits Immediately

**Check specific service:**

```bash
docker compose logs starlink-location
```

**Solution:**

```bash
# Rebuild without cache
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## Can't Access Services

**Check if containers are running:**

```bash
docker compose ps
```

**Check port bindings:**

```bash
docker compose ps
```

**Test from host:**

```bash
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health
```

---

## "Address Already in Use" Error

**Find process using port:**

```bash
# Linux/macOS
lsof -i :3000
lsof -i :8000
lsof -i :9090

# Kill process (if safe)
kill -9 <PID>
```

**Or change ports in `.env`:**

```bash
nano .env
# Change: GRAFANA_PORT=3001
docker compose down
docker compose up -d
```

---

## Prometheus Not Scraping

**Check Prometheus targets:**

```bash
open http://localhost:9090/targets
```

**Verify backend reachable from Prometheus:**

```bash
docker compose exec prometheus curl http://starlink-location:8000/health
```

---

## Grafana Shows No Data

**Verify data source:**

1. Go to <http://localhost:3000>
2. Configuration → Data Sources → Prometheus
3. Click "Test" button
4. Should show green "Data source is working"

**If test fails:**

```bash
# Check if Prometheus is running
docker compose ps prometheus

# Test from Grafana container
docker compose exec grafana curl http://prometheus:9090
```

---

## Build Fails

**Clear Docker cache:**

```bash
docker system prune -a
docker compose build --no-cache
```

**Check disk space:**

```bash
df -h
```

---

## Getting Help

If errors persist:

1. **Collect error information:**
   - Full error logs
   - Output from `docker compose ps`
   - Service logs from `docker compose logs`

2. **Check documentation:**
   - [Setup Guide](./README.md)
   - [Troubleshooting Guide](../troubleshooting/README.md)
   - [Prerequisites](prerequisites-verification.md)

3. **Common issues:**
   - Docker container not running
   - Port conflicts
   - File permission issues
   - Missing environment variables

---

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)
