# Docker Services Troubleshooting

This guide covers Docker-related issues including service startup, port
conflicts, and backend problems.

## Container Exits Immediately

### Check logs

```bash
docker compose logs starlink-location
docker compose logs prometheus
docker compose logs grafana
```

### Common Causes & Solutions

#### 1. Configuration Error

```bash
# Check syntax of .env
cat .env | rg -E "^[A-Z_]+=.*"

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

## Failed to Connect to Docker Daemon

```bash
# Ensure Docker is running
sudo systemctl status docker  # Linux
# or check Docker Desktop (macOS/Windows)

# Start Docker
sudo systemctl start docker
```

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

### Solution 1: Kill process

```bash
# Linux/macOS
kill -9 <PID>

# Windows
taskkill /PID <PID> /F
```

### Solution 2: Change port in .env

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

### Solution 3: Check if service is running

```bash
# See what's actually bound to the port
netstat -tlnp | rg 3000  # Linux
lsof -i :3000              # macOS
netstat -ano | findstr 3000 # Windows

# If it's Docker, just restart it
docker compose restart
```

## Backend Issues

### Backend Unhealthy or Crashing

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
docker compose logs --tail=100 starlink-location | \
  rg -i error
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

### Metrics Not Updating

**Verify data is being generated:**

```bash
# Check API status endpoint
curl <http://localhost:8000/api/status> | jq '.position'

# Check raw metrics
curl <http://localhost:8000/metrics> | rg "starlink_dish_" | head -5

# Check update frequency
# Should see changes every 1 second
for i in {1..3}; do
  curl -s <http://localhost:8000/api/status> | jq '.position.latitude'
  sleep 1
done
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
