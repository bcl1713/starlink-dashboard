# Starlink Dashboard Troubleshooting Guide

**Last Updated:** 2025-10-31 **Version:** 0.2.0

## Quick Diagnostics

Before diving into specific issues, run these checks:

```bash
# 1. Check all services running
docker compose ps

# 2. Check backend health
curl <http://localhost:8000/health>

# 3. Check logs for errors
docker compose logs --tail=50

# 4. Check resource usage
docker stats --no-stream
```

---

## Table of Contents

1. [Service Won't Start](#service-wont-start)
2. [Port Conflicts](#port-conflicts)
3. [Backend Issues](#backend-issues)
4. [Prometheus Issues](#prometheus-issues)
5. [Grafana Issues](#grafana-issues)
6. [Network & Connectivity](#network--connectivity)
7. [Data & Storage Issues](#data--storage-issues)
8. [Performance Issues](#performance-issues)
9. [Live Mode Issues](#live-mode-issues)
10. [POI Management Issues](#poi-management-issues)

---

## Service Won't Start

### Symptom: Container exits immediately

**Check logs:**

```bash
docker compose logs starlink-location
docker compose logs prometheus
docker compose logs grafana
```

**Common Causes & Solutions:**

#### 1. Configuration Error

```bash
# Check syntax of .env
cat .env | grep -E "^[A-Z_]+=.*"

# Rebuild without cache
docker compose down
docker compose build --no-cache
docker compose up -d
```

#### 2. Port Binding Failed

```bash
# Find what's using the port
lsof -i :8000  # Backend
lsof -i :9090  # Prometheus
lsof -i :3000  # Grafana

# Kill process or change port in .env
kill -9 <PID>
```

#### 3. Insufficient Disk Space

```bash
# Check available space
df -h

# If < 5 GB free:
docker system prune -a  # Remove unused images
docker volume prune      # Remove unused volumes
```

#### 4. Memory Issues

```bash
# Check system memory
free -h
docker stats --no-stream

# Stop other services or increase swap
docker compose down
# Stop unnecessary apps
docker compose up -d
```

### Symptom: "Failed to connect to Docker daemon"

```bash
# Ensure Docker is running
sudo systemctl status docker  # Linux
# or check Docker Desktop (macOS/Windows)

# Start Docker
sudo systemctl start docker
```

---

## Port Conflicts

### Symptom: "Address already in use"

**Find process using port:**

```bash
# Linux/macOS
lsof -i :3000
lsof -i :8000
lsof -i :9090

# Windows
netstat -ano | findstr :3000
```

#### Solution 1: Kill process

```bash
# Linux/macOS
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

#### Solution 2: Change port in .env

```bash
# Edit .env
nano .env

# Change port
GRAFANA_PORT=3001
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091

# Restart
docker compose down
docker compose up -d
```

#### Solution 3: Check if service is running

```bash
# See what's actually bound to the port
netstat -tlnp | grep 3000  # Linux
lsof -i :3000              # macOS
netstat -ano | findstr 3000 # Windows

# If it's Docker, just restart it
docker compose restart
```

---

## Backend Issues

### Symptom: Backend unhealthy or crashing

**Check health endpoint:**

```bash
curl -v <http://localhost:8000/health>
# Should return 200 with {"status": "ok"}

# Check extended info
curl <http://localhost:8000/health> | jq .
```

**View logs:**

```bash
docker compose logs -f starlink-location
# Look for errors or warnings

# Check last 100 lines
docker compose logs --tail=100 starlink-location | grep -i error
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
docker compose config | grep STARLINK
```

### Issue: Metrics not updating

**Verify data is being generated:**

```bash
# Check API status endpoint
curl <http://localhost:8000/api/status> | jq '.position'

# Check raw metrics
curl <http://localhost:8000/metrics> | grep "starlink_dish_" | head -5

# Check update frequency
# Should see changes every 1 second
for i in {1..3}; do curl -s <http://localhost:8000/api/status> | jq '.position.latitude'; sleep 1; done
```

**If no updates:**

```bash
# Rebuild backend
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d

# Check logs for simulation errors
docker compose logs starlink-location | grep -i "simulation\|error"
```

### Issue: "Simulation coordinator not initialized"

```bash
# Check startup logs
docker compose logs starlink-location | head -50

# Restart service
docker compose restart starlink-location

# Wait 10 seconds and check health
sleep 10
curl <http://localhost:8000/health>
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

---

## Prometheus Issues

### Symptom: Prometheus not collecting metrics

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
grep "static_configs:" -A 3 monitoring/prometheus/prometheus.yml
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

---

## Grafana Issues

### Symptom: Can't access Grafana

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

1. Go to <http://localhost:3000>
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

### Issue: Dashboards empty or no data

**Verify data exists:**

```bash
# Check Prometheus has data
curl <http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees>

# Should return something like:
# "result": [{"metric": {...}, "value": ["timestamp", "40.7128"]}]

# If empty, backend may not be exporting metrics
curl <http://localhost:8000/metrics> | grep starlink_dish_latitude
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
docker compose logs grafana | grep -i "template"

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

---

## Network & Connectivity

### Symptom: Services can't communicate

**Verify network connectivity:**

```bash
# Check if containers can reach each other
docker compose exec starlink-location curl <http://prometheus:9090>
docker compose exec prometheus curl <http://starlink-location:8000/health>
docker compose exec grafana curl <http://prometheus:9090>
```

**Check network configuration:**

```bash
# View network
docker network inspect starlink-dashboard-dev_starlink-net

# Verify all containers connected
docker network inspect starlink-dashboard-dev_starlink-net | grep -A 10 "Containers"
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
docker inspect starlink-location | grep -A 2 NetworkMode

# For bridge mode, check extra_hosts
docker inspect starlink-location | grep -A 5 extra_hosts
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

---

## Data & Storage Issues

### Symptom: POI list empty or missing

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

### Issue: Can't create/edit POIs

**Check API:**

```bash
# Test POI creation
curl -X POST <http://localhost:8000/api/pois> \
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

### Symptom: Data not persisting after restart

**Verify volumes mounted:**

```bash
# Check volume mounts in docker-compose.yml
grep -A 5 "volumes:" docker-compose.yml

# Verify volume exists
docker volume ls | grep poi
docker volume ls | grep prometheus
docker volume ls | grep grafana

# Check volume content
docker run -v poi_data:/data alpine ls -la /data
```

---

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
grep "update_interval" backend/starlink-location/config.yaml

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
open <http://localhost:9090/graph>

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

---

## Live Mode Issues

### Symptom: "Live mode: waiting for dish connection"

**This is normal!** The system is designed to wait for the dish.

**Verify dish status:**

```bash
# Check health endpoint
curl <http://localhost:8000/health> | jq '.dish_connected'

# Should be false initially, true when connected

# Monitor connection attempts
docker compose logs -f starlink-location | grep -i "dish\|connect"
```

**Troubleshoot connection:**

1. **Verify dish IP:**

   ```bash
   ping 192.168.100.1
   # If not reachable, update .env with correct IP
   ```

1. **Check network mode:**

   ```bash
   # Bridge mode (cross-platform)
   docker inspect starlink-location | grep -A 5 extra_hosts

   # Host mode (Linux only)
   docker inspect starlink-location | grep NetworkMode
   ```

1. **Test from container:**

   ```bash
   docker compose exec starlink-location \
     timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.100.1/9200'
   # Should succeed if reachable
   ```

1. **Check firewall:**

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
  curl -s <http://localhost:8000/api/status> | jq '.timestamp'
  sleep 2
done

# Timestamps should change

# If stuck, check logs
docker compose logs starlink-location | grep -i "error\|fail"

# May need to reconnect
docker compose restart starlink-location
```

---

## POI Management Issues

### Issue: ETA calculations incorrect

**Verify POI coordinates:**

```bash
# List POIs
curl <http://localhost:8000/api/pois> | jq '.[] | {name, latitude, longitude}'

# Manually calculate distance
# Using Haversine formula to NYC (40.7128, -74.0060)

# Verify ETAs
curl <http://localhost:8000/api/pois/etas> | jq '.[] | {name, distance_meters, eta_seconds}'
```

**Check speed used in calculation:**

```bash
# If not specified, uses fallback 67 knots
# To use current speed:
curl "<http://localhost:8000/api/pois/etas?speed_knots=50">
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
curl <http://localhost:8000/api/pois/etas> | jq length
# Should return count of POIs

# Test Infinity query manually
# In Grafana > Explore
# Set Data source to Infinity
# Enter URL: <http://starlink-location:8000/api/pois/etas>
# Click Run Query
```

---

## Debug Logging

### Enable debug mode

```bash
# Edit .env
LOG_LEVEL=DEBUG
JSON_LOGS=true

# Restart
docker compose down
docker compose up -d

# View detailed logs
docker compose logs -f starlink-location
```

### View all component logs

```bash
# All services
docker compose logs -f

# Specific service with timestamps
docker compose logs -f --timestamps starlink-location

# Last N lines
docker compose logs --tail=100 starlink-location

# Search for errors
docker compose logs | grep -i "error"
```

### Save logs to file

```bash
# Save all logs
docker compose logs > logs.txt

# Save specific service logs
docker compose logs starlink-location > backend.log
docker compose logs prometheus > prometheus.log
docker compose logs grafana > grafana.log
```

---

## Getting Help

### Before asking for help, gather

1. **Log output:**

   ```bash
   docker compose logs > debug-logs.txt
   ```

1. **System info:**

   ```bash
   docker --version
   docker compose version
   uname -a
   ```

1. **Configuration:**

   ```bash
   cat .env | grep -v "PASSWORD"
   docker compose config | head -50
   ```

1. **Current state:**

   ```bash
   docker compose ps
   docker stats --no-stream
   curl <http://localhost:8000/health>
   curl <http://localhost:9090/api/v1/targets>
   ```

### Resources

- [API Reference](./API-REFERENCE.md)
- [Setup Guide](./SETUP-GUIDE.md)
- [Design Document](./design-document.md)
- [Backend README](../backend/starlink-location/README.md)
- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## Still Need Help?

Check:

1. Related documentation files
2. Backend/Prometheus/Grafana container logs
3. System resource usage
4. Network connectivity between containers
5. File permissions and permissions
6. .env configuration values
7. Docker version compatibility
