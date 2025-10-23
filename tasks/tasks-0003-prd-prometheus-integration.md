# Task List: Prometheus Integration (Phase 3)

> Generated from: `0003-prd-prometheus-integration.md`

## Current State Assessment

The codebase already has foundational Prometheus integration:
- ✅ Basic metrics registry (`app/core/metrics.py`)
- ✅ `/metrics` endpoint (`app/api/metrics.py`)
- ✅ Background update loop updating metrics
- ✅ Prometheus scraping configured (currently at 1s interval)
- ✅ Basic Gauges for position, network, and status
- ✅ Counters for simulation updates and errors

**What's Missing for PRD Compliance:**
- ❌ Histogram metrics for latency and throughput (percentile analysis)
- ❌ Rich metric labels (`mode`, `region`, `zone`, `status`)
- ❌ Additional event counters (connection attempts, failures, outages, thermal events)
- ❌ POI/ETA metrics with labels
- ❌ Meta-metrics for monitoring the monitoring system
- ❌ Enhanced `/health` endpoint with Prometheus scrape status
- ❌ Optimized Prometheus scrape interval (10s instead of 1s)
- ❌ Environment variable for scrape interval override
- ❌ Comprehensive test coverage
- ❌ `METRICS.md` documentation with example queries

## Relevant Files

**Core Implementation:**
- `backend/starlink-location/app/core/metrics.py` - Metric registry and definitions (NEEDS ENHANCEMENT)
- `backend/starlink-location/app/core/labels.py` - Label helper functions (TO BE CREATED)
- `backend/starlink-location/app/api/metrics.py` - `/metrics` endpoint handler (MINOR UPDATES)
- `backend/starlink-location/app/api/health.py` - Health endpoint (NEEDS ENHANCEMENT)
- `backend/starlink-location/main.py` - Background update loop (MINOR UPDATES)

**Configuration:**
- `monitoring/prometheus/prometheus.yml` - Prometheus scrape config (NEEDS UPDATE)
- `.env` - Environment variables (NEEDS NEW VARS)
- `backend/starlink-location/requirements.txt` - Python dependencies (ALREADY HAS prometheus_client)

**Testing:**
- `backend/starlink-location/tests/unit/test_metrics.py` - Unit tests for metrics (EXISTS, NEEDS EXPANSION)
- `backend/starlink-location/tests/unit/test_labels.py` - Unit tests for label helpers (TO BE CREATED)
- `backend/starlink-location/tests/unit/test_metric_validation.py` - Value range validation tests (TO BE CREATED)
- `backend/starlink-location/tests/integration/test_metrics_endpoint.py` - Integration tests (EXISTS, NEEDS EXPANSION)
- `backend/starlink-location/tests/integration/test_prometheus_scraping.py` - Prometheus scraping tests (TO BE CREATED)
- `backend/starlink-location/tests/integration/test_histogram_distribution.py` - Histogram validation (TO BE CREATED)

**Documentation:**
- `docs/METRICS.md` - Comprehensive metrics documentation (TO BE CREATED)

### Notes

- The project uses `pytest` for testing. Run tests with:
  ```bash
  /home/brian/Projects/starlink-dashboard/backend/starlink-location/venv/bin/python -m pytest
  ```
- Prometheus client library is already installed (`prometheus-client>=0.19.0`)
- Existing metrics use a custom `REGISTRY` to avoid conflicts with default registry
- Background update loop runs at 0.1s (10 Hz), much faster than Prometheus scrape interval

## Tasks

- [x] 1.0 Enhance Metrics Registry with Histograms, Counters, and Labels
  - [x] 1.1 Add Histogram metric `starlink_network_latency_ms` with buckets `[20, 40, 60, 80, 100, 150, 200, 500]` for percentile analysis
  - [x] 1.2 Add Histogram metric `starlink_network_throughput_down_mbps` with buckets `[50, 100, 150, 200, 250, 300]`
  - [x] 1.3 Add Histogram metric `starlink_network_throughput_up_mbps` with buckets `[10, 20, 30, 40, 50]`
  - [x] 1.4 Rename existing gauge metrics to `*_current` (e.g., `starlink_network_latency_ms_current`) to distinguish from histograms
  - [x] 1.5 Add Counter `starlink_connection_attempts_total` to track connection attempts
  - [x] 1.6 Add Counter `starlink_connection_failures_total` to track failed connections
  - [x] 1.7 Add Counter `starlink_outage_events_total` to track outage occurrences
  - [x] 1.8 Add Counter `starlink_thermal_events_total` to track thermal throttle events
  - [x] 1.9 Add Gauge `starlink_dish_uptime_seconds` for dish uptime (if not already present)
  - [x] 1.10 Add Gauge `starlink_dish_thermal_throttle` as boolean (0/1) for current thermal state
  - [x] 1.11 Add Gauge `starlink_dish_outage_active` as boolean (0/1) for current outage state
  - [x] 1.12 Update `update_metrics_from_telemetry()` to populate both histogram and gauge versions of network metrics
  - [x] 1.13 Add inline comments explaining histogram bucket choices based on Starlink performance ranges

- [x] 2.0 Implement Label Management System
  - [x] 2.1 Create new file `backend/starlink-location/app/core/labels.py`
  - [x] 2.2 Implement `get_mode_label(config) -> str` function returning "simulation" or "live"
  - [x] 2.3 Implement `get_status_label(latency_ms, packet_loss_percent) -> str` function returning "excellent", "good", "degraded", or "poor" based on thresholds
  - [x] 2.4 Implement `get_geographic_labels(latitude, longitude) -> dict` function returning region/zone labels (stub for now, can be enhanced later)
  - [x] 2.5 Implement `apply_common_labels(metric, telemetry, config) -> dict` helper that returns all applicable labels for a metric
  - [x] 2.6 Update all metrics in `app/core/metrics.py` to accept label parameters (e.g., `labelnames=['mode', 'status']`)
  - [x] 2.7 Update `update_metrics_from_telemetry()` to compute labels using label helpers and apply them when setting metric values
  - [x] 2.8 Update `set_service_info()` call in `main.py` to use label helpers

- [x] 3.0 Add POI/ETA Metrics and Meta-Metrics
  - [x] 3.1 Add Gauge `starlink_eta_poi_seconds` with labelname `['name']` for ETA to each POI
  - [x] 3.2 Add Gauge `starlink_distance_to_poi_meters` with labelname `['name']` for distance to each POI
  - [ ] 3.3 Add placeholder logic to update POI metrics (stub with sample POIs if actual POI system not yet implemented)
  - [x] 3.4 Add Histogram `starlink_metrics_scrape_duration_seconds` with default buckets to track metric collection time
  - [x] 3.5 Add Counter `starlink_metrics_generation_errors_total` to track metric generation errors
  - [x] 3.6 Add Gauge `starlink_metrics_last_update_timestamp_seconds` to track last successful metric update timestamp
  - [x] 3.7 Update `_background_update_loop()` in `main.py` to track start/end time of metric updates and record to scrape_duration histogram
  - [x] 3.8 Update `_background_update_loop()` error handling to increment `generation_errors_total` counter
  - [x] 3.9 Update `_background_update_loop()` to set `last_update_timestamp_seconds` after successful update

- [ ] 4.0 Enhance Health Endpoint and Configure Prometheus Scraping
  - [ ] 4.1 Add `last_scrape_time` tracking in `app/api/metrics.py` - record timestamp on each `/metrics` request
  - [ ] 4.2 Create module-level variable or shared state to store last scrape timestamp accessible to health endpoint
  - [ ] 4.3 Update `/health` endpoint in `app/api/health.py` to include `prometheus_last_scrape` field with ISO 8601 timestamp
  - [ ] 4.4 Update `/health` endpoint to include `metrics_count` field by inspecting REGISTRY
  - [ ] 4.5 Implement health status logic: return 200 if last scrape < 30s ago, otherwise 503 (degraded)
  - [ ] 4.6 Update `monitoring/prometheus/prometheus.yml` to set global `scrape_interval: 10s` (currently 15s)
  - [ ] 4.7 Update `monitoring/prometheus/prometheus.yml` to set job-specific `scrape_interval: 10s` (currently 1s)
  - [ ] 4.8 Keep `scrape_timeout: 5s` as-is in prometheus.yml
  - [ ] 4.9 Add `PROMETHEUS_SCRAPE_INTERVAL=10s` to `.env` file with comment explaining override capability
  - [ ] 4.10 Add `METRICS_UPDATE_INTERVAL=3s` to `.env` file for background loop interval (currently hardcoded at 0.1s)
  - [ ] 4.11 Update `main.py` to read `METRICS_UPDATE_INTERVAL` from environment and use in background loop sleep

- [ ] 5.0 Implement Comprehensive Testing Suite
  - [ ] 5.1 Expand `tests/unit/test_metrics.py` to verify all histogram metrics are correctly instantiated
  - [ ] 5.2 Expand `tests/unit/test_metrics.py` to verify all new counter metrics are correctly instantiated
  - [ ] 5.3 Create `tests/unit/test_labels.py` to test `get_mode_label()` with simulation and live configs
  - [ ] 5.4 Add tests in `test_labels.py` for `get_status_label()` covering all 4 status levels
  - [ ] 5.5 Add tests in `test_labels.py` for `get_geographic_labels()` with various coordinates
  - [ ] 5.6 Add tests in `test_labels.py` for `apply_common_labels()` integration
  - [ ] 5.7 Create `tests/unit/test_metric_validation.py` to test latitude range (-90 to 90)
  - [ ] 5.8 Add tests in `test_metric_validation.py` for longitude range (-180 to 180)
  - [ ] 5.9 Add tests in `test_metric_validation.py` for heading range (0 to 360)
  - [ ] 5.10 Add tests in `test_metric_validation.py` for latency values (> 0)
  - [ ] 5.11 Add tests in `test_metric_validation.py` for throughput values (>= 0)
  - [ ] 5.12 Expand `tests/integration/test_metrics_endpoint.py` to verify `/metrics` returns valid Prometheus format
  - [ ] 5.13 Add test in `test_metrics_endpoint.py` to verify response time < 100ms
  - [ ] 5.14 Add test in `test_metrics_endpoint.py` to verify HELP and TYPE comments are present
  - [ ] 5.15 Create `tests/integration/test_prometheus_scraping.py` with Docker-based test that starts Prometheus and verifies scraping works
  - [ ] 5.16 Add test in `test_prometheus_scraping.py` to verify metrics appear in Prometheus with correct labels
  - [ ] 5.17 Add test in `test_prometheus_scraping.py` to verify scrape interval is 10s
  - [ ] 5.18 Create `tests/integration/test_histogram_distribution.py` to verify histogram buckets contain data
  - [ ] 5.19 Add test in `test_histogram_distribution.py` to verify latency histogram has samples across buckets
  - [ ] 5.20 Add test in `test_histogram_distribution.py` to verify throughput histograms have samples across buckets
  - [ ] 5.21 Add tests covering both simulation and live mode scenarios (parametrized tests)

- [ ] 6.0 Create Metrics Documentation
  - [ ] 6.1 Create `docs/METRICS.md` file
  - [ ] 6.2 Add documentation header and introduction explaining the metrics system
  - [ ] 6.3 Document all position metrics (latitude, longitude, altitude, speed, heading) with types, ranges, and labels
  - [ ] 6.4 Document all network performance metrics (latency, throughput) including both histogram and gauge versions
  - [ ] 6.5 Document histogram bucket choices and rationale
  - [ ] 6.6 Document all status metrics (obstruction, uptime, thermal_throttle, outage_active)
  - [ ] 6.7 Document all event counter metrics (connection_attempts, failures, outages, thermal_events)
  - [ ] 6.8 Document POI/ETA metrics with label explanation
  - [ ] 6.9 Document meta-metrics (scrape_duration, generation_errors, last_update_timestamp)
  - [ ] 6.10 Document all label types (mode, region, zone, status) with possible values
  - [ ] 6.11 Add "Example Prometheus Queries" section with query for current position on map
  - [ ] 6.12 Add example query for average latency over last 5 minutes
  - [ ] 6.13 Add example query for 95th percentile throughput
  - [ ] 6.14 Add example query for outage frequency (events per hour)
  - [ ] 6.15 Add example query for ETA to specific POI
  - [ ] 6.16 Add "Metric Naming Conventions" section explaining suffix usage (_seconds, _meters, _total, etc.)
  - [ ] 6.17 Add inline code comments to `app/core/metrics.py` explaining bucket choices for histograms

---

**Status:** ✅ Detailed sub-tasks generated. Ready for implementation.

**Total Sub-tasks:** 79

**Estimated Effort:** 2-3 days for a junior developer
