# Metrics Health Monitoring

**See also:** [Metrics Overview](./overview.md) |
[Troubleshooting](./troubleshooting.md)

---

## Health Endpoint

The `/health` endpoint returns:

```json
{
  "status": "ok",
  "uptime_seconds": 3600.5,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2024-10-23T16:30:00.000000",
  "prometheus_last_scrape": "2024-10-23T16:29:50.000000",
  "metrics_count": 45,
  "detail": null
}
```

**Status values:**

- `"ok"`: Prometheus is actively scraping (last scrape < 30 seconds ago)
- `"degraded"`: Prometheus hasn't scraped in > 30 seconds (includes initial
  startup)

---

## Prometheus Scrape Status

### Check if Prometheus is Scraping

```promql
# Check if Prometheus is scraping the endpoint
time() - starlink_metrics_last_update_timestamp_seconds < 30

# Alert if metrics collection is stalled (no update for 2 minutes)
ALERT MetricsCollectionStalled IF time() - starlink_metrics_last_update_timestamp_seconds > 120
```

---

## Health Monitoring Queries

### Service Health

```promql
# Is metrics collection active? (should be 1 for healthy systems)
time() - starlink_metrics_last_update_timestamp_seconds < 30

# Metrics generation error rate
rate(starlink_metrics_generation_errors_total[1h])

# Metric collection duration (should be < 5 seconds)
starlink_metrics_scrape_duration_seconds
```

### Network Health

```promql
# Current latency
starlink_network_latency_ms_current

# Connection failure rate
rate(starlink_connection_failures_total[1h]) / rate(starlink_connection_attempts_total[1h])

# Active outage
starlink_dish_outage_active
```

### System Health

```promql
# Service uptime
starlink_uptime_seconds

# Dish uptime
starlink_dish_uptime_seconds

# Thermal throttle active
starlink_dish_thermal_throttle
```

---

## Grafana Dashboard Integration

All metrics are automatically available in Grafana dashboards. Use the
Prometheus data source at `http://prometheus:9090` to create visualizations:

- **Gauges:** Position, altitude, speed, heading, network performance
- **Graphs:** Throughput trends, latency over time, obstruction changes
- **Heatmaps:** Latency distribution by status
- **Stat panels:** Current uptime, last scrape time, error counts

---

## Alert Rules

### Recommended Alerts

```yaml
groups:
  - name: starlink_alerts
    rules:
      - alert: MetricsCollectionStalled
        expr: time() - starlink_metrics_last_update_timestamp_seconds > 120
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Metrics collection has stalled"
          description: "No metrics updates in {{ $value }} seconds"

      - alert: HighLatency
        expr: starlink_network_latency_ms_current > 200
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High network latency detected"
          description: "Latency is {{ $value }}ms"

      - alert: DishOutage
        expr: starlink_dish_outage_active == 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dish outage active"

      - alert: ThermalThrottle
        expr: starlink_dish_thermal_throttle == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dish is thermally throttled"
```

---

## See Also

- [Metrics Overview](./overview.md) - Complete metrics reference
- [Troubleshooting](./troubleshooting.md) - Common issues and solutions
