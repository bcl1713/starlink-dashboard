# Features Overview

[Back to README](../README.md)

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

For a detailed list of completed and planned features, see
[Development Plan](development-plan.md).

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
│   ├── setup/                     # Setup instructions
│   ├── api/                       # API endpoints
│   ├── troubleshooting/           # Common issues
│   ├── architecture/              # Architecture details
│   └── grafana-configuration.md   # Dashboard configuration
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

## Development Status

**Current Phase:** Foundation Complete + Major Features Complete

**Completed Work:**

- Phase 0: Core infrastructure, metrics, dashboards ✅
- POI Interactive Management: Complete ✅ (10 sessions)
- KML Route Import and Management: Complete ✅ (16 sessions)
- ETA Route Timing: Complete ✅ (24 sessions)
- Mission Communication Planning: Complete ✅ (12 sessions)

**Branch Status:** feature/mission-comm-planning (ready for merge to main)

**Next Steps:** See the [Development Plan](development-plan.md) for timeline
details.

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
[Setup Guide - Performance Tuning](./setup/installation.md#performance-tuning)

---

[Back to README](../README.md)
