# Installation

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

---

## Table of Contents

1. [Quick Installation](#quick-installation)
2. [Step-by-Step Installation](#step-by-step-installation)
3. [Verification](#verification)
4. [Access Points](#access-points)
5. [First-Time Configuration](#first-time-configuration)
6. [Troubleshooting](#troubleshooting)

---

## Quick Installation

For experienced users, here's the fast track:

```bash
# Clone repository
git clone https://github.com/your-repo/starlink-dashboard.git
cd starlink-dashboard

# Set up environment
cp .env.example .env

# Build and start
docker compose build
docker compose up -d

# Verify
curl http://localhost:8000/health
```

**Access:** Grafana at <http://localhost:3000> (admin/admin)

---

## Step-by-Step Installation

### Step 1: Clone the Repository

```bash
# Navigate to your workspace
cd ~/Projects  # or your preferred location

# Clone the repository
git clone https://github.com/your-repo/starlink-dashboard.git

# Enter directory
cd starlink-dashboard

# Verify files
ls -la
```

**Expected files:**

```
backend/
monitoring/
docker-compose.yml
.env.example
CLAUDE.md
README.md
```

---

### Step 2: Create Environment File

The `.env` file contains all configuration settings.

```bash
# Copy example file
cp .env.example .env

# View contents
cat .env
```

**Default configuration (simulation mode):**

```bash
# Operating mode
STARLINK_MODE=simulation

# Service ports
STARLINK_LOCATION_PORT=8000
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000

# Data retention
PROMETHEUS_RETENTION=1y

# Grafana credentials
GRAFANA_ADMIN_PASSWORD=admin
```

**For now, the defaults are fine.** You can customize later in
[Configuration](./configuration.md).

---

### Step 3: Build Docker Images

Build all services (takes 2-3 minutes on first run):

```bash
docker compose build
```

**Expected output:**

```
[+] Building 45.2s (23/23) FINISHED
 => [starlink-location] ...
 => => naming to docker.io/library/starlink-location:latest
```

**Verify images created:**

```bash
docker compose images
```

**Expected output:**

```
CONTAINER           IMAGE                    SIZE
starlink-location   starlink-location:latest 500MB
prometheus          prom/prometheus:latest   200MB
grafana             grafana/grafana:latest   300MB
```

---

### Step 4: Start Services

Start all services in background (detached mode):

```bash
docker compose up -d
```

**Expected output:**

```
[+] Running 4/4
 ✔ Network starlink-dashboard-dev_starlink-net  Created
 ✔ Container prometheus                         Started
 ✔ Container starlink-location                  Started
 ✔ Container grafana                            Started
```

**Check status:**

```bash
docker compose ps
```

**Expected output:**

```
NAME                STATUS              PORTS
starlink-location   Up 10 seconds       0.0.0.0:8000->8000/tcp
prometheus          Up 12 seconds       0.0.0.0:9090->9090/tcp
grafana             Up 11 seconds       0.0.0.0:3000->3000/tcp
```

All services should show "Up" status.

---

### Step 5: Verify Services

**Backend health check:**

```bash
curl http://localhost:8000/health
```

**Expected response:**

```json
{
  "status": "ok",
  "uptime_seconds": 15.3,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2025-10-31T10:30:00.000000",
  "message": "Service is healthy",
  "dish_connected": false
}
```

**View logs (optional):**

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f starlink-location

# Press Ctrl+C to exit
```

---

## Verification

### Service Health Checks

**1. Backend API:**

```bash
curl http://localhost:8000/health | jq .
```

✅ Should return `"status": "ok"`

---

**2. Prometheus targets:**

```bash
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[].health'
```

✅ Should return `"up"` for all targets

---

**3. Grafana:**

```bash
curl -s http://localhost:3000/api/health | jq .
```

✅ Should return `"database": "ok"`

---

### Data Flow Verification

**1. Backend generating metrics:**

```bash
curl http://localhost:8000/api/status | jq '.position'
```

✅ Should show current position data

---

**2. Prometheus scraping backend:**

```bash
curl 'http://localhost:9090/api/v1/query?query=starlink_dish_latitude_degrees' | jq .
```

✅ Should return metric value

---

**3. Check container logs:**

```bash
docker compose logs --tail=20 starlink-location
```

✅ Should show simulation updates

---

## Access Points

After successful installation:

### Grafana (Dashboards)

**URL:** <http://localhost:3000>

**Login:**

- Username: `admin`
- Password: `admin` (or value from `.env`)

**First login:**

1. Enter credentials
2. Skip password change prompt (or set new password)
3. Navigate to Dashboards → Starlink Overview

---

### Prometheus (Metrics Database)

**URL:** <http://localhost:9090>

**Usage:**

- No login required
- View targets: <http://localhost:9090/targets>
- Run queries: <http://localhost:9090/graph>

---

### Backend API (Interactive Documentation)

**URL:** <http://localhost:8000/docs>

**Usage:**

- Browse all endpoints
- Test API calls
- View request/response schemas

---

## First-Time Configuration

### Upload Sample Routes (Optional)

Sample routes are available in `/data/sample_routes/`:

```bash
# Via UI
open http://localhost:8000/ui/routes

# Or via API
curl -X POST \
  -F "file=@data/sample_routes/simple-circular.kml" \
  http://localhost:8000/api/routes/upload
```

---

### Create POIs (Optional)

**Via UI:**

```bash
open http://localhost:8000/ui/pois
```

**Via API:**

```bash
curl -X POST http://localhost:8000/api/pois \
  -H "Content-Type: application/json" \
  -d '{
    "name": "New York City",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "description": "NYC Downtown"
  }'
```

---

### View Dashboards

Open Grafana and explore:

1. **Starlink Overview** - Main dashboard with map
2. **Network Metrics** - Latency, throughput
3. **Position & Movement** - Position history

---

## Troubleshooting

### Services won't start

**Check logs:**

```bash
docker compose logs
```

**Common issues:**

- Port conflicts → [Prerequisites](./prerequisites.md#port-availability-check)
- Insufficient disk space → `df -h`
- Docker not running → `sudo systemctl start docker`

---

### Container exits immediately

**Check specific service:**

```bash
docker compose logs starlink-location
```

**Solution:**

```bash
# Rebuild without cache
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

### Can't access services

**Check if containers are running:**

```bash
docker compose ps
```

**Check port bindings:**

```bash
docker compose ps
```

**Test from host:**

```bash
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health
```

---

### "Address already in use" error

**Find process using port:**

```bash
# Linux/macOS
lsof -i :3000
lsof -i :8000
lsof -i :9090

# Kill process (if safe)
kill -9 <PID>
```

**Or change ports in `.env`:**

```bash
nano .env
# Change: GRAFANA_PORT=3001
docker compose down
docker compose up -d
```

---

### Prometheus not scraping

**Check Prometheus targets:**

```bash
open http://localhost:9090/targets
```

**Verify backend reachable from Prometheus:**

```bash
docker compose exec prometheus curl http://starlink-location:8000/health
```

---

### Grafana shows no data

**Verify data source:**

1. Go to <http://localhost:3000>
2. Configuration → Data Sources → Prometheus
3. Click "Test" button
4. Should show green "Data source is working"

**If test fails:**

```bash
# Check if Prometheus is running
docker compose ps prometheus

# Test from Grafana container
docker compose exec grafana curl http://prometheus:9090
```

---

### Build fails

**Clear Docker cache:**

```bash
docker system prune -a
docker compose build --no-cache
```

**Check disk space:**

```bash
df -h
```

---

## Next Steps

Installation complete! Now proceed to:

1. **[Configuration](./configuration.md)** - Customize for your use case
2. **[API Reference](../api/README.md)** - Explore available endpoints
3. **[Route Management](../../CLAUDE.md#route-management)** - Upload flight routes

**Need help?** Check the [Troubleshooting Guide](../troubleshooting/README.md)

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
