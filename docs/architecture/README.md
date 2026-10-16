# Architecture

**Purpose**: Explain system design, technical decisions, and internal structure
**Audience**: Developers, contributors, technical evaluators

[Back to main docs](../index.md)

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
- Retain telemetry in Prometheus for configured history windows
- Run as a **self-contained Docker Compose stack**
- Provide **web dashboard** (Mission Planner) for visualization

### System Stack

```text
Mission Planner (Nginx + native Overview)
    | same-origin backend API
    v
starlink-location (FastAPI) <----> Prometheus (history queries / metric scraping)
    |
    v
Starlink dish or simulator

Weather providers -> gfs-worker -> shared products -> starlink-location
```

---

[Go to Full Architecture Documentation →](./design-document.md)

[Back to main docs](../index.md)

## Responsive native Overview

See
[responsive layout, camera and scroll ownership](./overview-responsive-layout.md)
for the single-tree mobile/scaled-desktop implementation.

## Aviation weather

See the
[aviation weather architecture design](../superpowers/specs/2026-10-06-aviation-weather-design.md),
[source inventory](../reports/2026-10-06-aviation-weather-source-inventory.md),
and
[local rendering proof design](../superpowers/specs/2026-10-06-aviation-weather-proof-design.md)
for dated design rationale. Aviation weather is implemented: see the
[current API contract](../api/aviation-weather.md) for catalog, settings and
artifact behavior. Compose runs a demand-driven `gfs-worker` with a mailbox and
shared product artifacts; the backend serves those products read-only.
Historical proposals describe intent and are not the current endpoint contract.
