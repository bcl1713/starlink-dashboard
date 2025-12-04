# Design Document: Mobile Starlink Terminal Monitoring Webapp

**This document has been reorganized into multiple focused files.**

---

## Documentation Topics

- **[Overview](./overview.md)** - Project objectives and goals
- **[System Architecture](./system-architecture.md)** - High-level architecture
  and component design
- **[Simulation Mode](./simulation-mode.md)** - Simulation implementation
  details
- **[Core Components](./core-components.md)** - Backend, Prometheus, Grafana
- **[Mapping & Routing](./mapping-routing.md)** - KML routes, POIs, and ETAs
- **[Development Workflow](./development-workflow.md)** - Development practices
- **[Future Enhancements](./future-enhancements.md)** - Planned features

---

## Quick Overview

This project builds a **Docker-based web application** that monitors and
visualizes real-time metrics from a **mobile Starlink terminal**.

### Key Features

- Collect or simulate real-time Starlink stats (latency, throughput,
  obstructions)
- Plot terminal's **position and trajectory** on a live map
- Support **KML route overlays**, POIs, and ETA calculations
- Store all data for historical analysis
- Run as a **self-contained Docker Compose stack**
- Provide **web dashboard** (Grafana-based) for visualization

### System Stack

```text
┌────────────────────────────────────────────┐
│                  Grafana                   │
│  ├── Starlink Stats Dashboard              │
│  ├── Map (Geomap / TrackMap)               │
│  ├── POI + ETA Panels                      │
│  └── (Optional) Control Buttons            │
└──────────────┬─────────────────────────────┘
               │ Prometheus Queries
┌──────────────┴─────────────────────────────┐
│               Prometheus                   │
│  ├── Scrapes live/simulated metrics        │
│  └── Stores all time-series data           │
└──────────────┬─────────────────────────────┘
               │ HTTP Metrics / API
┌──────────────┴─────────────────────────────┐
│   starlink-location (Python/FastAPI)       │
│  ├── API Layer (routes, pois, missions)    │
│  ├── Services (managers, calculators)      │
│  ├── Core (metrics, config, models)        │
│  ├── Simulation or Live Polling            │
│  └── /metrics (Prometheus endpoint)        │
└──────────────┬─────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │ Starlink Dish (Live)│
    │ or Simulator Engine │
    └─────────────────────┘
```

---

[Go to Full Architecture Documentation →](./system-architecture.md)

[Back to main docs](../INDEX.md)
