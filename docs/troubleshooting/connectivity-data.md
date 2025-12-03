# Connectivity, Data & Performance Troubleshooting

This guide covers network connectivity, live mode issues, data storage, POI
management, and performance optimization.

## Network & Connectivity

### Services Can't Communicate

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

### Live Mode Won't Connect to Dish

**Test network connectivity:**

```bash
# From host
ping 192.168.100.1
timeout 5 bash -c \
  'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && \
  echo "Connection OK" || echo "Connection failed"

# From container
docker compose exec starlink-location ping -c 3 192.168.100.1
docker compose exec starlink-location \
  timeout 5 bash -c \
  'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && \
  echo "OK" || echo "Failed"
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
     timeout 5 bash -c \
     'cat < /dev/null > /dev/tcp/192.168.100.1/9200'
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

### Metrics from Live Mode Appear Stale

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

## Data & Storage Issues

### POI List Empty or Missing

**Check POI file:**

```bash
# File exists?
ls -la backend/starlink-location/data/pois.json

# Content valid?
cat backend/starlink-location/data/pois.json | jq .

# If corrupted, reset
echo '[]' > backend/starlink-location/data/pois.json
docker compose restart starlink-location
```

### Can't Create/Edit POIs

**Check API:**

```bash
# Test POI creation
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "latitude": 40.7, "longitude": -74.0}'

# Check response for errors
# If 500 error, check backend logs:
docker compose logs starlink-location | tail -20
```

**Check file permissions:**

```bash
# POI file writable?
docker compose exec starlink-location ls -la /app/data/pois.json

# Fix if needed
docker compose exec starlink-location chmod 666 /app/data/pois.json
```

### Data Not Persisting After Restart

**Verify volumes mounted:**

```bash
# Check volume mounts in docker-compose.yml
rg -A 5 "volumes:" docker-compose.yml

# Verify volume exists
docker volume ls | rg poi
docker volume ls | rg prometheus
docker volume ls | rg grafana

# Check volume content
docker run -v poi_data:/data alpine ls -la /data
```

## POI Management Issues

### ETA Calculations Incorrect

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

### POI Table Not Updating in Grafana

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

## Performance Issues

### High CPU Usage

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
docker compose exec starlink-location sed -i \
  's/update_interval_seconds: 0.1/update_interval_seconds: 1.0/' \
  /app/config.yaml
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

### High Memory Usage

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

### Slow Dashboard Loading

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
