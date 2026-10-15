# Metrics & Monitoring Troubleshooting

This guide covers Prometheus and Mission Planner issues related to metrics
collection and visualization.

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
