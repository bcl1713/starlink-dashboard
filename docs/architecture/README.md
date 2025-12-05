# Architecture

**Purpose**: Explain system design, technical decisions, and internal structure
**Audience**: Developers, contributors, technical evaluators

[Back to main docs](../INDEX.md)

---

## Documentation in This Category

### System Design

- **[Design Document](./design-document.md)**: Comprehensive system
  architecture, technology stack, and component design for the mobile Starlink
  terminal monitoring webapp

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
