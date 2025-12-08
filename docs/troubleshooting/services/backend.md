# Troubleshooting Backend Issues

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Backend Issues

### Symptom: Backend unhealthy or crashing

**Check health endpoint:**

```bash
curl -v http://localhost:8000/health
# Should return 200 with {"status": "ok"}

# Check extended info
curl http://localhost:8000/health | jq .
```

**View logs:**

```bash
docker compose logs -f starlink-location
# Look for errors or warnings

# Check last 100 lines
docker compose logs --tail=100 starlink-location | rg -i error
```

### Issue: "Cannot load configuration"

```bash
# Check config file exists
ls -la backend/starlink-location/config.yaml

# Check JSON files
ls -la backend/starlink-location/data/

# Validate YAML syntax
cat backend/starlink-location/config.yaml | head -20

# Check environment variables
docker compose config | rg STARLINK
```

### Issue: Metrics not updating

**Verify data is being generated:**

```bash
# Check API status endpoint
curl http://localhost:8000/api/status | jq '.position'

# Check raw metrics
curl http://localhost:8000/metrics | rg "starlink_dish_" | head -5

# Check update frequency
# Should see changes every 1 second
for i in {1..3}; do curl -s http://localhost:8000/api/status | jq '.position.latitude'; sleep 1; done
```

**If no updates:**

```bash
# Rebuild backend
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d

# Check logs for simulation errors
docker compose logs starlink-location | rg -i "simulation|error"
```

### Issue: "Simulation coordinator not initialized"

```bash
# Check startup logs
docker compose logs starlink-location | head -50

# Restart service
docker compose restart starlink-location

# Wait 10 seconds and check health
sleep 10
curl http://localhost:8000/health
```

### Issue: POI file locked or inaccessible

```bash
# Check file permissions
ls -la backend/starlink-location/data/pois.json

# Fix if needed
docker compose exec starlink-location chmod 666 /app/data/pois.json

# Or reset file
docker compose exec starlink-location sh -c 'echo "[]" > /app/data/pois.json'
```

## Live Mode Issues

### Symptom: "Live mode: waiting for dish connection"

**This is normal!** The system is designed to wait for the dish.

**Verify dish status:**

```bash
# Check health endpoint
curl http://localhost:8000/health | jq '.dish_connected'

# Should be false initially, true when connected

# Monitor connection attempts
docker compose logs -f starlink-location | rg -i "dish|connect"
```

**Troubleshoot connection:**

1. **Verify dish IP:**

   ```bash
   ping 192.168.100.1
   # If not reachable, update .env with correct IP
   ```

2. **Check network mode:**

   ```bash
   # Bridge mode (cross-platform)
   docker inspect starlink-location | rg -A 5 extra_hosts

   # Host mode (Linux only)
   docker inspect starlink-location | rg NetworkMode
   ```

3. **Test from container:**

   ```bash
   docker compose exec starlink-location \
     timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.100.1/9200'
   # Should succeed if reachable
   ```

4. **Check firewall:**

   ```bash
   # Linux: check firewall rules
   sudo ufw status
   sudo ufw allow 9200

   # macOS: System Preferences > Security & Privacy > Firewall
   # Windows: Settings > Windows Defender Firewall
   ```

### Symptom: Metrics from live mode appear stale

```bash
# Check update frequency
for i in {1..5}; do
  curl -s http://localhost:8000/api/status | jq '.timestamp'
  sleep 2
done

# Timestamps should change

# If stuck, check logs
docker compose logs starlink-location | rg -i "error|fail"

# May need to reconnect
docker compose restart starlink-location
```

## POI Management Issues

### Issue: ETA calculations incorrect

**Verify POI coordinates:**

```bash
# List POIs
curl http://localhost:8000/api/pois | jq '.[] | {name, latitude, longitude}'

# Manually calculate distance
# Using Haversine formula to NYC (40.7128, -74.0060)

# Verify ETAs
curl http://localhost:8000/api/pois/etas | jq '.[] | {name, distance_meters, eta_seconds}'
```

**Check speed used in calculation:**

```bash
# If not specified, uses fallback 67 knots
# To use current speed:
curl "http://localhost:8000/api/pois/etas?speed_knots=50"
```

### Issue: POI table not updating in Grafana

**Verify Infinity datasource:**

```bash
# Check datasource configured
# Grafana > Settings > Data Sources
# Should have "Infinity" datasource

# If missing, add it:
# Name: Infinity
# Type: Infinity
# No other settings needed
```

**Check POI endpoint:**

```bash
# Verify endpoint accessible
curl http://localhost:8000/api/pois/etas | jq length
# Should return count of POIs

# Test Infinity query manually
# In Grafana > Explore
# Set Data source to Infinity
# Enter URL: http://starlink-location:8000/api/pois/etas
# Click Run Query
```

## Related Documentation

- [Quick Diagnostics](../quick-diagnostics.md)
- [Service Issues](../service-issues.md)
- [Data Issues](../data-issues.md)
- [API Reference](../../api/README.md)
- [Setup Guide](../../setup/README.md)
