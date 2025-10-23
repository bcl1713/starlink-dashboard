# PRD: Prometheus Integration (Phase 3)

## 1. Introduction/Overview

This PRD defines the requirements for integrating Prometheus metrics into the
Starlink monitoring backend service. The feature enables comprehensive
time-series data collection from both simulated and live Starlink terminal
data, providing the foundation for Grafana visualization and historical
analysis.

**Problem:** The backend currently generates telemetry data but lacks a
standardized metrics endpoint for Prometheus to scrape and persist this data
over time.

**Goal:** Implement a production-ready `/metrics` endpoint that exposes all
Starlink telemetry in Prometheus format, configure Prometheus to scrape this
data at appropriate intervals, and ensure the system supports both simulation
and live modes with proper labeling and health monitoring.

---

## 2. Goals

1. Expose all Starlink telemetry metrics via a Prometheus-compatible `/metrics`
   endpoint
2. Configure Prometheus to scrape metrics at intervals suitable for real-time
   monitoring (10-15 seconds)
3. Implement appropriate metric types (Gauges, Histograms, Counters) based on
   data characteristics
4. Add rich metric labels for filtering by mode, status, and geographic context
5. Include comprehensive health checks and meta-metrics for monitoring system
   health
6. Ensure extensible data retention configuration via environment variables
7. Provide full test coverage (unit, integration, validation)
8. Document all exposed metrics with query examples

---

## 3. User Stories

1. **As a developer**, I want Prometheus to automatically scrape backend metrics
   every 10-15 seconds so I can visualize real-time telemetry in Grafana.

2. **As an operator**, I want to filter metrics by `mode="simulation"` or
   `mode="live"` so I can distinguish between test and production data.

3. **As a dashboard designer**, I want histogram metrics for latency and
   throughput so I can create percentile-based visualizations (p50, p95, p99).

4. **As a system administrator**, I want health check endpoints that expose
   Prometheus scraping status so I can monitor the monitoring system itself.

5. **As a user**, I want to configure Prometheus retention via the
   `PROMETHEUS_RETENTION` environment variable so I can balance storage costs
   with historical analysis needs.

6. **As a developer**, I want comprehensive metric documentation with example
   Prometheus queries so I can quickly build useful dashboards and alerts.

---

## 4. Functional Requirements

### 4.1 Metrics Endpoint

1. The backend MUST expose a `/metrics` endpoint on port 8000.
2. The endpoint MUST return Prometheus exposition format (text-based).
3. The endpoint MUST respond within 100ms under normal load.
4. The endpoint MUST include HELP and TYPE comments for all metrics.

### 4.2 Core Metrics - Position (Gauges)

5. `starlink_dish_latitude_degrees` - Current latitude (-90 to 90)
6. `starlink_dish_longitude_degrees` - Current longitude (-180 to 180)
7. `starlink_dish_altitude_meters` - Current altitude above sea level
8. `starlink_dish_speed_knots` - Current ground speed in knots
9. `starlink_dish_heading_degrees` - Current heading (0-360, true north)

### 4.3 Core Metrics - Network Performance (Histograms + Gauges)

10. `starlink_network_latency_ms` - Histogram with buckets [20, 40, 60, 80, 100,
    150, 200, 500]
11. `starlink_network_latency_ms_current` - Gauge for latest value
12. `starlink_network_throughput_down_mbps` - Histogram with buckets [50, 100,
    150, 200, 250, 300]
13. `starlink_network_throughput_down_mbps_current` - Gauge for latest value
14. `starlink_network_throughput_up_mbps` - Histogram with buckets [10, 20, 30,
    40, 50]
15. `starlink_network_throughput_up_mbps_current` - Gauge for latest value

### 4.4 Core Metrics - Status (Gauges)

16. `starlink_dish_obstruction_percent` - Obstruction percentage (0-100)
17. `starlink_dish_uptime_seconds` - Uptime since last boot
18. `starlink_dish_thermal_throttle` - Boolean (0 or 1) indicating thermal
    throttling
19. `starlink_dish_outage_active` - Boolean (0 or 1) indicating active outage

### 4.5 Core Metrics - POI/ETA (Gauges with labels)

20. `starlink_eta_poi_seconds{name="POI_NAME"}` - ETA to each POI in seconds
21. `starlink_distance_to_poi_meters{name="POI_NAME"}` - Distance to each POI in
    meters

### 4.6 Event Metrics (Counters)

22. `starlink_connection_attempts_total` - Total connection attempts to dish
23. `starlink_connection_failures_total` - Failed connection attempts
24. `starlink_outage_events_total` - Total outage events detected
25. `starlink_thermal_events_total` - Total thermal throttle events

### 4.7 Metric Labels

26. All metrics MUST include a `mode` label with values `simulation` or `live`.
27. Position metrics SHOULD include `region` and `zone` labels when geographic
    context is available.
28. Network metrics SHOULD include a `status` label indicating connection
    quality (`excellent`, `good`, `degraded`, `poor`).

### 4.8 Prometheus Configuration

29. Prometheus MUST scrape the backend at a 10-second interval (balancing
    real-time needs with load).
30. The scrape configuration MUST be defined in
    `monitoring/prometheus/prometheus.yml`.
31. The scrape timeout MUST be set to 5 seconds.
32. Prometheus MUST use the `PROMETHEUS_RETENTION` environment variable for data
    retention (default: `15d`).

### 4.9 Health Checks

33. The backend MUST expose a `/health` endpoint returning JSON:
    ```json
    {
      "status": "healthy",
      "mode": "simulation",
      "prometheus_last_scrape": "2025-10-23T12:34:56Z",
      "metrics_count": 25
    }
    ```
34. The `/health` endpoint MUST return HTTP 200 when healthy, 503 when degraded.

### 4.10 Meta-Metrics

35. The backend MUST expose `starlink_metrics_scrape_duration_seconds` -
    Histogram of metric collection time.
36. The backend MUST expose `starlink_metrics_generation_errors_total` - Counter
    of errors during metric generation.
37. The backend MUST expose `starlink_metrics_last_update_timestamp_seconds` -
    Unix timestamp of last successful update.

### 4.11 Testing

38. Unit tests MUST verify all metric types are correctly instantiated.
39. Unit tests MUST verify metric values fall within expected ranges (e.g.,
    latitude -90 to 90).
40. Integration tests MUST verify Prometheus can successfully scrape the
    `/metrics` endpoint.
41. Integration tests MUST verify metrics appear in Prometheus with correct
    labels.
42. Validation tests MUST check that histogram buckets contain appropriate data
    distributions.
43. Tests MUST cover both simulation and live mode scenarios.

### 4.12 Documentation

44. A `METRICS.md` file MUST document all exposed metrics with descriptions,
    types, and labels.
45. The documentation MUST include example Prometheus queries for common use
    cases:
    - Current position on map
    - Average latency over last 5 minutes
    - 95th percentile throughput
    - Outage frequency
    - ETA to specific POI
46. Inline code comments MUST explain metric bucket choices and label logic.

---

## 5. Non-Goals (Out of Scope)

1. **Custom metric aggregation** - Prometheus recording rules will be added in a
   future phase.
2. **Alerting rules** - Alert configuration is deferred to Phase 6+.
3. **Push-based metrics** - This phase uses pull-based scraping only; push
   gateways are out of scope.
4. **Multi-terminal support** - Single dish monitoring only; multi-instance
   support is a future enhancement.
5. **Authentication** - Metrics endpoint will be unauthenticated (internal
   network only).
6. **Custom exporters** - No integration with `speedtest-exporter` or
   `blackbox-exporter` at this stage.

---

## 6. Design Considerations

### Technology Choices

- **Library:** `prometheus_client` (official Python client, well-maintained)
- **Metric Types:**
  - **Gauges:** Position, status, current values (can go up or down)
  - **Histograms:** Latency, throughput (track distributions for percentiles)
  - **Counters:** Events, errors (monotonically increasing)

### Metric Bucket Design

- **Latency buckets:** Cover expected Starlink range (20-500ms) with granularity
  at lower values where most data concentrates
- **Throughput buckets:** Align with Starlink spec ranges (100-300 Mbps down,
  10-50 Mbps up)

### Label Cardinality

- Limit label values to prevent cardinality explosion
- `mode`: 2 values (simulation, live)
- `region`/`zone`: Optional, limited to predefined geographic areas
- `status`: 4 values (excellent, good, degraded, poor)
- POI labels: Limited to configured POIs (typically < 20)

---

## 7. Technical Considerations

### Dependencies

- `prometheus_client >= 0.20.0` - Official Prometheus Python client
- `fastapi` - Already used for backend API
- `asyncio` - Background metric update loop

### Prometheus Configuration

Create `monitoring/prometheus/prometheus.yml`:

```yaml
global:
  scrape_interval: 10s
  evaluation_interval: 10s

scrape_configs:
  - job_name: "starlink-location"
    static_configs:
      - targets: ["starlink-location:8000"]
    scrape_timeout: 5s
    metrics_path: /metrics
```

### Environment Variables

Extend `.env`:

```bash
PROMETHEUS_RETENTION=15d
PROMETHEUS_SCRAPE_INTERVAL=10s  # Optional override
METRICS_UPDATE_INTERVAL=3s      # How often backend updates metrics
```

### Background Update Loop

Metrics should be updated in an async background task running every 3-5 seconds
(independent of Prometheus scrape interval). This ensures fresh data on each
scrape.

### Error Handling

- Failed metric updates MUST increment `starlink_metrics_generation_errors_total`
- Failed scrapes MUST be logged with error details
- The system MUST continue operating if Prometheus is unreachable

---

## 8. Success Metrics

1. **Scrape Success Rate:** 99.9% of Prometheus scrapes succeed within timeout
2. **Scrape Duration:** P95 scrape duration < 50ms
3. **Data Freshness:** Metrics updated within 5s of actual telemetry changes
4. **Test Coverage:** 100% of metric generation code covered by unit tests
5. **Integration Success:** Prometheus successfully stores metrics with 100%
   label accuracy
6. **Documentation Completeness:** All metrics documented with working example
   queries

---

## 9. Open Questions

1. **Retention Extension:** Should we pre-configure recording rules for
   long-term aggregated storage beyond `PROMETHEUS_RETENTION`?
   - **Decision:** Defer to Phase 6, focus on raw data retention for now.

2. **Metric Naming:** Confirm naming convention follows Prometheus best
   practices (base unit in metric name, e.g., `_seconds`, `_meters`).
   - **Decision:** Yes, follow standard conventions per Prometheus docs.

3. **Remote Write:** Should we support Prometheus remote write for external
   storage (e.g., Grafana Cloud)?
   - **Decision:** Out of scope for Phase 3, add as optional Phase 9
     enhancement.

4. **Histogram vs Summary:** Should network metrics use Summary instead of
   Histogram for quantile calculations?
   - **Decision:** Use Histogram for better aggregation across instances and
     compatibility with Grafana.

5. **Cardinality Monitoring:** Should we expose cardinality metrics for POI
   labels?
   - **Decision:** Not initially; monitor Prometheus metrics count and add if
     needed.

---

## 10. Implementation Notes

### File Structure

```
backend/starlink-location/
├── app/
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── registry.py       # Metric definitions
│   │   ├── collector.py      # Update logic
│   │   └── labels.py          # Label helpers
│   ├── main.py                # FastAPI app
│   └── simulator.py           # Existing simulator
├── tests/
│   ├── test_metrics_unit.py
│   ├── test_metrics_integration.py
│   └── test_metrics_validation.py
└── requirements.txt           # Add prometheus_client
```

### Development Sequence

1. Add `prometheus_client` to requirements
2. Create metric registry in `metrics/registry.py`
3. Implement metric update logic in `metrics/collector.py`
4. Wire `/metrics` endpoint to FastAPI app
5. Add background update task to `main.py`
6. Configure Prometheus scraping
7. Write unit tests
8. Write integration tests (Docker-based)
9. Document metrics in `METRICS.md`
10. Validate with manual queries in Prometheus UI

---

## Acceptance Criteria

- [ ] `/metrics` endpoint returns valid Prometheus exposition format
- [ ] All 25+ metrics defined with correct types and labels
- [ ] Prometheus scrapes backend every 10 seconds with >99% success rate
- [ ] Histogram metrics show proper distribution in Prometheus
- [ ] Counter metrics increment correctly for events
- [ ] Labels (mode, region, status) appear correctly in all queries
- [ ] `/health` endpoint reports Prometheus scrape status
- [ ] `PROMETHEUS_RETENTION` environment variable controls data retention
- [ ] All tests pass (unit, integration, validation)
- [ ] `METRICS.md` documents all metrics with example queries
- [ ] Example Prometheus queries return expected results

---

## Appendix: Example Prometheus Queries

```promql
# Current position
starlink_dish_latitude_degrees{mode="simulation"}
starlink_dish_longitude_degrees{mode="simulation"}

# Average latency over last 5 minutes
rate(starlink_network_latency_ms_sum[5m]) / rate(starlink_network_latency_ms_count[5m])

# 95th percentile throughput
histogram_quantile(0.95, rate(starlink_network_throughput_down_mbps_bucket[5m]))

# Outage frequency (events per hour)
rate(starlink_outage_events_total[1h]) * 3600

# ETA to "Home" POI
starlink_eta_poi_seconds{name="Home"}
```
