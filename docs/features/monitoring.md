# Monitoring & Dashboards

**Related:** [Main README](../../README.md) |
[Setup Guide](../setup/installation.md)

## Core Monitoring Features

### Real-Time Position Tracking

Track Starlink terminal position in real-time with historical trail
visualization.

**Capabilities:**

- Live GPS coordinates (latitude, longitude, altitude)
- Interactive globe display in Mission Planner
- Historical position trail
- Speed and heading indicators
- Position accuracy metrics

**Available In:** Simulation and Live modes

**See:** [Mission Planner Overview](#mission-planner-overview)

### Network Performance Monitoring

Comprehensive network metrics for latency, throughput, and connectivity.

**Metrics Tracked:**

- Latency (ping time in milliseconds)
- Download throughput (Mbps)
- Upload throughput (Mbps)
- Packet loss percentage
- Signal quality indicators
- Obstruction detection

**Available In:** Simulation and Live modes

**See:** [Metrics Documentation](../metrics/overview.md)

### Historical Data Retention

Store and query up to 1 year of metrics data (configurable).

**Features:**

- Configurable retention period (15d, 30d, 90d, 1y)
- Time-series database (Prometheus)
- Historical trend analysis
- Data export capabilities
- Automatic data cleanup

**Configuration:** `PROMETHEUS_RETENTION` in `.env`

**Storage Requirements:**

- 1 year: ~2.4 GB
- 90 days: ~600 MB
- 30 days: ~200 MB
- 15 days: ~100 MB

**See:**
[Storage Configuration](../setup/configuration/storage-configuration.md)

---

## Mission Planner Overview

Open <http://localhost:5173> for the native Overview. It displays aircraft
position and history, upcoming POIs, operational clocks, and network history.
Prometheus supplies the stored network samples through the backend API.

See [Overview features](overview.md) for settings, freshness rules, and display
behavior.
