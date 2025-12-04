# Grafana Troubleshooting

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
