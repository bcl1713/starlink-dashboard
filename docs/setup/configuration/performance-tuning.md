# Performance Tuning

[Back to Configuration Guide](./README.md)

---

## Storage Optimization

### Reduce Prometheus Retention

Save disk space by reducing retention period:

```bash
# In .env
PROMETHEUS_RETENTION=30d  # ~200 MB instead of 2.4 GB for 1y
PROMETHEUS_RETENTION=90d  # ~600 MB
PROMETHEUS_RETENTION=15d  # ~100 MB
```

**Apply changes:**

```bash
docker compose down
docker compose up -d
```

**Verify retention:**

```bash
docker compose logs prometheus | rg -i retention
```

### Storage Calculation

```text
Number of metrics: 45
Scrape interval: 1 second
Retention period: 1 year (31,536,000 seconds)
Size per sample: ~1.5 bytes (compressed)
Compression overhead: ~1.2x

Storage = (45 × 31,536,000 × 1.5 × 1.2) / 1,073,741,824 ≈ 2.4 GB
```

**Common retention periods:**

| Retention | Storage | Use Case            |
| --------- | ------- | ------------------- |
| `1y`      | ~2.4 GB | Long-term analysis  |
| `90d`     | ~600 MB | Quarterly reviews   |
| `30d`     | ~200 MB | Monthly monitoring  |
| `15d`     | ~100 MB | Development/testing |
| `7d`      | ~50 MB  | Minimal storage     |

---

## Memory Optimization

For systems with limited memory, add resource limits in `docker-compose.yml`:

```yaml
services:
  starlink-location:
    deploy:
      resources:
        limits:
          memory: 256M

  prometheus:
    deploy:
      resources:
        limits:
          memory: 512M

  grafana:
    deploy:
      resources:
        limits:
          memory: 256M
```

**Apply:**

```bash
docker compose down
docker compose up -d
```

**Monitor usage:**

```bash
docker stats --no-stream
```

---

## Network Optimization

For slow networks, increase scrape intervals:

**Edit `monitoring/prometheus/prometheus.yml`:**

```yaml
global:
  scrape_interval: 15s # Increase from default 10s
  scrape_timeout: 10s # Increase from default 5s
```

**Restart Prometheus:**

```bash
docker compose restart prometheus
```

---

## CPU Optimization

### Reduce Update Frequency

If CPU usage is high, reduce backend update frequency:

**Edit backend config:**

```yaml
# backend/starlink-location/config.yaml
update_interval_seconds: 2.0 # Instead of 1.0
```

**Rebuild:**

```bash
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d
```

### Check CPU Usage

```bash
# Monitor container CPU
docker stats --no-stream

# Identify high CPU container
docker stats <container-name>
```

---

## Monitoring Resource Usage

### Current Usage

```bash
# All containers
docker stats --no-stream

# Specific service
docker stats starlink-location --no-stream
```

### Disk Usage

```bash
# Check volume sizes
docker system df -v

# Prometheus data volume
docker volume inspect prometheus_data
```

### Memory Usage

```bash
# System memory
free -h

# Container memory
docker stats --format "table {{.Name}}\t{{.MemUsage}}"
```

---

[Back to Configuration Guide](./README.md)
