# Starlink Prometheus Metrics: Complete Reference

**Overview:** [Metrics Overview](./overview.md)

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

## See Also

- [Metrics Overview](./overview.md) - Quick reference and common queries
- [Health Monitoring](./health-monitoring.md) - Health check details
- [Troubleshooting](./troubleshooting.md) - Common metrics issues
- [Prometheus Documentation](https://prometheus.io/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Metric Types](https://prometheus.io/docs/concepts/metric_types/)
