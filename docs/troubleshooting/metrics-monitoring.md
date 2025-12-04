# Metrics & Monitoring Troubleshooting

This guide covers Prometheus and Grafana issues related to metrics collection
and visualization.

## Prometheus Issues

### Prometheus Not Collecting Metrics

**Check Prometheus targets:**

```bash
# Open browser
open <http://localhost:9090/targets>
# Or use curl
curl <http://localhost:9090/api/v1/targets> | jq '.data.activeTargets'
```

**Verify backend is reachable:**

```bash
# From Prometheus container
docker compose exec prometheus curl <http://starlink-location:8000/health>

# From host
curl <http://localhost:8000/health>
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

### High Disk Usage

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

### Can't Access Grafana

**Verify container running:**

```bash
docker compose ps grafana

# Check logs
docker compose logs grafana

# Verify port
curl <http://localhost:3000>
```

### Issue: "Data source not working"

**Test data source connection:**

1. Go to <<http://localhost:3000>>
2. Settings > Data Sources > Prometheus
3. Click "Test" button
4. Should see green "Data source is working"

**If test fails:**

```bash
# Check if Prometheus is running
docker compose ps prometheus

# Test from Grafana container
docker compose exec grafana curl <http://prometheus:9090>
```

### Dashboards Empty

**Verify data exists:**

```bash
# Check Prometheus has data
curl <http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees>

# Should return something like:
# "result": [{"metric": {...}, "value": ["timestamp", "40.7128"]}]

# If empty, backend may not be exporting metrics
curl <http://localhost:8000/metrics> | rg starlink_dish_latitude
```

**Reload dashboards:**

```bash
# Go to <http://localhost:3000>
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

### Can't Change Password

```bash
# Reset admin password via API
docker compose exec grafana grafana-cli admin reset-admin-password newpassword

# Or reset via container shell
docker compose exec grafana /bin/bash
# Inside container:
grafana-cli admin reset-admin-password newpassword
```
