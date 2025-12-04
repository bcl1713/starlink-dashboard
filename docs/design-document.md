# Design Document: Mobile Starlink Terminal Monitoring Webapp

**This document has been reorganized into multiple focused files.**

Please see: **[Architecture Documentation](./architecture/README.md)**

---

## Quick Links

- **[Overview & Objectives](./architecture/README.md)** - Project goals
- **[System Architecture](./architecture/README.md#system-stack)** - Component
  design
- **[Core Components](./architecture/README.md)** - Backend, Prometheus, Grafana
- **[Development Workflow](../CLAUDE.md)** - Docker rebuild process
- **[Setup Guide](./setup/README.md)** - Installation instructions

---

## Project Overview

This project builds a **Docker-based web application** that monitors and
visualizes real-time metrics from a **mobile Starlink terminal**.

### Key Features

- Real-time Starlink stats (latency, throughput, obstructions)
- Position and trajectory mapping
- KML route overlays with POIs and ETAs
- Historical data storage
- Self-contained Docker Compose stack
- Grafana-based web dashboard

### Technology Stack

- **Backend:** Python 3.13 + FastAPI
- **Metrics:** Prometheus
- **Visualization:** Grafana
- **Deployment:** Docker Compose
- **Simulation:** Full simulation mode for development

---

[Go to Full Architecture Documentation →](./architecture/README.md)

[Back to main docs](./INDEX.md)
