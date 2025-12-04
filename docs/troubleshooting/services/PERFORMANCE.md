# Performance Troubleshooting

## Performance Issues

### Symptom: High CPU usage

**Identify process:**

```bash
docker stats --no-stream

# High CPU in which container?
# Backend (simulator updates too frequent?)
# Prometheus (too much data, slow query?)
# Grafana (dashboard rendering?)
```

**Backend high CPU:**

```bash
# Check update interval in .env or config
rg "update_interval" backend/starlink-location/config.yaml

# Increase it (less frequent updates)
docker compose exec starlink-location sed -i 's/update_interval_seconds: 0.1/update_interval_seconds: 1.0/' /app/config.yaml
docker compose restart starlink-location
```

**Prometheus high CPU:**

```bash
# Reduce retention
PROMETHEUS_RETENTION=7d
docker compose down && docker compose up -d

# Or reduce scrape frequency
# Edit monitoring/prometheus/prometheus.yml
# Change scrape_interval from 10s to 30s
```

### Symptom: High memory usage

**Check memory consumption:**

```bash
docker stats --no-stream

# Identify which container
docker stats <container-name>
```

**Reduce Prometheus data:**

```bash
# Lower retention period
PROMETHEUS_RETENTION=15d
docker compose down && docker compose up -d
```

**Restart to clear memory:**

```bash
docker compose down
docker system prune -a  # Remove unused images
docker compose up -d
```

### Symptom: Slow dashboard loading

**Check query performance:**

```bash
# Open Prometheus
open http://localhost:9090/graph

# Run a query and check execution time
# Enter: starlink_dish_latitude_degrees[5m]
# Click Execute
# Shows query time at bottom
```

**Optimize if slow:**

```bash
# If > 1 second, either:
# 1. Reduce time range (less data)
# 2. Reduce Prometheus retention
# 3. Increase system resources
```

## Related Documentation

- [Quick Diagnostics](./quick-diagnostics.md)
- [Backend Issues](./backend-issues.md)
- [Data Issues](./data-issues.md)
- [API Reference](../API-REFERENCE.md)
- [Setup Guide](../SETUP-GUIDE.md)
