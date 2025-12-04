# Installation Steps

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

---

## Overview

This guide provides detailed step-by-step instructions for installing Starlink
Dashboard.

For a quick installation, see
[Quick Installation](./installation-quick-start.md).

---

## Step 1: Clone the Repository

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

```text
backend/
monitoring/
docker-compose.yml
.env.example
CLAUDE.md
README.md
```

---

## Step 2: Create Environment File

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

## Step 3: Build Docker Images

Build all services (takes 2-3 minutes on first run):

```bash
docker compose build
```

**Expected output:**

```json
[+] Building 45.2s (23/23) FINISHED
 => [starlink-location] ...
 => => naming to docker.io/library/starlink-location:latest
```

**Verify images created:**

```bash
docker compose images
```

**Expected output:**

```text
CONTAINER           IMAGE                    SIZE
starlink-location   starlink-location:latest 500MB
prometheus          prom/prometheus:latest   200MB
grafana             grafana/grafana:latest   300MB
```

---

## Step 4: Start Services

Start all services in background (detached mode):

```bash
docker compose up -d
```

**Expected output:**

```json
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

```text
NAME                STATUS              PORTS
starlink-location   Up 10 seconds       0.0.0.0:8000->8000/tcp
prometheus          Up 12 seconds       0.0.0.0:9090->9090/tcp
grafana             Up 11 seconds       0.0.0.0:3000->3000/tcp
```

All services should show "Up" status.

---

## Step 5: Verify Services

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

## Next Steps

Installation complete! Now proceed to:

1. **[Verification](./installation-verification.md)** - Verify installation
   health
2. **[First-Time Configuration](./installation-first-time.md)** - Optional setup
3. **[Configuration](./configuration.md)** - Customize for your use case

**Need help?** Check the
[Troubleshooting Guide](./installation-troubleshooting.md)

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
