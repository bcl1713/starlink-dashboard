# Metrics Troubleshooting

**See also:** [Metrics Overview](./overview.md) |
[Health Monitoring](./health-monitoring.md)

---

## Metrics Not Appearing

### Missing Metrics Symptoms

- Grafana shows "No data"
- Prometheus targets show "down"
- Health endpoint returns empty metrics count

### Missing Metrics Diagnosis

1. Check if backend is running:

   ```bash
   curl http://localhost:8000/health
   ```

2. Check metrics endpoint:

   ```bash
   curl http://localhost:8000/metrics
   ```

3. Check Prometheus targets:

   ```bash
   open http://localhost:9090/targets
   ```

4. Check last scrape time:

   ```bash
   curl http://localhost:8000/health | jq .prometheus_last_scrape
   ```

### Missing Metrics Solutions

**Backend not responding:**

```bash
docker compose ps
docker compose logs starlink-location
docker compose restart starlink-location
```

**Prometheus not scraping:**

```bash
docker compose logs prometheus
# Check prometheus.yml configuration
cat monitoring/prometheus/prometheus.yml
```

---

## High Latency or Packet Loss

### Using Status Labels

Filter metrics by network quality status:

```promql
# Queries when network is degraded
starlink_network_latency_ms{status="degraded"}
starlink_network_throughput_down_mbps{status="poor"}
```

### Performance Analysis

```promql
# 95th percentile latency over time
histogram_quantile(0.95, rate(starlink_network_latency_ms_bucket[5m]))

# Connection failure rate
rate(starlink_connection_failures_total[1h]) / rate(starlink_connection_attempts_total[1h])
```

---

## Memory Usage Concerns

### Check Collection Performance

Meta-metrics help identify collection issues:

```promql
# Collection duration (should be < 1 second typically)
starlink_metrics_scrape_duration_seconds

# Is collection healthy?
rate(starlink_metrics_generation_errors_total[5m]) == 0
```

### Reduce Memory Usage

1. **Reduce retention period** in `.env`:

   ```bash
   PROMETHEUS_RETENTION=7d  # Instead of 1y
   ```

2. **Increase scrape interval** in `.env`:

   ```bash
   PROMETHEUS_SCRAPE_INTERVAL=30s  # Instead of 10s
   ```

3. **Restart services:**

   ```bash
   docker compose down
   docker compose up -d
   ```

---

## Stale Metrics

### Stale Metrics Symptoms

- Metrics show old timestamps
- `starlink_metrics_last_update_timestamp_seconds` is stale

### Stale Metrics Diagnosis

```promql
# Check how old the last update is
time() - starlink_metrics_last_update_timestamp_seconds
```

### Stale Metrics Solutions

```bash
# Restart backend service
docker compose restart starlink-location

# Check logs for errors
docker compose logs -f starlink-location
```

---

## Missing POI Metrics

### POI Metrics Symptoms

- No `starlink_eta_poi_seconds` metrics
- No `starlink_distance_to_poi_meters` metrics

### POI Metrics Cause

POIs haven't been created yet.

### POI Metrics Solutions

1. **Create POIs via UI:**

   ```bash
   open http://localhost:8000/ui/pois
   ```

2. **Create POIs via API:**

   ```bash
   curl -X POST http://localhost:8000/api/pois \
     -H "Content-Type: application/json" \
     -d '{
       "name": "NYC",
       "latitude": 40.7128,
       "longitude": -74.0060
     }'
   ```

3. **Verify POI metrics:**

   ```bash
   curl http://localhost:8000/metrics | grep poi
   ```

---

## Grafana Shows No Data

### Checking Grafana Data Source

1. Go to <http://localhost:3000>
2. Configuration → Data Sources → Prometheus
3. Click "Test" button
4. Should show green "Data source is working"

### When Data Source Test Fails

```bash
# Check if Prometheus is running
docker compose ps prometheus

# Test from Grafana container
docker compose exec grafana curl http://prometheus:9090
```

### Verifying Grafana Queries

In Grafana dashboard, check PromQL queries:

```promql
# Simple test query
starlink_service_info

# If this works, issue is with specific query
starlink_dish_latitude_degrees
```

---

## High Cardinality Warnings

### Cardinality Warning Symptoms

- Prometheus logs show "series churn" warnings
- Memory usage increases over time

### Cardinality Warning Cause

Too many unique label combinations (especially POI names).

### Cardinality Warning Solutions

1. **Limit POI count** - Keep under 100 POIs
2. **Use consistent naming** - Avoid dynamic POI names
3. **Increase Prometheus memory:**

   ```yaml
   # In docker-compose.yml
   prometheus:
     command:
       - "--storage.tsdb.retention.time=15d"
       - "--storage.tsdb.retention.size=2GB"
   ```

---

## Simulation Metrics Not Updating

### Simulation Update Symptoms

- `simulation_updates_total` not increasing
- Position metrics frozen

### Simulation Update Diagnosis

```bash
# Check simulation errors
curl http://localhost:8000/metrics | grep simulation_errors_total

# Check backend logs
docker compose logs -f starlink-location
```

### Simulation Update Solutions

```bash
# Verify simulation mode enabled
grep STARLINK_MODE .env
# Should show: STARLINK_MODE=simulation

# Restart services
docker compose restart starlink-location
```

---

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Troubleshooting](https://grafana.com/docs/grafana/latest/troubleshooting/)
