# Quick Start Guide

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)

---

## Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- Git

---

## 3-Minute Setup

```bash
# 1. Clone and enter directory
git clone https://github.com/your-repo/starlink-dashboard.git
cd starlink-dashboard

# 2. Set up configuration
cp .env.example .env

# 3. Start services
./scripts/compose.sh up -d --build

# 4. Verify and access
curl http://localhost:8000/health        # Backend health
open http://localhost:5173                # Mission Planner
```

**Detailed setup:** See [Installation Guide](./installation.md)

---

## Access Points

Once services are running:

| Service             | URL                             | Purpose                        |
| ------------------- | ------------------------------- | ------------------------------ |
| **Mission Planner** | <http://localhost:5173>         | Dashboard and mission planning |
| **Prometheus**      | <http://localhost:9090>         | Metrics database               |
| **Backend API**     | <http://localhost:8000/docs>    | Interactive API docs           |
| **Health Check**    | <http://localhost:8000/health>  | Service status                 |
| **Metrics**         | <http://localhost:8000/metrics> | Raw Prometheus metrics         |

---

## Operating Modes

### Simulation Mode (Default)

Perfect for development and testing without hardware.

```bash
# Configuration
STARLINK_MODE=simulation          # Default
PROMETHEUS_RETENTION=1y           # 1 year of data
```

**Features:**

- Generates realistic Starlink telemetry
- Follows KML routes or circular paths
- Simulates network metrics with realistic patterns
- Useful for UI development and testing

**See:**
[Configuration Guide - Simulation Mode](./configuration.md#simulation-mode)

---

### Live Mode

Connect to a real Starlink terminal for actual data.

```bash
# Configuration
STARLINK_MODE=live
STARLINK_DISH_HOST=192.168.100.1  # Your terminal IP
STARLINK_DISH_PORT=9200           # Standard gRPC port
```

**Requirements:**

- Starlink terminal on local network
- Network access to terminal's gRPC port
- Proper Docker networking configuration

**See:** [Configuration Guide - Live Mode](./configuration.md#live-mode)

---

## Development Commands

### Docker Compose

```bash
# Start all services
./scripts/compose.sh up -d --build

# Stop all services
docker compose down

# View live logs
docker compose logs -f

# View logs from specific service
docker compose logs -f starlink-location

# Rebuild images
./scripts/compose.sh build
./scripts/compose.sh build --no-cache

# Restart services
docker compose restart

# Full reset (rebuild and restart)
./scripts/compose.sh down && ./scripts/compose.sh build --no-cache && ./scripts/compose.sh up -d
```

---

### Testing & Verification

```bash
# Check backend health
curl http://localhost:8000/health

# Get current status
curl http://localhost:8000/api/status | jq .

# List all POIs
curl http://localhost:8000/api/pois | jq .

# Get ETA to POIs
curl http://localhost:8000/api/pois/etas | jq .

# View available metrics
curl http://localhost:8000/metrics | head -20
```

---

[Back to Setup Guide](./README.md) | [Back to main docs](../index.md)
