# Configuration

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)

---

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [Simulation Mode](#simulation-mode)
3. [Live Mode](#live-mode)
4. [Performance Tuning](#performance-tuning)
5. [Network Configuration](#network-configuration)
6. [Storage Configuration](#storage-configuration)

---

## Environment Variables

All configuration is done via the `.env` file in the project root.

### Complete Reference

| Variable | Default | Description | Mode |
|----------|---------|-------------|------|
| `STARLINK_MODE` | `simulation` | `simulation` or `live` | Both |
| `STARLINK_DISH_HOST` | `192.168.100.1` | Dish IP address | Live |
| `STARLINK_DISH_PORT` | `9200` | Dish gRPC port | Live |
| `PROMETHEUS_RETENTION` | `1y` | Data retention period | Both |
| `GRAFANA_ADMIN_PASSWORD` | `admin` | Grafana password | Both |
| `STARLINK_LOCATION_PORT` | `8000` | Backend port | Both |
| `PROMETHEUS_PORT` | `9090` | Prometheus port | Both |
| `GRAFANA_PORT` | `3000` | Grafana port | Both |
| `TIMEZONE_TAKEOFF` | `America/Los_Angeles` | Takeoff timezone | Both |
| `TIMEZONE_LANDING` | `Europe/London` | Landing timezone | Both |
| `LOG_LEVEL` | `INFO` | Backend log level | Both |
| `JSON_LOGS` | `true` | JSON log format | Both |

---

## Simulation Mode

**Purpose:** Development, testing, and demonstrations without hardware.

### Basic Configuration

Edit `.env`:

```bash
# Set mode to simulation
STARLINK_MODE=simulation

# Optional: Adjust simulation behavior
# (advanced config in backend/starlink-location/config.yaml)
```

### Simulated Behavior

The simulator generates realistic Starlink telemetry:

| Metric | Simulation Behavior |
|--------|-------------------|
| **Position** | Circular or route-following movement |
| **Speed** | 0-100 knots with realistic variation |
| **Latency** | 20-80ms typical, occasional 200ms spikes |
| **Throughput** | Download 50-200 Mbps, Upload 10-40 Mbps |
| **Obstructions** | 0-30% with smooth variation |
| **Altitude** | 100-10,000 meters |

### Route Configuration

**Using Default Circular Route:**

The simulator uses a circular pattern by default. No configuration needed.

**Using Custom KML Route:**

1. Place KML file in `/data/sim_routes/`:

   ```bash
   cp your-route.kml data/sim_routes/my-route.kml
   ```

2. Restart backend:

   ```bash
   docker compose restart starlink-location
   ```

3. Check logs:

   ```bash
   docker compose logs starlink-location | rg -i "kml|route"
   ```

### Testing Simulation Mode

```bash
# Check status
curl http://localhost:8000/api/status | jq '.position'

# Monitor position updates (should change every second)
watch -n 1 'curl -s http://localhost:8000/api/status | jq .position.latitude'

# View metrics
curl http://localhost:8000/metrics | rg starlink_dish_latitude
```

---

## Live Mode

**Purpose:** Connect to a real Starlink terminal for actual telemetry.

### Prerequisites

1. Starlink terminal on local network
2. Terminal accessible at `192.168.100.1` (default) or known IP
3. Port `9200` accessible for gRPC

### Basic Configuration

Edit `.env`:

```bash
# Set mode to live
STARLINK_MODE=live

# Configure dish connection
STARLINK_DISH_HOST=192.168.100.1  # Your terminal's IP
STARLINK_DISH_PORT=9200            # Standard gRPC port
```

### Network Mode Selection

Choose network mode based on your OS:

#### Option A: Bridge Mode (Recommended - Cross-Platform)

Already configured by default. Works on Windows, macOS, and Linux.

**In `docker-compose.yml`:**

```yaml
extra_hosts:
  - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

No changes needed - this is the default configuration.

#### Option B: Host Mode (Linux Only - Best Performance)

For Linux systems, host mode provides direct network access.

**In `docker-compose.yml`:**

Uncomment:

```yaml
network_mode: host
```

And comment out:

```yaml
# extra_hosts:
#   - "dish.starlink:${STARLINK_DISH_HOST:-192.168.100.1}"
```

**Apply changes:**

```bash
docker compose down
docker compose up -d
```

### Connection Behavior

The system gracefully handles connection issues:

**On Startup:**

- If dish unreachable, service starts anyway
- Status shows `dish_connected: false`
- No metrics exported until connection established

**During Operation:**

- Attempts reconnect on each update cycle
- Returns last known values while reconnecting
- Automatic reconnection when dish becomes available

**Health Check:**

```bash
curl http://localhost:8000/health | jq .
```

**Connected response:**

```json
{
  "status": "ok",
  "mode": "live",
  "message": "Live mode: connected to dish",
  "dish_connected": true
}
```

**Disconnected response:**

```json
{
  "status": "ok",
  "mode": "live",
  "message": "Live mode: waiting for dish connection",
  "dish_connected": false
}
```

### Testing Connection

**1. Verify dish is reachable:**

```bash
ping 192.168.100.1
```

**2. Test port accessibility:**

```bash
timeout 5 bash -c 'cat < /dev/null > /dev/tcp/192.168.100.1/9200' && \
  echo "Connection OK" || echo "Connection failed"
```

**3. Check backend logs:**

```bash
docker compose logs -f starlink-location | rg -i "dish|connect"
```

**4. Verify metrics:**

```bash
curl http://localhost:8000/metrics | rg starlink_dish
```

### Custom IP Configuration

If your dish uses a different IP:

```bash
# Edit .env
nano .env

# Update IP
STARLINK_DISH_HOST=192.168.1.100  # Your actual IP

# Restart
docker compose down
docker compose up -d

# Verify
curl http://localhost:8000/health | jq '.dish_connected'
```

---

## Performance Tuning

### Storage Optimization

Reduce Prometheus retention to save disk space:

```bash
# In .env
PROMETHEUS_RETENTION=30d  # ~200 MB instead of 2.4 GB for 1y
PROMETHEUS_RETENTION=90d  # ~600 MB
PROMETHEUS_RETENTION=15d  # ~100 MB
```

**Apply changes:**

```bash
docker compose down
docker compose up -d
```

**Verify retention:**

```bash
docker compose logs prometheus | rg -i retention
```

---

### Memory Optimization

For systems with limited memory, add resource limits in `docker-compose.yml`:

```yaml
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

**Apply:**

```bash
docker compose down
docker compose up -d
```

**Monitor usage:**

```bash
docker stats --no-stream
```

---

### Network Optimization

For slow networks, increase scrape intervals:

**Edit `monitoring/prometheus/prometheus.yml`:**

```yaml
global:
  scrape_interval: 15s  # Increase from default 10s
  scrape_timeout: 10s   # Increase from default 5s
```

**Restart Prometheus:**

```bash
docker compose restart prometheus
```

---

## Network Configuration

### Port Configuration

**Default ports:**

- Backend: `8000`
- Prometheus: `9090`
- Grafana: `3000`

**To change ports:**

Edit `.env`:

```bash
STARLINK_LOCATION_PORT=8001
PROMETHEUS_PORT=9091
GRAFANA_PORT=3001
```

**Apply:**

```bash
docker compose down
docker compose up -d
```

**Access new ports:**

- Backend: <http://localhost:8001>
- Prometheus: <http://localhost:9091>
- Grafana: <http://localhost:3001>

---

### Firewall Configuration

**Linux (ufw):**

```bash
# Open ports
sudo ufw allow 3000/tcp  # Grafana
sudo ufw allow 8000/tcp  # Backend
sudo ufw allow 9090/tcp  # Prometheus

# Verify
sudo ufw status
```

**Linux (firewalld):**

```bash
# Open ports
sudo firewall-cmd --permanent --add-port=3000/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=9090/tcp

# Reload
sudo firewall-cmd --reload
```

---

## Storage Configuration

### Data Retention

**Storage calculation:**

```
Number of metrics: 45
Scrape interval: 1 second
Retention period: 1 year (31,536,000 seconds)
Size per sample: ~1.5 bytes (compressed)
Compression overhead: ~1.2x

Storage = (45 × 31,536,000 × 1.5 × 1.2) / 1,073,741,824 ≈ 2.4 GB
```

**Common retention periods:**

| Retention | Storage | Use Case |
|-----------|---------|----------|
| `1y` | ~2.4 GB | Long-term analysis |
| `90d` | ~600 MB | Quarterly reviews |
| `30d` | ~200 MB | Monthly monitoring |
| `15d` | ~100 MB | Development/testing |
| `7d` | ~50 MB | Minimal storage |

---

### Volume Management

**View volumes:**

```bash
docker volume ls | rg starlink
```

**Check volume size:**

```bash
docker volume inspect prometheus_data
```

**Clean up old data:**

```bash
# Stop services
docker compose down

# Remove volumes (WARNING: deletes all data)
docker volume rm starlink-dashboard-dev_prometheus_data

# Restart
docker compose up -d
```

---

## Logging Configuration

### Log Levels

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**In `.env`:**

```bash
# Development: detailed logs
LOG_LEVEL=DEBUG

# Production: standard logs
LOG_LEVEL=INFO

# Quiet: errors only
LOG_LEVEL=ERROR
```

**Apply:**

```bash
docker compose restart starlink-location
```

---

### Log Format

**JSON logs (default):**

```bash
JSON_LOGS=true
```

**Human-readable logs:**

```bash
JSON_LOGS=false
```

---

### View Logs

**All services:**

```bash
docker compose logs -f
```

**Specific service:**

```bash
docker compose logs -f starlink-location
docker compose logs -f prometheus
docker compose logs -f grafana
```

**Filter by level:**

```bash
docker compose logs starlink-location | rg -i error
docker compose logs starlink-location | rg -i warning
```

**Save logs to file:**

```bash
docker compose logs > logs.txt
docker compose logs starlink-location > backend.log
```

---

## Timezone Configuration

For flight operations, configure takeoff and landing timezones:

```bash
# In .env
TIMEZONE_TAKEOFF=America/Los_Angeles  # West Coast
TIMEZONE_LANDING=Europe/London        # UK

# Or other common zones:
# America/New_York (EST/EDT)
# America/Chicago (CST/CDT)
# America/Denver (MST/MDT)
# Asia/Tokyo (JST)
# Australia/Sydney (AEST/AEDT)
```

These are used in mission planning and time displays.

---

## Configuration Examples

### Development Setup

Optimized for local development:

```bash
# .env
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=7d
LOG_LEVEL=DEBUG
JSON_LOGS=false
```

---

### Production Setup

Optimized for production monitoring:

```bash
# .env
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1
PROMETHEUS_RETENTION=1y
GRAFANA_ADMIN_PASSWORD=<strong-password>
LOG_LEVEL=INFO
JSON_LOGS=true
```

---

### Testing Setup

Minimal resource usage:

```bash
# .env
STARLINK_MODE=simulation
PROMETHEUS_RETENTION=1d
LOG_LEVEL=WARNING
```

---

## Applying Configuration Changes

### Environment Variable Changes

```bash
# 1. Edit .env
nano .env

# 2. Restart affected services
docker compose down
docker compose up -d

# 3. Verify changes
curl http://localhost:8000/health
```

---

### Configuration File Changes

**For backend config.yaml changes:**

```bash
# Backend Python code changes require full rebuild
docker compose down
docker compose build --no-cache starlink-location
docker compose up -d
```

**For Prometheus config changes:**

```bash
# Edit monitoring/prometheus/prometheus.yml
nano monitoring/prometheus/prometheus.yml

# Restart Prometheus
docker compose restart prometheus

# Verify
curl http://localhost:9090/-/healthy
```

---

## Verification

After configuration changes, verify:

```bash
# 1. Services running
docker compose ps

# 2. Health checks
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:3000/api/health

# 3. Logs for errors
docker compose logs | rg -i error
```

---

## Next Steps

Configuration complete! Proceed to:

- **[API Reference](../api/README.md)** - Explore endpoints
- **[Route Management](../../CLAUDE.md#route-management)** - Upload routes
- **[Troubleshooting](../troubleshooting/README.md)** - Common issues

---

[Back to Setup Guide](./README.md) | [Back to main docs](../INDEX.md)
