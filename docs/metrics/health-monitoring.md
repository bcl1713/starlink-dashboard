# Metrics health monitoring

`GET /health` checks backend initialization and recent requests to `/metrics`.
It is distinct from Prometheus target health and from valid dish telemetry.

```bash
curl --fail --max-time 10 http://localhost:8000/health
curl --fail --max-time 10 http://localhost:9090/api/v1/targets
```

## Response semantics

Before the coordinator is initialized, health returns HTTP 503. An initialized
server returns HTTP 200 for both `status: "ok"` and `status: "degraded"`:

- `ok`: `/metrics` was requested less than 30 seconds ago.
- `degraded`: no metrics request yet, or the most recent request is at least 30
  seconds old. A `detail` string explains this state.

Any `/metrics` request updates the scrape timestamp, including a manual curl;
this is not proof that Prometheus scraped or stored the response successfully.
Use Prometheus `up{job="starlink-location"}` and target `lastError` for that.

Common fields include `status`, `uptime_seconds`, `mode`, `message`, `version`,
`timestamp`, `prometheus_last_scrape`, and `metrics_count`.
`prometheus_last_scrape` is null before the first metrics request.
`metrics_count` counts collected metric families, not individual samples, and is
not fixed at 45. `detail` is omitted when there is no explanation to report.

`dish_connected` is present only in live mode. An `ok` health response can still
have `dish_connected: false`. Check connectivity and measurement freshness
separately. Flight phase, ETA mode, active route identifiers, timing flags,
scheduled/actual timestamps and countdowns are attached when the corresponding
state is available; do not assume every field exists or has a non-null value.

The current handler's `version` string is hard-coded to `0.2.0`; it does not
identify the deployed v1.0.0 release or current source revision. Use reviewed
image tags and image revision labels for deployment provenance.

## Useful Prometheus checks

```promql
# Successful Prometheus HTTP scrape
up{job="starlink-location"}

# Seconds since an ordinary successful background metric update
time() - starlink_metrics_last_update_timestamp_seconds

# Metric-update errors per second
rate(starlink_metrics_generation_errors_total[5m])

# Mean metric-update duration in seconds
rate(starlink_metrics_scrape_duration_seconds_sum[5m]) / rate(starlink_metrics_scrape_duration_seconds_count[5m])
```

The update timestamp is separate from the health endpoint's last scrape time. A
stalled timestamp can indicate unavailable telemetry, stopped background
updates, or a different replay update path. Avoid treating one expression as a
complete connectivity or replay-health alarm. PromQL comparisons without `bool`
filter matching samples; they do not automatically return a 0/1 health gauge.

## Alert limitations

The bundled `monitoring/prometheus/rules/mission-alerts.yml` contains mission
window rules. Its current `mission_next_conflict_seconds{status="degraded"}` and
`{status="critical"}` selectors require a `status` label that the registry does
not define for that family (it defines only `mission_id`). Do not rely on those
rules for operational notification until the exporter/rule contract is aligned
and verified. The local Compose stack does not configure Alertmanager or a
notification receiver.

See [metrics reference](reference.md) and [troubleshooting](troubleshooting.md).
