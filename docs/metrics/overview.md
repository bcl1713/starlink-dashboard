# Metrics overview

The backend exposes `/metrics` at <http://localhost:8000/metrics>. It returns
Prometheus text with the OpenMetrics content type and EOF marker. Use the
[reference](reference.md) for verified names, units and labels; the actual
registry and updater define the checked-out version's behavior.

The bundled Prometheus configuration scrapes `starlink-location:8000` every **1
second**, with a **1-second timeout**. Both the global and job-specific
intervals are in `monitoring/prometheus/prometheus.yml`. There is no
`PROMETHEUS_SCRAPE_INTERVAL` or `METRICS_UPDATE_INTERVAL` environment setting.
Backend updates default to 1 second and can be configured independently with
`STARLINK_UPDATE_INTERVAL_SECONDS`. Stored history uses `PROMETHEUS_RETENTION`
(example default `1y`). Changing frontend history polling or the displayed
lookback does not change scraping or retention.

Mission Planner renders Overview history through backend queries to Prometheus;
Grafana is not required. Use <http://localhost:9090> for direct queries. Adjust
host URLs if `.env` maps different ports.

## Example queries

```promql
# Prometheus can scrape the backend (1 means success)
up{job="starlink-location"}

# Current latency in milliseconds
starlink_network_latency_ms_current

# Average speed in knots over five minutes (speed is a gauge)
avg_over_time(starlink_dish_speed_knots[5m])

# Position gauges in one selector
{__name__=~"starlink_dish_(latitude|longitude)_degrees"}

# Latency p95 per operating mode, combining status buckets
histogram_quantile(0.95, sum by (le, mode) (rate(starlink_network_latency_ms_bucket[5m])))

# Mean observed latency per mode (no samples can produce NaN)
sum by (mode) (rate(starlink_network_latency_ms_sum[5m])) / sum by (mode) (rate(starlink_network_latency_ms_count[5m]))

# POI ETA; additional category and eta_type labels remain in the result
starlink_eta_poi_seconds{name="NYC"}
```

Histogram quantiles describe observations over the query window, not an
instantaneous value. Histograms retain observations from earlier status labels;
aggregate away `status` when you want the combined distribution. Gauges do not
inherit histogram `mode`/`status` labels. Prometheus adds scrape labels such as
`job` and `instance` separately.

Unavailable verified network measurements are exported as `NaN`, and do not
create histogram observations. Live dish loss clears telemetry gauges to `NaN`;
this preserves existing Prometheus history and does not simulate replacement
measurements. A scrape can succeed while no valid telemetry is available.

See [health monitoring](health-monitoring.md) and
[troubleshooting](troubleshooting.md) before interpreting zeros, missing series,
or stale-looking graphs as real-world measurements.
