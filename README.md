# Starlink Dashboard

A Docker-based monitoring system for Starlink terminals with real-time metrics
visualization through Prometheus and Grafana. Supports both live monitoring of
physical Starlink hardware and simulation mode for offline development.

**Status:** Phase 0 Complete (Foundation) + ETA Route Timing Feature Complete
**Version:** 0.3.0 **Last Updated:** 2025-11-04 **Branch:**
feature/eta-route-timing (ready for merge to main)

## Quick Navigation

**For Users:**

- [Quick Start](#quick-start)
- [Setup Guide](./docs/SETUP-GUIDE.md) - Detailed setup for simulation and live
  modes
- [Grafana Dashboards](#grafana-dashboards)
- [Troubleshooting](./docs/TROUBLESHOOTING.md)

**For Developers:**

- [Contributing Guide](./CONTRIBUTING.md)
- [API Reference](./docs/API-REFERENCE.md)
- [Development Status](./dev/STATUS.md)
- [Architecture](./docs/design-document.md)

---

## Quick Start

### Prerequisites

- Docker (version 20.10 or higher)
- Docker Compose (version 2.0 or higher)
- Git

### 3-Minute Setup

```bash
# 1. Clone and enter directory
git clone <https://github.com/your-repo/starlink-dashboard.git>
cd starlink-dashboard

# 2. Set up configuration
cp .env.example .env

# 3. Start services
docker compose up -d

# 4. Verify and access
curl <http://localhost:8000/health>        # Backend health
open <http://localhost:3000>                # Grafana (admin/admin)
```

**Detailed setup:** See [Setup Guide](./docs/SETUP-GUIDE.md)

---

## Access Points

Once services are running:

| Service          | URL                             | Purpose                  |
| ---------------- | ------------------------------- | ------------------------ |
| **Grafana**      | <http://localhost:3000>         | Dashboards (admin/admin) |
| **Prometheus**   | <http://localhost:9090>         | Metrics database         |
| **Backend API**  | <http://localhost:8000/docs>    | Interactive API docs     |
| **Health Check** | <http://localhost:8000/health>  | Service status           |
| **Metrics**      | <http://localhost:8000/metrics> | Raw Prometheus metrics   |

---

## Grafana Dashboards

Three pre-configured dashboards provide comprehensive monitoring:

| Dashboard               | Purpose                      | Key Features                                                              |
| ----------------------- | ---------------------------- | ------------------------------------------------------------------------- |
| **Starlink Overview**   | Main monitoring dashboard    | Live position map, POI ETA table, network latency gauge, throughput graph |
| **Network Metrics**     | Detailed network performance | Latency analysis, throughput breakdown, packet loss, signal quality       |
| **Position & Movement** | Location tracking            | Live map with history, altitude profile, speed/heading trends             |

**Dashboard Access:**

- Starlink Overview: <http://localhost:3000/d/starlink-overview>
- Network Metrics: <http://localhost:3000/d/starlink-network>
- Position & Movement: <http://localhost:3000/d/starlink-position>

**Dashboard Guide:** See [Grafana Setup Documentation](./docs/grafana-setup.md)

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
[Setup Guide - Simulation Mode](./docs/SETUP-GUIDE.md#simulation-mode-setup)

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

**See:** [Setup Guide - Live Mode](./docs/SETUP-GUIDE.md#live-mode-setup)

---

## Configuration

### Environment Variables

All configuration via `.env` file:

| Variable                 | Default         | Purpose                                  |
| ------------------------ | --------------- | ---------------------------------------- |
| `STARLINK_MODE`          | `simulation`    | Operating mode (simulation or live)      |
| `STARLINK_DISH_HOST`     | `192.168.100.1` | Dish IP address (live mode)              |
| `STARLINK_DISH_PORT`     | `9200`          | Dish gRPC port (live mode)               |
| `PROMETHEUS_RETENTION`   | `1y`            | Metrics retention period                 |
| `GRAFANA_ADMIN_PASSWORD` | `admin`         | Grafana password (change in production!) |
| `STARLINK_LOCATION_PORT` | `8000`          | Backend port                             |
| `PROMETHEUS_PORT`        | `9090`          | Prometheus port                          |
| `GRAFANA_PORT`           | `3000`          | Grafana port                             |

**Complete reference:** See [CLAUDE.md](./CLAUDE.md#configuration)

---

## Key Features

- **Real-time Monitoring:** Live position tracking and metrics on interactive
  maps
- **Dual Mode:** Works with real hardware or in simulation mode
- **Historical Data:** Full 1-year metrics retention (configurable)
- **POI Management:** Create and track points of interest with real-time ETAs
- **Network Analytics:** Detailed latency, throughput, and packet loss metrics
- **Docker-based:** Single `docker compose up` for complete stack
- **REST API:** Full API for programmatic access and integrations

---

## Project Structure

```text
starlink-dashboard/
├── backend/                       # Python FastAPI backend
│   └── starlink-location/
│       ├── app/                   # Application code
│       ├── tests/                 # Test suite
│       ├── config.yaml            # Default configuration
│       └── README.md              # Backend-specific docs
├── monitoring/                    # Prometheus & Grafana configs
│   ├── prometheus/
│   └── grafana/
├── docs/                          # Comprehensive documentation
│   ├── SETUP-GUIDE.md             # Setup instructions
│   ├── API-REFERENCE.md           # API endpoints
│   ├── TROUBLESHOOTING.md         # Common issues
│   ├── design-document.md         # Architecture details
│   ├── METRICS.md                 # Prometheus metrics
│   └── grafana-setup.md           # Dashboard configuration
├── dev/                           # Development management
│   ├── STATUS.md                  # Current development status
│   ├── README.md                  # Workflow documentation
│   ├── active/                    # Active tasks
│   └── completed/                 # Completed tasks
├── docker-compose.yml             # Service composition
├── .env.example                   # Configuration template
├── CLAUDE.md                      # AI development guide
├── CONTRIBUTING.md                # Contribution guidelines
└── README.md                      # This file
```

---

## Development Commands

### Docker Compose

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View live logs
docker compose logs -f

# View logs from specific service
docker compose logs -f starlink-location

# Rebuild images
docker compose build
docker compose build --no-cache

# Restart services
docker compose restart

# Full reset (rebuild and restart)
docker compose down && docker compose build --no-cache && docker compose up -d
```

### Testing & Verification

```bash
# Check backend health
curl <http://localhost:8000/health>

# Get current status
curl <http://localhost:8000/api/status> | jq .

# List all POIs
curl <http://localhost:8000/api/pois> | jq .

# Get ETA to POIs
curl <http://localhost:8000/api/pois/etas> | jq .

# View available metrics
curl <http://localhost:8000/metrics> | head -20
```

---

## Architecture Overview

The system consists of three main components:

```text
┌─────────────────────────────────────────────────┐
│  Grafana (Port 3000)                            │
│  - Starlink Overview Dashboard                  │
│  - Network Metrics Dashboard                    │
│  - Position & Movement Dashboard                │
└────────────────┬────────────────────────────────┘
                 │ (Prometheus Queries)
┌────────────────▼────────────────────────────────┐
│  Prometheus (Port 9090)                         │
│  - Time-series database                         │
│  - 1-year metrics retention                     │
└────────────────┬────────────────────────────────┘
                 │ (Scrapes metrics)
┌────────────────▼────────────────────────────────┐
│  Backend Service (Port 8000)                    │
│  - FastAPI application                          │
│  - Simulation or Live mode                      │
│  - Prometheus metrics export                    │
│  - POI management                               │
│  - REST API (/docs)                             │
└─────────────────────────────────────────────────┘
         │                          │
    ┌────▼──────────────┐      ┌────▼──────────────┐
    │ Simulation Engine │      │ Starlink Terminal │
    │ (No hardware)     │      │ (Live mode only)  │
    └───────────────────┘      └───────────────────┘
```

**Full architecture:** See [Design Document](./docs/design-document.md)

---

## Documentation

Comprehensive documentation is organized by topic:

### For Getting Started

- [Setup Guide](./docs/SETUP-GUIDE.md) - Installation and configuration
- [Quick Start](#quick-start) - 3-minute setup

### For Using the System

- [Grafana Setup](./docs/grafana-setup.md) - Dashboard usage
- [API Reference](./docs/API-REFERENCE.md) - REST API endpoints
- [Troubleshooting](./docs/TROUBLESHOOTING.md) - Common issues

### For Development

- [Contributing Guide](./CONTRIBUTING.md) - How to contribute
- [CLAUDE.md](./CLAUDE.md) - Development configuration
- [Design Document](./docs/design-document.md) - Architecture
- [Development Status](./dev/STATUS.md) - Current progress

### For Reference

- [METRICS.md](./docs/METRICS.md) - Prometheus metrics
- [Backend README](./backend/starlink-location/README.md) - Service details

---

## Getting Help

**Setup Issues:**

- See [Setup Guide](./docs/SETUP-GUIDE.md)
- Check [Troubleshooting Guide](./docs/TROUBLESHOOTING.md)

**API Questions:**

- See [API Reference](./docs/API-REFERENCE.md)
- Visit <http://localhost:8000/docs> (interactive documentation)

**Development Questions:**

- See [Contributing Guide](./CONTRIBUTING.md)
- Check [Development Status](./dev/STATUS.md)

**Specific Issues:**

- See [Troubleshooting Guide](./docs/TROUBLESHOOTING.md)
- Run diagnostic commands in [Quick Start](#testing--verification)

---

## Contributing

Want to help improve Starlink Dashboard?

- Read [Contributing Guide](./CONTRIBUTING.md)
- Check [Development Status](./dev/STATUS.md) for current tasks
- Review [Architecture](./docs/design-document.md) before starting

---

## Mission Communication Planning

Pre-flight mission communication analysis for predicting and managing satellite
communication degradation across three onboard transports (X-Band, Ka,
StarShield/Ku). Essential for flight operations planning, crew briefing, and
communication contingency preparation.

**Features:**

- **Mission Planning Interface:** Create and manage missions with transport
  configurations, timing windows, and operational constraints
- **Satellite Geometry Engine:** Analyzes 3D satellite positions, azimuth
  angles, and elevation constraints for real-time communication status
- **Timeline Generation:** Predicts communication degradation windows across
  mission flight phases
- **Multi-Format Exports:** Generate PDF briefings, CSV logs, and Excel reports
  for crew and ground operators
- **Grafana Integration:** Real-time mission timeline visualization, alert rules
  for approaching degradation windows, satellite coverage overlays
- **Performance Optimized:** Benchmark-tested recomputation at <0.12s per
  mission with concurrent support

**Documentation:**

- [Mission Planning Guide](./docs/MISSION-PLANNING-GUIDE.md) - Complete user
  guide with UI walkthrough
- [Mission Communication SOP](./docs/MISSION-COMM-SOP.md) - Operations playbook
  for mission planning and monitoring
- [Performance Notes](./docs/PERFORMANCE-NOTES.md) - Benchmark results and
  optimization guidance
- [Monitoring Setup](./monitoring/README.md#mission-communication-planning) -
  Dashboard and alert configuration

**Status:** Phase 5 Complete ✅ (All tests passing, production-ready)

---

## Development Status

**Current Phase:** Foundation Complete + Major Features Complete

**Completed Work:**

- Phase 0: Core infrastructure, metrics, dashboards ✅
- POI Interactive Management: Complete ✅ (10 sessions)
- KML Route Import and Management: Complete ✅ (16 sessions)
- ETA Route Timing: Complete ✅ (24 sessions)
  - Automatic timing metadata extraction from KML waypoints
  - Real-time ETA calculations to waypoints and locations
  - Simulator respects route timing speeds for realistic movement
  - Comprehensive Prometheus metrics and Grafana visualization
  - All 451 tests passing
- **Mission Communication Planning: Complete ✅ (12 sessions)**
  - Pre-flight communication degradation prediction
  - Satellite geometry analysis (X-Band, Ka, Ku transports)
  - Timeline computation and multi-format exports (PDF, CSV, XLSX)
  - Grafana visualization with real-time monitoring and alerts
  - 720+ integration and scenario tests passing
  - Production-ready with <0.12s per-mission performance

**Branch Status:** feature/mission-comm-planning (ready for merge to main)

**Next Steps:** See [Phased Development Plan](./docs/phased-development-plan.md)
for future enhancements

---

## Performance & Storage

**Resource Requirements:**

- Minimum RAM: 4 GB
- Minimum Disk: 5 GB
- Storage usage: ~2.4 GB per year (configurable)

**Performance:**

- Backend response time: <50ms
- Prometheus query time: <1s
- Grafana dashboard load: <2s

**See:**
[Setup Guide - Performance Tuning](./docs/SETUP-GUIDE.md#performance-tuning)

---

## License

Part of the Starlink Dashboard project.

---

## Related Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Docker Documentation](https://docs.docker.com/)
