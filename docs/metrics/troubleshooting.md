# Metrics troubleshooting

Start with the maintained
[metrics and history diagnostics](../troubleshooting/metrics-monitoring.md).
They cover endpoint reachability, Prometheus targets, same-origin API checks,
and the configured 1-second scrape cadence.

A successful HTTP scrape does not prove that measurements are available. Inspect
`/health` mode and live-only `dish_connected`, then examine `/metrics` for
`NaN`, missing labeled samples, or valid values. Live outages clear telemetry
gauges instead of publishing simulated replacements; historical samples remain.
A manual `/metrics` request also refreshes the health scrape timestamp.

Missing POI/route series can reflect absent active data, unavailable timing,
freshness validation, or no instantiated label set. Check Mission Planner and
backend logs before creating replacement data. POI metrics have `name`,
`category` and `eta_type` labels; histogram families use their own labels. Use
[verified names and units](reference.md), especially altitude in feet and
histogram `_bucket`, `_sum`, `_count` samples.

For stationary simulation positions, check active route/replay completion and
configured mode. `simulation_updates_total` is a shared-updater counter and
cannot prove simulation mode. Ordinary update metadata does not track every
paced-replay path; see [health semantics](health-monitoring.md).

If series churn or storage grows, measure actual series cardinality and resource
usage. Avoid unbounded dynamic label values. No fixed 100-POI capacity limit is
established here. Retention bounds history, not Prometheus RAM; a storage-size
flag is not a memory limit. Preserve the existing config-file argument when
changing Prometheus command options, and see
[storage configuration](../setup/configuration/storage-configuration.md).

Do not reset files, prune Docker data, or delete volumes as a metrics repair.
Capture sanitized logs and the checked-out version before changing settings.
