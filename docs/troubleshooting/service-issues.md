# Troubleshooting Service Issues

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Prometheus Issues

### Symptom: Prometheus not collecting metrics

**Check Prometheus targets:**

```bash
# Open browser
open http://localhost:9090/targets
# Or use curl
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'
```

**Verify backend is reachable:**

```bash
# From Prometheus container
docker compose exec prometheus curl http://starlink-location:8000/health

# From host
curl http://localhost:8000/health
```

**Check scrape config:**

```bash
# View prometheus.yml
cat monitoring/prometheus/prometheus.yml

# Verify backend URL is correct
rg "static_configs:" -A 3 monitoring/prometheus/prometheus.yml
```

### Issue: "Failed to reload config"

```bash
# Check YAML syntax
docker run --rm -v $(pwd)/monitoring/prometheus:/config \
  prom/prometheus:latest \
  promtool check config /config/prometheus.yml

# Fix errors and restart
docker compose restart prometheus
```

### Issue: High disk usage

**Check storage:**

```bash
# Size of prometheus volume
docker volume inspect prometheus_data
# Or see size
du -sh /var/lib/docker/volumes/starlink-dashboard-dev_prometheus_data

# Reduce retention in .env
PROMETHEUS_RETENTION=15d  # Instead of 1y
docker compose down
docker compose up -d

# Check if cleaning up
docker compose logs prometheus | tail -20
```

## Grafana Issues

### Symptom: Can't access Grafana

**Verify container running:**

```bash
docker compose ps grafana

# Check logs
docker compose logs grafana

# Verify port
curl http://localhost:3000
```

### Issue: "Data source not working"

**Test data source connection:**

1. Go to <http://localhost:3000>
2. Settings > Data Sources > Prometheus
3. Click "Test" button
4. Should see green "Data source is working"

**If test fails:**

```bash
# Check if Prometheus is running
docker compose ps prometheus

# Test from Grafana container
docker compose exec grafana curl http://prometheus:9090
```

### Issue: Dashboards empty or no data

**Verify data exists:**

```bash
# Check Prometheus has data
curl http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees

# Should return something like:
# "result": [{"metric": {...}, "value": ["timestamp", "40.7128"]}]

# If empty, backend may not be exporting metrics
curl http://localhost:8000/metrics | rg starlink_dish_latitude
```

**Reload dashboards:**

```bash
# Go to http://localhost:3000
# Click refresh icon in browser
# Or restart grafana
docker compose restart grafana
```

### Issue: "Templating initialization failed"

```bash
# Check logs
docker compose logs grafana | rg -i "template"

# Clear Grafana cache
docker compose exec grafana rm -rf /var/lib/grafana/cache

# Restart
docker compose restart grafana
```

### Issue: Can't change password

```bash
# Reset admin password via API
docker compose exec grafana grafana-cli admin reset-admin-password newpassword

# Or reset via container shell
docker compose exec grafana /bin/bash
# Inside container:
grafana-cli admin reset-admin-password newpassword
```

## Network & Connectivity

### Symptom: Services can't communicate

**Verify network connectivity:**

```bash
# Check if containers can reach each other
docker compose exec starlink-location curl http://prometheus:9090
docker compose exec prometheus curl http://starlink-location:8000/health
docker compose exec grafana curl http://prometheus:9090
```

**Check network configuration:**

```bash
# View network
docker network inspect starlink-dashboard-dev_starlink-net

# Verify all containers connected
docker network inspect starlink-dashboard-dev_starlink-net | rg -A 10 "Containers"
```

### Symptom: Live mode won't connect to dish

**Test network connectivity:**

```bash
# From host
ping 192.168.100.1
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && echo "Connection OK" || echo "Connection failed"

# From container
docker compose exec starlink-location ping -c 3 192.168.100.1
docker compose exec starlink-location timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && echo "OK" || echo "Failed"
```

**Check network mode:**

```bash
# Verify bridge vs host mode
docker inspect starlink-location | rg -A 2 NetworkMode

# For bridge mode, check extra_hosts
docker inspect starlink-location | rg -A 5 extra_hosts
```

**Update IP if needed:**

```bash
# Edit .env
nano .env
STARLINK_DISH_HOST=<your-actual-ip>

# Restart
docker compose down
docker compose up -d
```

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
