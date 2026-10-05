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
./scripts/compose.sh build --no-cache
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
curl --fail http://localhost:5173/api/status
```

---

## "Address Already in Use" Error

**Find process using port:**

```bash
# Linux/macOS
lsof -i :5173
lsof -i :8000
lsof -i :9090

# Kill process (if safe)
kill -9 <PID>
```

**Or change ports in `.env`:**

```bash
nano .env
# Change: STARLINK_LOCATION_PORT=8001
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

## Mission Planner Issues

Open <http://localhost:5173> and check the Overview. Verify the same-origin
backend proxy and Prometheus readiness:

```bash
docker compose ps mission-planner starlink-location prometheus
docker compose logs --tail=30 mission-planner starlink-location
curl --fail http://localhost:5173/api/status
curl --fail http://localhost:9090/-/ready
```

For empty history graphs, inspect Prometheus targets at
<http://localhost:9090/targets> and the backend metrics at
<http://localhost:8000/metrics>.

---

## Build Fails

**Clear Docker cache:**

```bash
docker system prune -a
./scripts/compose.sh build --no-cache
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
