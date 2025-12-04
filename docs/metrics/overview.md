# Starlink Prometheus Metrics: Overview

**Complete Reference:** [Metrics Reference](./reference.md)

---

## Overview

This document describes all Prometheus metrics exposed by the Starlink Location
Backend. The metrics are available at `http://localhost:8000/metrics` in
Prometheus text format.

**Metrics Scrape Configuration:**

- Interval: 10 seconds (configurable via `PROMETHEUS_SCRAPE_INTERVAL` in `.env`)
- Timeout: 5 seconds
- Format: OpenMetrics 1.0.0

---

## Metric Categories

### Position Metrics

Track the physical location and movement of the Starlink dish.

**Key metrics:**

- `starlink_dish_latitude_degrees` - Latitude position (-90 to 90)
- `starlink_dish_longitude_degrees` - Longitude position (-180 to 180)
- `starlink_dish_altitude_meters` - Altitude above sea level
- `starlink_dish_speed_knots` - Movement speed (0 to 1000+ knots)
- `starlink_dish_heading_degrees` - Direction of travel (0-360°)

---

### Network Performance Metrics

Monitor network quality and throughput in real-time.

#### Current Values (Gauges)

Instantaneous network performance values:

- `starlink_network_latency_ms_current` - Current round-trip latency
- `starlink_network_throughput_down_mbps_current` - Current download speed
- `starlink_network_throughput_up_mbps_current` - Current upload speed
- `starlink_network_packet_loss_percent` - Packet loss percentage

#### Histograms (for Percentile Analysis)

Enable calculation of p50, p95, p99 using PromQL:

- `starlink_network_latency_ms` - Latency distribution with status labels
- `starlink_network_throughput_down_mbps` - Download throughput distribution
- `starlink_network_throughput_up_mbps` - Upload throughput distribution

---

### Obstruction and Signal Quality Metrics

Track dish obstructions and signal quality:

- `starlink_dish_obstruction_percent` - Sky obstruction (0-100%)
- `starlink_signal_quality_percent` - Signal quality (0-100%, higher is better)

---

### Status and Uptime Metrics

Monitor service health and availability:

- `starlink_service_info` - Service metadata (version, mode)
- `starlink_uptime_seconds` - Service uptime
- `starlink_dish_uptime_seconds` - Dish connection uptime
- `starlink_dish_thermal_throttle` - Thermal throttle state (0/1)
- `starlink_dish_outage_active` - Outage state (0/1)

---

### Event Counter Metrics

Track cumulative events (monotonically increasing):

- `starlink_connection_attempts_total` - Total connection attempts
- `starlink_connection_failures_total` - Failed connection attempts
- `starlink_outage_events_total` - Total outage events
- `starlink_thermal_events_total` - Thermal throttle events

---

### Simulation Metrics

Track simulation system health:

- `simulation_updates_total` - Total simulation updates
- `simulation_errors_total` - Simulation errors encountered

---

### POI/ETA Metrics

Track estimated time of arrival to points of interest:

- `starlink_eta_poi_seconds{name="..."}` - ETA in seconds to named POI
- `starlink_distance_to_poi_meters{name="..."}` - Distance to named POI

---

### Meta-Metrics (System Health)

Monitor the metrics system itself:

- `starlink_metrics_scrape_duration_seconds` - Metrics collection time
- `starlink_metrics_generation_errors_total` - Metric generation errors
- `starlink_metrics_last_update_timestamp_seconds` - Last successful update

---

## Metric Labels

Labels enable filtering and aggregation in PromQL queries.

### Mode Label

- **Values:** `simulation`, `live`
- **Usage:** Filter queries by operation mode
- **Example:** `starlink_network_latency_ms{mode="simulation"}`

### Status Label

Automatic status classification based on performance:

- **excellent:** latency < 50ms AND packet loss < 1%
- **good:** latency < 100ms AND packet loss < 5%
- **degraded:** latency < 150ms OR packet loss < 10%
- **poor:** latency >= 150ms OR packet loss >= 10%

**Example:** `starlink_network_latency_ms{status="excellent"}`

### POI Name Label

- **Values:** Custom POI names/identifiers
- **Applies to:** ETA and distance metrics
- **Example:** `starlink_eta_poi_seconds{name="NYC"}`

---

## Common PromQL Queries

### Current Network Status

```promql
# Current latency
starlink_network_latency_ms_current

# Current download throughput
starlink_network_throughput_down_mbps_current

# Current upload throughput
starlink_network_throughput_up_mbps_current
```

### Percentile Analysis

```promql
# 95th percentile latency over last 5 minutes
histogram_quantile(0.95, rate(starlink_network_latency_ms_bucket[5m]))

# 50th percentile (median) latency
histogram_quantile(0.50, rate(starlink_network_latency_ms_bucket[5m]))

# 99th percentile download throughput
histogram_quantile(0.99, rate(starlink_network_throughput_down_mbps_bucket[5m]))
```

### Network Performance by Status

```promql
# Average latency for "good" status connections
rate(starlink_network_latency_ms_sum{status="good"}[5m]) / rate(starlink_network_latency_ms_count{status="good"}[5m])

# Download throughput for "excellent" connections
rate(starlink_network_throughput_down_mbps_sum{status="excellent"}[5m]) / rate(starlink_network_throughput_down_mbps_count{status="excellent"}[5m])
```

### Availability and Reliability

```promql
# Connection failure rate
rate(starlink_connection_failures_total[1h]) / rate(starlink_connection_attempts_total[1h])

# Outage frequency (events per hour)
rate(starlink_outage_events_total[1h])

# Uptime percentage
starlink_dish_uptime_seconds / (24 * 3600)  # For 24-hour window
```

### Service Health

```promql
# Is metrics collection active? (should be 1 for healthy systems)
time() - starlink_metrics_last_update_timestamp_seconds < 30

# Metrics generation error rate
rate(starlink_metrics_generation_errors_total[1h])

# Metric collection duration (should be < 5 seconds)
starlink_metrics_scrape_duration_seconds
```

### Position Tracking

```promql
# Current position
{starlink_dish_latitude_degrees, starlink_dish_longitude_degrees}

# Average speed over last 5 minutes
rate(starlink_dish_speed_knots[5m])

# Obstruction percentage
starlink_dish_obstruction_percent
```

### POI Navigation

```promql
# ETA to New York
starlink_eta_poi_seconds{name="NYC"}

# Distance to nearest airport
starlink_distance_to_poi_meters{name=~"airport.*"}
```

---

## Integration with Grafana

All metrics are automatically available in Grafana dashboards. Use the
Prometheus data source at `http://prometheus:9090` to create visualizations:

- **Gauges:** Position, altitude, speed, heading, network performance
- **Graphs:** Throughput trends, latency over time, obstruction changes
- **Heatmaps:** Latency distribution by status
- **Stat panels:** Current uptime, last scrape time, error counts

---

## Configuration

Metrics are configurable via environment variables in `.env`:

```bash
# Prometheus scrape interval (how often Prometheus collects metrics)
PROMETHEUS_SCRAPE_INTERVAL=10s

# Metrics update interval (how often backend updates collected metrics)
METRICS_UPDATE_INTERVAL=3s

# Retention period for Prometheus
PROMETHEUS_RETENTION=15d
```

---

## See Also

- [Metrics Reference](./reference.md) - Complete metric specifications
- [Health Monitoring](./health-monitoring.md) - Health check details
- [Troubleshooting](./troubleshooting.md) - Common metrics issues
