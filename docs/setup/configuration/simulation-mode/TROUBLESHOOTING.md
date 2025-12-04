# Troubleshooting & Best Practices

## Troubleshooting

### Position Not Updating

**Symptoms:**

- Position stays the same
- Metrics show stale data

**Solutions:**

1. **Check backend is running:**

   ```bash
   docker compose ps starlink-location
   ```

2. **Check logs for errors:**

   ```bash
   docker compose logs starlink-location | rg -i "error|simulation"
   ```

3. **Restart backend:**

   ```bash
   docker compose restart starlink-location
   ```

4. **Rebuild if needed:**

   ```bash
   docker compose down
   docker compose build --no-cache starlink-location
   docker compose up -d
   ```

### Metrics Not Appearing in Prometheus

**Symptoms:**

- Prometheus shows no data
- Grafana dashboards empty

**Solutions:**

1. **Check backend metrics endpoint:**

   ```bash
   curl http://localhost:8000/metrics | rg starlink_
   ```

2. **Check Prometheus targets:**

   ```bash
   curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets'
   ```

3. **Verify Prometheus is scraping:**

   ```bash
   docker compose logs prometheus | rg -i "scrape\|target"
   ```

### Unrealistic Data

**Symptoms:**

- Speed too high/low
- Position jumps
- Metrics don't make sense

**Solutions:**

- Check if custom route has timing data
- Verify KML file format is correct
- Review simulation config.yaml parameters
- Restart with default circular route

---

## Best Practices

### Development

```bash
# .env for development
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=7d
LOG_LEVEL=DEBUG
JSON_LOGS=false
```

**Why:**

- Quick iteration
- Verbose logging for debugging
- Minimal storage footprint
- Human-readable logs

### Testing

```bash
# .env for testing
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=1d
LOG_LEVEL=INFO
```

**Why:**

- Predictable behavior
- Automated testing friendly
- Fast cleanup

### Demonstrations

```bash
# .env for demos
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=15d
LOG_LEVEL=INFO
JSON_LOGS=true
```

**Why:**

- Professional log format
- Enough retention for demo review
- Realistic simulation behavior
