# Starlink Dashboard - Features Overview

**Related:** [Main README](../../README.md) | [Setup Guide](../setup/README.md)

This document provides a comprehensive overview of all features available in the
Starlink Dashboard system.

---

## Feature Categories

### 1. [Monitoring & Dashboards](./monitoring.md)

Core real-time position tracking, network performance metrics, historical data
retention, and Grafana dashboard details.

### 2. [Navigation & Timing](./navigation.md)

Route management (KML import, visualization), Point of Interest (POI) tracking
with real-time ETA, and flight phase detection.

### 3. [Mission Communication Planning](./mission-planning.md)

Pre-flight predictive planning tools, real-time timeline preview,
satellite geometry analysis, multi-format briefing exports, and mission
timeline visualization.

### 4. Overview Upcoming POIs

The native Overview globe projects generated operational POIs for the active
mission. Imported departure and arrival waypoint names are used as their labels;
the compact **Upcoming POIs** panel is an unscrollable Top 5 queue, while the
map retains operational context independently. In flight, ETA is a route-aware
estimate from current telemetry position and speed against active-route
geometry. Scheduled `expected_arrival_time` is provenance only;
`estimated_arrival_time` drives the live urgency colour and ordering and is not
telemetry. See the [Upcoming POIs endpoint](../api/endpoints/overview-upcoming-pois.md)
for states, timing provenance, and retention details.

This feature does not modify, retire, or replace Grafana; Grafana remains the
supported fallback and parity comparator.

### 5. [System Configuration & Simulation](./system.md)

Environment configuration, REST API documentation, and simulation mode
capabilities (realistic telemetry, route following).

---

## Related Documentation

- [Main README](../../README.md) - Quick start and overview
- [Setup Guide](../setup/README.md) - Installation instructions
- [API Reference](../api/README.md) - Complete API docs
- [Troubleshooting](../troubleshooting/README.md) - Common issues
