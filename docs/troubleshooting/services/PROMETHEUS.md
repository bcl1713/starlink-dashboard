# Prometheus Troubleshooting

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
