# Starlink Prometheus Metrics Documentation

## Overview

This document describes all Prometheus metrics exposed by the Starlink Location
Backend. The metrics are available at `<http://localhost:8000/metrics`> in
Prometheus text format.

**Metrics Scrape Configuration:**

- Interval: 10 seconds (configurable via `PROMETHEUS_SCRAPE_INTERVAL` in `.env`)
- Timeout: 5 seconds
- Format: OpenMetrics 1.0.0

## Position Metrics

### Latitude and Longitude

- **Metric:** `starlink_dish_latitude_degrees`
- **Type:** Gauge
- **Description:** Dish latitude in decimal degrees (-90 to 90)
- **Example:** `40.7128`

- **Metric:** `starlink_dish_longitude_degrees`
- **Type:** Gauge
- **Description:** Dish longitude in decimal degrees (-180 to 180)
- **Example:** `-74.0060`

### Altitude

- **Metric:** `starlink_dish_altitude_meters`
- **Type:** Gauge
- **Description:** Dish altitude in meters above sea level
- **Range:** -500 to 15,000+ meters (sea level to aircraft altitude)
- **Example:** `100.5`

### Speed and Heading

- **Metric:** `starlink_dish_speed_knots`
- **Type:** Gauge
- **Description:** Dish speed in knots (1 knot = 1.852 km/h)
- **Range:** 0 to 1000+ knots
- **Example:** `15.3`

- **Metric:** `starlink_dish_heading_degrees`
- **Type:** Gauge
- **Description:** Dish heading in degrees (0=North, 90=East, 180=South,
  270=West)
- **Range:** 0 to 360 degrees
- **Example:** `135.5`

## Network Performance Metrics

### Current Values (Gauges)

Current instantaneous network performance values.

- **Metric:** `starlink_network_latency_ms_current`
- **Type:** Gauge
- **Description:** Current network round-trip latency in milliseconds
- **Typical Range:** 25-150 ms
- **Example:** `45.2`

- **Metric:** `starlink_network_throughput_down_mbps_current`
- **Type:** Gauge
- **Description:** Current download throughput in Megabits per second
- **Typical Range:** 50-300 Mbps
- **Example:** `120.5`

- **Metric:** `starlink_network_throughput_up_mbps_current`
- **Type:** Gauge
- **Description:** Current upload throughput in Megabits per second
- **Typical Range:** 10-50 Mbps
- **Example:** `25.3`

- **Metric:** `starlink_network_packet_loss_percent`
- **Type:** Gauge
- **Description:** Packet loss as percentage (0-100)
- **Example:** `0.5`

### Histograms (for Percentile Analysis)

Histograms allow calculation of percentiles (p50, p95, p99) using PromQL.

- **Metric:** `starlink_network_latency_ms`
- **Type:** Histogram
- **Description:** Latency histogram for percentile analysis
- **Buckets:** [20, 40, 60, 80, 100, 150, 200, 500, +Inf] ms
- **Labels:** `mode` (simulation|live), `status` (excellent|good|degraded|poor)
- **Bucket Rationale:**
  - 20ms: Excellent/ideal performance threshold
  - 40-80ms: Good performance range
  - 100-150ms: Degraded performance range
  - 200-500ms: Poor performance range
  - 500ms+: Severe latency

- **Metric:** `starlink_network_throughput_down_mbps`
- **Type:** Histogram
- **Description:** Download throughput histogram
- **Buckets:** [50, 100, 150, 200, 250, 300, +Inf] Mbps
- **Labels:** `mode`, `status`
- **Bucket Rationale:**
  - 50 Mbps: Minimum usable throughput
  - 100-150 Mbps: Good performance
  - 200+ Mbps: Excellent performance
  - 300+ Mbps: Premium/exceptional performance

- **Metric:** `starlink_network_throughput_up_mbps`
- **Type:** Histogram
- **Description:** Upload throughput histogram
- **Buckets:** [10, 20, 30, 40, 50, +Inf] Mbps
- **Labels:** `mode`, `status`
- **Bucket Rationale:**
  - 10 Mbps: Minimum usable upload
  - 20-30 Mbps: Good upload performance
  - 40+ Mbps: Excellent upload performance

## Obstruction and Signal Quality Metrics

- **Metric:** `starlink_dish_obstruction_percent`
- **Type:** Gauge
- **Description:** Dish obstruction as percentage (0-100)
- **Interpretation:** Percentage of sky blocked from satellite view
- **Example:** `2.5` (2.5% of sky obstructed)

- **Metric:** `starlink_signal_quality_percent`
- **Type:** Gauge
- **Description:** Signal quality as percentage (0-100)
- **Range:** 0 to 100%
- **Interpretation:** Higher is better
- **Example:** `95.0`

## Status and Uptime Metrics

- **Metric:** `starlink_service_info`
- **Type:** Gauge
- **Description:** Service metadata
- **Labels:** `version`, `mode`
- **Value:** Always 1 (info metric)
- **Example:** `starlink_service_info{version="0.2.0",mode="simulation"} 1`

- **Metric:** `starlink_uptime_seconds`
- **Type:** Gauge
- **Description:** Service uptime in seconds since startup
- **Example:** `3600.5` (1 hour)

- **Metric:** `starlink_dish_uptime_seconds`
- **Type:** Gauge
- **Description:** Dish uptime in seconds
- **Example:** `86400.0` (1 day)

### Dish Status Metrics (Boolean 0/1)

- **Metric:** `starlink_dish_thermal_throttle`
- **Type:** Gauge
- **Description:** Dish thermal throttle state
- **Value:** 0 = normal, 1 = throttled (overheating)

- **Metric:** `starlink_dish_outage_active`
- **Type:** Gauge
- **Description:** Dish outage state
- **Value:** 0 = connected, 1 = outage in progress

## Event Counter Metrics

Counters only increase and never decrease (except on service restart).

- **Metric:** `starlink_connection_attempts_total`
- **Type:** Counter
- **Description:** Total number of connection attempts
- **Unit:** Count
- **Increment:** +1 on each connection attempt

- **Metric:** `starlink_connection_failures_total`
- **Type:** Counter
- **Description:** Total number of failed connection attempts
- **Unit:** Count

- **Metric:** `starlink_outage_events_total`
- **Type:** Counter
- **Description:** Total number of outage events detected
- **Unit:** Count

- **Metric:** `starlink_thermal_events_total`
- **Type:** Counter
- **Description:** Total number of thermal throttle events
- **Unit:** Count

## Simulation Metrics

- **Metric:** `simulation_updates_total`
- **Type:** Counter
- **Description:** Total number of simulation updates
- **Unit:** Updates
- **Increment Rate:** 10 Hz (0.1s intervals)

- **Metric:** `simulation_errors_total`
- **Type:** Counter
- **Description:** Total number of simulation errors
- **Unit:** Errors
- **Interpretation:** Should remain at 0 for healthy operation

## POI/ETA Metrics

- **Metric:** `starlink_eta_poi_seconds`
- **Type:** Gauge
- **Description:** Estimated time of arrival to point of interest
- **Labels:** `name` (POI name/identifier)
- **Unit:** Seconds
- **Example:** `starlink_eta_poi_seconds{name="NYC"} 3600` (1 hour to NYC)

- **Metric:** `starlink_distance_to_poi_meters`
- **Type:** Gauge
- **Description:** Distance to point of interest
- **Labels:** `name` (POI name/identifier)
- **Unit:** Meters
- **Example:** `starlink_distance_to_poi_meters{name="NYC"} 150000` (150km away)

## Meta-Metrics (System Health)

Meta-metrics monitor the metrics system itself.

- **Metric:** `starlink_metrics_scrape_duration_seconds`
- **Type:** Histogram
- **Description:** Time spent collecting metrics per update cycle
- **Buckets:** [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5] seconds
- **Unit:** Seconds
- **Interpretation:** Should stay well under 5 seconds (scrape timeout)

- **Metric:** `starlink_metrics_generation_errors_total`
- **Type:** Counter
- **Description:** Total errors during metric generation
- **Unit:** Errors
- **Interpretation:** Should remain 0 for production systems

- **Metric:** `starlink_metrics_last_update_timestamp_seconds`
- **Type:** Gauge
- **Description:** Unix timestamp of last successful metric update
- **Unit:** Seconds (Unix epoch)
- **Usage:** Health check - if current_time - value > 30s, metrics collection is
  stalled

## Metric Labels

Labels allow filtering and aggregating metrics in PromQL queries.

### Mode Label

- **Values:** `simulation`, `live`
- **Usage:** Filter queries by operation mode
- **Applies to:** Network histograms, position metrics (implicit)

### Status Label

- **Values:** `excellent`, `good`, `degraded`, `poor`
- **Thresholds:**
  - **excellent:** latency < 50ms AND packet loss < 1%
  - **good:** latency < 100ms AND packet loss < 5%
  - **degraded:** latency < 150ms OR packet loss < 10%
  - **poor:** latency >= 150ms OR packet loss >= 10%
- **Applies to:** Network histograms

### POI Name Label

- **Values:** Custom POI names/identifiers
- **Applies to:** `starlink_eta_poi_seconds`, `starlink_distance_to_poi_meters`

## Example Prometheus Queries

### Current Network Status

```promql
# Current latency
starlink_network_latency_ms_current

# Current throughput (download)
starlink_network_throughput_down_mbps_current

# Current throughput (upload)
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

## Metric Naming Conventions

Starlink metrics follow Prometheus naming conventions:

- **`_total`** suffix: Counters (monotonically increasing)
  - Example: `starlink_connection_attempts_total`

- **`_seconds`** suffix: Gauges and histograms measuring time
  - Example: `starlink_metrics_scrape_duration_seconds`

- **`_meters`** suffix: Gauges and histograms measuring distance
  - Example: `starlink_distance_to_poi_meters`

- **`_percent`** suffix: Gauges measuring percentages (0-100)
  - Example: `starlink_dish_obstruction_percent`

- **`_mbps`** suffix: Gauges/histograms for network speed
  - Example: `starlink_network_throughput_down_mbps`

- **`_knots`** suffix: Gauges for nautical speed
  - Example: `starlink_dish_speed_knots`

- **`_degrees`** suffix: Gauges for angles/coordinates
  - Example: `starlink_dish_heading_degrees`

- **`_current`** suffix: Current/instantaneous values (distinguishes from
  histograms)
  - Example: `starlink_network_latency_ms_current`

- **`_info`** suffix: Information metrics (always value=1)
  - Example: `starlink_service_info`

## Health Monitoring

### Health Endpoint

The `/health` endpoint returns:

```json
{
  "status": "ok",
  "uptime_seconds": 3600.5,
  "mode": "simulation",
  "version": "0.2.0",
  "timestamp": "2024-10-23T16:30:00.000000",
  "prometheus_last_scrape": "2024-10-23T16:29:50.000000",
  "metrics_count": 45,
  "detail": null
}
```

**Status values:**

- `"ok"`: Prometheus is actively scraping (last scrape < 30 seconds ago)
- `"degraded"`: Prometheus hasn't scraped in > 30 seconds (includes initial
  startup)

### Prometheus Scrape Status Query

```promql
# Check if Prometheus is scraping the endpoint
time() - starlink_metrics_last_update_timestamp_seconds < 30

# Alert if metrics collection is stalled (no update for 2 minutes)
ALERT MetricsCollectionStalled IF time() - starlink_metrics_last_update_timestamp_seconds > 120
```

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

## Integration with Grafana

All metrics are automatically available in Grafana dashboards. Use the
Prometheus data source at `<http://prometheus:9090`> to create visualizations:

- **Gauges:** Position, altitude, speed, heading, network performance
- **Graphs:** Throughput trends, latency over time, obstruction changes
- **Heatmaps:** Latency distribution by status
- **Stat panels:** Current uptime, last scrape time, error counts

## Troubleshooting

### Metrics Not Appearing

1. Check if backend is running: `curl <http://localhost:8000/health`>
2. Check metrics endpoint: `curl <http://localhost:8000/metrics`>
3. Check Prometheus targets: Visit `<http://localhost:9090/targets`>
4. Check last scrape time:
   `curl <http://localhost:8000/health> | jq .prometheus_last_scrape`

### High Latency or Packet Loss

Use status labels to filter:

```promql
# Queries when network is degraded
starlink_network_latency_ms{status="degraded"}
starlink_network_throughput_down_mbps{status="poor"}
```

### Memory Usage

Meta-metrics help identify collection issues:

```promql
# Collection duration (should be < 1 second typically)
starlink_metrics_scrape_duration_seconds

# Is collection healthy?
rate(starlink_metrics_generation_errors_total[5m]) == 0
```

## References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Metric Types](https://prometheus.io/docs/concepts/metric_types/)
- [Histogram Quantiles](https://prometheus.io/docs/prometheus/latest/querying/functions/#histogram_quantile)
