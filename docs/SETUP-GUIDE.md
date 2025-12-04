# Starlink Dashboard Setup Guide

**Last Updated:** 2025-10-31 **Project Version:** 0.2.0

## Quick Navigation

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Simulation Mode Setup](#simulation-mode-setup)
- [Live Mode Setup](#live-mode-setup)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

- **Docker:** Version 20.10 or higher

  ```bash
  docker --version  # Should be >= 20.10
  ```

- **Docker Compose:** Version 2.0 or higher

  ```bash
  docker compose version  # Should be >= 2.0
  ```

- **Git:** For version control

  ```bash
  git --version
  ```

- **Disk Space:** Minimum 5 GB
  - ~2.4 GB for 1 year of Prometheus metrics (configurable)
  - ~1 GB for Docker images
  - ~1 GB for development/caching

- **Memory:** Minimum 4 GB RAM
  - Grafana: ~150 MB
  - Prometheus: ~200 MB
  - Backend: ~100-150 MB
  - Docker overhead: ~500 MB

- **Network:** Internet access for pulling Docker images

### OS-Specific Notes

**Linux:**

- ✅ Full feature support including host network mode
- Firewall may need port 3000, 8000, 9090 open

**macOS (Intel or Apple Silicon):**

- ✅ Full feature support via Docker Desktop
- Uses bridge network mode (cross-platform compatible)

**Windows:**

- ✅ Full feature support via Docker Desktop
- WSL 2 recommended for better performance
- Uses bridge network mode (cross-platform compatible)

---

## Installation

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone <https://github.com/your-repo/starlink-dashboard.git>
cd starlink-dashboard

# Verify directory structure
ls -la
# You should see: backend/, docs/, monitoring/, docker-compose.yml, .env.example
```

### Step 2: Create Environment File

```bash
# Copy the example environment file
cp .env.example .env

# View the configuration
cat .env

# Edit as needed for your setup
nano .env
```

### Step 3: Build Docker Images

```bash
# Build all services (first time may take 2-3 minutes)
docker compose build

# Verify build success
docker compose images
```

### Step 4: Start Services

```bash
# Start all services in background
docker compose up -d

# Verify services are running
docker compose ps
```

**Expected output:**

```text
CONTAINER ID   IMAGE                        STATUS
xxxxx          starlink-location:latest     Up 2 seconds (healthy)
xxxxx          prom/prometheus:latest       Up 3 seconds
xxxxx          grafana/grafana:latest       Up 4 seconds
```

### Step 5: Verify Services

```bash
# Check backend health
curl <http://localhost:8000/health>

# View container logs (useful for debugging)
docker compose logs -f
```

---

## Simulation Mode Setup

**Default Mode** - No hardware required, perfect for development.

### Configuration

The system is configured for simulation mode by default:

**`.env` file:**

```bash
STARLINK_MODE=simulation          # Default mode
PROMETHEUS_RETENTION=1y           # 1 year of data
GRAFANA_ADMIN_PASSWORD=admin      # Change in production
```

### Quick Start

```bash
# Ensure .env is configured
cat .env | grep STARLINK_MODE

# Start services
docker compose up -d

# Verify backend is running in simulation mode
curl <http://localhost:8000/health> | jq '.mode'
# Output: "simulation"
```

### Simulated Behavior

The system automatically generates realistic Starlink telemetry:

| Metric           | Simulation Behavior                                         |
| ---------------- | ----------------------------------------------------------- |
| **Position**     | Circular or straight route following KML route if available |
| **Speed**        | 0-100 knots with realistic variation                        |
| **Latency**      | 20-80ms typical, occasional 200ms spikes                    |
| **Throughput**   | Download 50-200 Mbps, Upload 10-40 Mbps                     |
| **Obstructions** | 0-30% with smooth variation                                 |
| **Altitude**     | 100-10,000 meters with small variations                     |

### Route Configuration

The simulator can follow pre-recorded KML routes or generate circular paths:

**Using Default Circular Route:**

```bash
# Edit config for route parameters
# Location: backend/starlink-location/config.yaml
# Change route.pattern and route.radius_km
```

**Using Custom KML Route:**

1. Place KML file in `/data/sim_routes/`:

```bash
cp your-route.kml /data/sim_routes/my-route.kml
```

1. Restart backend:

```bash
docker compose restart starlink-location
```

1. Check logs:

```bash
docker compose logs starlink-location | grep -i "kml\|route"
```

### Access Points

Once running in simulation mode:

| Service            | URL                             | Notes                  |
| ------------------ | ------------------------------- | ---------------------- |
| **Grafana**        | <http://localhost:3000>         | admin / admin          |
| **Prometheus**     | <http://localhost:9090>         | Metrics database       |
| **Backend Health** | <http://localhost:8000/health>  | Service status         |
| **Backend API**    | <http://localhost:8000/docs>    | Interactive docs       |
| **Metrics**        | <http://localhost:8000/metrics> | Raw Prometheus metrics |

### Testing Simulation Mode

```bash
# Check current status
curl <http://localhost:8000/api/status> | jq .

# List configured POIs
curl <http://localhost:8000/api/pois> | jq .

# Get ETAs to all POIs
curl <http://localhost:8000/api/pois/etas> | jq .

# View available metrics
curl <http://localhost:8000/metrics> | head -20
```

---

## Live Mode Setup

**Connect to a real Starlink terminal** for actual telemetry.

### Prerequisites - Live Mode

1. **Starlink Terminal:** On the same network or accessible via IP
2. **Network Access:** Container must reach terminal at `192.168.100.1:9200`
3. **Terminal Configuration:** Standard Starlink terminal (firmware may vary)

### Configuration - Live Mode

#### Step 1: Update `.env`

```bash
# Edit .env
nano .env

# Set mode to live
STARLINK_MODE=live

# Set dish IP address (default: 192.168.100.1)
STARLINK_DISH_HOST=192.168.100.1

# Set dish gRPC port (standard: 9200)
STARLINK_DISH_PORT=9200
```

#### Step 2: Network Configuration

Choose one network mode based on your OS:

#### Option A: Bridge Mode (Recommended - Cross-Platform)

Works on Windows, macOS, and Linux. Already configured by default.

```yaml
# In docker-compose.yml (default)
extra_hosts:
  - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

#### Option B: Host Mode (Linux Only - Best Performance)

Directly access the host network. More efficient but Linux-only.

```yaml
# In docker-compose.yml - uncomment this:
network_mode: host
# And comment out the extra_hosts section
# extra_hosts:
#   - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

After changing network mode:

```bash
docker compose down
docker compose up -d
```

### Quick Start - Live Mode

```bash
# 1. Update .env
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1

# 2. Rebuild (if config changed significantly)
docker compose down
docker compose up -d --build

# 3. Check connection status
curl <http://localhost:8000/health> | jq .

# Expected: "dish_connected": true
```

### Verifying Connection

```bash
# Check health endpoint
curl <http://localhost:8000/health> | jq .

# Look for:
# "mode": "live"
# "dish_connected": true
# "message": "Live mode: connected to dish"

# If disconnected:
# "dish_connected": false
# "message": "Live mode: waiting for dish connection"
```

### Troubleshooting Live Mode Connection

**Connection Failed:**

```bash
# 1. Verify dish is on the network
ping 192.168.100.1

# 2. Check if port is accessible (if netcat available)
nc -zv 192.168.100.1 9200

# 3. View backend logs
docker compose logs starlink-location | tail -50

# 4. Check network mode
docker inspect starlink-location | grep -A 5 NetworkMode

# 5. Verify firewall isn't blocking
# (depends on your network setup)
```

**If Using Custom IP:**

Update `.env` and restart:

```bash
STARLINK_DISH_HOST=192.168.1.100  # Your custom IP
docker compose down
docker compose up -d
docker compose logs -f starlink-location
```

### Live Mode Features

Once connected:

- Real-time position updates from terminal
- Actual network metrics (latency, throughput)
- Real obstruction readings
- POI/ETA calculations based on actual location
- All dashboard features work with real data

### Connection Behavior

The system is designed to gracefully handle connection issues:

- **On Startup:** If dish is unreachable, service starts anyway
- **During Operation:** Attempts reconnect on each update cycle
- **On Failure:** Returns last known good values while reconnecting
- **Health Check:** Shows actual connection status

This allows:

- Continuous operation even if dish loses power
- Seamless reconnection without restarting service
- Accurate health monitoring via `/health` endpoint

---

## Verification

### Service Health Checks

```bash
# 1. Check all containers running
docker compose ps

# Expected: All services "Up"

# 2. Check backend health
curl <http://localhost:8000/health>
# Expected: {"status": "ok", ...}

# 3. Check Prometheus scraping
curl <http://localhost:9090/api/v1/targets>
# Expected: All targets "UP"

# 4. Verify metrics available
curl <http://localhost:8000/metrics> | head -5
# Expected: Prometheus format with TYPE comments

# 5. Access Grafana
open <http://localhost:3000>
# Expected: Login page (admin/admin)
```

### Data Flow Verification

```bash
# 1. Backend generating metrics
curl <http://localhost:8000/api/status> | jq '.position'

# 2. Prometheus scraping backend
curl <http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees>

# 3. Grafana querying Prometheus
# Open <http://localhost:3000>
# Check Starlink Overview dashboard for live data
```

### Dashboard Verification

Access Grafana and verify:

1. **Starlink Overview** - Main dashboard with map and metrics
2. **Network Metrics** - Latency, throughput, packet loss
3. **Position & Movement** - Position history and altitude

All panels should show live data updating.

---

## Troubleshooting

### Container Won't Start

```bash
# View detailed error logs
docker compose logs starlink-location

# Check system resources
docker stats

# Free up space (if needed)
docker system prune -a
```

### Port Already in Use

```bash
# Find process using port 3000 (Grafana)
lsof -i :3000

# Kill the process
kill -9 <PID>

# Or change port in .env
GRAFANA_PORT=3001
docker compose down && docker compose up -d
```

### Can't Connect to Services

**Backend unreachable:**

```bash
# Check if container is running
docker compose ps starlink-location

# Check logs for errors
docker compose logs starlink-location | tail -20

# Rebuild and restart
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d
```

**Prometheus not scraping:**

```bash
# Check Prometheus targets
open <http://localhost:9090/targets>

# Verify backend health from Prometheus container
docker compose exec prometheus curl <http://starlink-location:8000/health>
```

**Grafana data empty:**

```bash
# Verify data source is connected
# 1. Go to <http://localhost:3000>
# 2. Settings > Data Sources > Prometheus
# 3. Click "Test" button
# 4. Should say "Data source is working"
```

### POI File Issues

```bash
# Check POI file exists
ls -la backend/starlink-location/data/pois.json

# Verify JSON is valid
cat backend/starlink-location/data/pois.json | jq .

# Reset to empty if corrupted
echo '[]' > backend/starlink-location/data/pois.json
```

### Configuration Not Applying

```bash
# 1. Verify .env changes
cat .env | grep STARLINK_MODE

# 2. Rebuild if environment variables changed
docker compose down
docker compose build --no-cache
docker compose up -d

# 3. Check if changes took effect
curl <http://localhost:8000/health> | jq '.mode'
```

### High CPU/Memory Usage

```bash
# Check resource usage
docker stats

# Reduce Prometheus retention if needed
PROMETHEUS_RETENTION=7d  # Instead of 1y
docker compose down
docker compose up -d

# Check if old data cleaning up
docker compose logs prometheus | tail -20
```

---

## Environment Variables Reference

| Variable                 | Default               | Description            | Mode |
| ------------------------ | --------------------- | ---------------------- | ---- |
| `STARLINK_MODE`          | `simulation`          | `simulation` or `live` | Both |
| `STARLINK_DISH_HOST`     | `192.168.100.1`       | Dish IP address        | Live |
| `STARLINK_DISH_PORT`     | `9200`                | Dish gRPC port         | Live |
| `PROMETHEUS_RETENTION`   | `1y`                  | Data retention period  | Both |
| `GRAFANA_ADMIN_PASSWORD` | `admin`               | Grafana password       | Both |
| `STARLINK_LOCATION_PORT` | `8000`                | Backend service port   | Both |
| `PROMETHEUS_PORT`        | `9090`                | Prometheus UI port     | Both |
| `GRAFANA_PORT`           | `3000`                | Grafana UI port        | Both |
| `TIMEZONE_TAKEOFF`       | `America/Los_Angeles` | Timezone for displays  | Both |
| `TIMEZONE_LANDING`       | `Europe/London`       | Timezone for displays  | Both |
| `LOG_LEVEL`              | `INFO`                | Backend logging level  | Both |
| `JSON_LOGS`              | `true`                | JSON-formatted logs    | Both |

---

## Performance Tuning

### Storage Optimization

Reduce metrics retention to save disk space:

```bash
# In .env
PROMETHEUS_RETENTION=30d  # ~200 MB instead of 2.4 GB

docker compose down
docker compose up -d
```

### Memory Optimization

Run on systems with limited memory:

```bash
# In docker-compose.yml, add memory limits:
services:
  starlink-location:
    deploy:
      resources:
        limits:
          memory: 256M
  prometheus:
    deploy:
      resources:
        limits:
          memory: 512M
  grafana:
    deploy:
      resources:
        limits:
          memory: 256M
```

### Network Optimization

For slow networks, increase scrape timeout:

```bash
# Edit monitoring/prometheus/prometheus.yml
scrape_interval: 15s  # Increase from default
scrape_timeout: 10s   # Increase from default
```

---

## Next Steps

1. **Setup POIs:** Create Points of Interest for navigation
   - See
     [Backend README - POI Management](../backend/starlink-location/README.md#poi-management)

1. **Explore Dashboards:** Customize Grafana dashboards
   - See [Grafana Setup Guide](./grafana-setup.md)

1. **Develop Features:** Start working on new features
   - See [Development Guide](../dev/README.md)

1. **Monitor System:** Set up alerts and monitoring
   - See [METRICS documentation](./METRICS.md)

---

## Related Documentation

- [CLAUDE.md](/CLAUDE.md) - Development configuration
- [README.md](/README.md) - Project overview
- [API Reference](./API-REFERENCE.md) - Endpoint documentation
- [Backend README](../backend/starlink-location/README.md) - Service details
- [Grafana Setup](./grafana-setup.md) - Dashboard configuration
- [Design Document](./design-document.md) - Architecture overview
