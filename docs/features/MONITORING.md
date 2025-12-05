# Monitoring & Dashboards

**Related:** [Main README](../../README.md) |
[Setup Guide](../setup/installation.md)

## Core Monitoring Features

### Real-Time Position Tracking

Track Starlink terminal position in real-time with historical trail
visualization.

**Capabilities:**

- Live GPS coordinates (latitude, longitude, altitude)
- Interactive map display in Grafana
- Historical position trail
- Speed and heading indicators
- Position accuracy metrics

**Available In:** Simulation and Live modes

**See:** [Grafana Dashboards](#grafana-dashboards)

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

**See:** [CLAUDE.md - Storage](../../CLAUDE.md#storage--route-management)

---

## Grafana Dashboards

### Starlink Overview Dashboard

Main monitoring dashboard with comprehensive system view.

**URL:** <http://localhost:3000/d/starlink-overview>

**Panels:**

- Live position map with route overlay
- POI ETA table with countdown timers
- Network latency gauge
- Throughput graphs (download/upload)
- Signal quality indicators
- Obstruction percentage

**Use Cases:**

- Real-time flight monitoring
- Quick system health check
- Mission planning overview

### Network Metrics Dashboard

Detailed network performance analysis.

**URL:** <http://localhost:3000/d/starlink-network>

**Panels:**

- Latency trend analysis
- Throughput breakdown by time
- Packet loss visualization
- Signal quality over time
- Connection stability metrics
- Historical comparisons

**Use Cases:**

- Network troubleshooting
- Performance optimization
- SLA monitoring

### Position & Movement Dashboard

Focused location and movement tracking.

**URL:** <http://localhost:3000/d/starlink-position>

**Panels:**

- Interactive map with full history
- Altitude profile chart
- Speed trend graph
- Heading compass
- Distance traveled metrics
- Waypoint progress

**Use Cases:**

- Route tracking
- Movement analysis
- Position verification

**Configuration Guide:** See
[Grafana Setup Documentation](../grafana-configuration.md)
