# Perf 03: transient metric lifecycle

Issue [#393](https://github.com/bcl1713/starlink-dashboard/issues/393), baseline
`f0c1bd49` on 2026-10-28. The read-only scrape/frame implementation from #391 is
already present. These are controlled synthetic exporter measurements, not
measured production savings or a whole-stack acceptance claim.

## Label inventory and ownership

This inventories every labeled family in `prometheus_metrics.py`. All other
families have no mutable labels and cannot accumulate identity children.

| Families                                                                                                                                                                                        | Labels                                                                                            | Type and lifecycle                                                                                                                                                                                                                                |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `starlink_eta_poi_seconds`, `starlink_distance_to_poi_meters`                                                                                                                                   | name, category, eta_type                                                                          | Transient frame gauges. The admitted telemetry/derived producer stages the current POI list from POIManager. CRUD, category/name, phase/ETA-mode and bulk-delete notifications invalidate the frame; one replacement removes obsolete identities. |
| `starlink_route_progress_percent`, `starlink_current_waypoint_index`                                                                                                                            | route_name                                                                                        | Transient frame gauges. Current route/progress only; absent without an applicable route/observation.                                                                                                                                              |
| `starlink_route_has_timing_data`, `starlink_route_total_duration_seconds`, `starlink_route_departure_time_unix`, `starlink_route_arrival_time_unix`, `starlink_route_segment_count_with_timing` | route_name                                                                                        | Transient frame gauges. Current route only, including legitimate zero timing flag. Unknown timing measurements remain NaN.                                                                                                                        |
| `starlink_service_info`                                                                                                                                                                         | version, mode                                                                                     | Current frame metadata; previous service/version combinations disappear on replacement.                                                                                                                                                           |
| `starlink_mode_info`                                                                                                                                                                            | mode                                                                                              | Frame metadata; two bounded simulation/live children with intentional 0/1 values.                                                                                                                                                                 |
| `starlink_aircraft_position`                                                                                                                                                                    | dimension                                                                                         | Frame collector alias with three fixed dimension values; coordinates are sample values.                                                                                                                                                           |
| `mission_active_info`                                                                                                                                                                           | mission_id, route_id                                                                              | Transient mission gauge. Successful activation replaces the owner; deactivation/deletion removes the original exact labels, including old route IDs.                                                                                              |
| `mission_phase_state`, `mission_next_conflict_seconds`, `mission_timeline_generated_timestamp`, `mission_degraded_seconds`, `mission_critical_seconds`                                          | mission_id                                                                                        | Transient mission gauges. Only the active owner's updates are admitted; missing reports are absent. Helpers do not fabricate observations for inactive missions.                                                                                  |
| `mission_comm_state`                                                                                                                                                                            | mission_id, transport                                                                             | Transient mission gauge. Same owner; canonical transports X, Ka, Ku. Zero means available.                                                                                                                                                        |
| `starlink_ground_entry_point_location`                                                                                                                                                          | lat, lon, city, region, country, ip, display                                                      | Transient native gauge. Ground-entry-point publisher already tracks exact previous labels and removes them on identity change; preserved.                                                                                                         |
| `starlink_ground_entry_point_info`                                                                                                                                                              | city, region, country, ip, display, pop_id, identity_source, matched_cidr, freshness, discrepancy | Same existing GEP owner/removal pattern; source/freshness identity stays distinct.                                                                                                                                                                |
| `starlink_device_location`                                                                                                                                                                      | lat, lon, altitude                                                                                | Dormant compatibility gauge: no production publisher in the current checkout. It creates no children by declaration. Use numeric position/frame alias for current position.                                                                       |
| `starlink_eta_to_waypoint_seconds`, `starlink_distance_to_waypoint_meters`                                                                                                                      | route_name, waypoint_name                                                                         | Dormant compatibility gauges with no production publisher. Preserve names without creating fictional samples.                                                                                                                                     |
| `starlink_route_segment_speed_knots`                                                                                                                                                            | route_name, segment_index                                                                         | Dormant compatibility gauge with no production publisher.                                                                                                                                                                                         |
| `starlink_network_latency_ms`, `starlink_network_throughput_down_mbps`, `starlink_network_throughput_up_mbps`                                                                                   | mode, status (+ histogram le)                                                                     | Persistent aggregate histograms. Accepted observations only; bounded modes simulation/live/unknown and statuses excellent/good/degraded/poor/unknown. Never removed during mission/POI lifecycle.                                                 |

Unlabeled counters (connection attempts/failures, outage/thermal events,
simulation updates/errors, metric-generation errors) and the unlabeled scrape
duration histogram are persistent aggregates. They are not cleared by this work.

## Publication and concurrency

The seven mission gauges remain native `Gauge` objects for compatibility. A
single registered `MissionMetrics` collector owns their exposition, replacing
individual registration. Its short reentrant lock covers ownership changes,
exact public `Gauge.remove(*labels)` calls, value writes and copying all seven
metric families. Collection releases that lock before yielding families or
formatting bytes. The registry is not registered/unregistered during mutation.
Scrapers never acquire repository admission or perform filesystem reads.

Production lifecycle writers acquire repository admission before the mission
lock. The collector only takes the mission lock, so there is no reverse lock
order. Repeated samples with unchanged mission/route identity do not remove
children. A collected family list remains valid even after a concurrent switch.
Telemetry/POI/route publication retains its separate existing immutable frame
and compare-and-swap admission contract; this is not a new cross-collector
transaction.

Replay prepares observations privately, then publishes mission state after
runtime commit and source validation. If optional publication fails after a
verified commit, only that committed owner's active identity remains; obsolete
dynamic values are removed. A superseded tick cannot replace a successor.
Terminal replay cancellation/failure removes its mission children. Persisted
selection reconciliation does not resurrect terminal replay metrics while that
replay selection remains attached.

The existing reconciliation owner also restores unpaced simulation/live mission
identity after restart and handles external deactivation. Simulation now uses
the same reconciliation loop as live: executor wakeups every 250 ms, with the
existing cache limiting inventory checks to once per second unless a local
mutation invalidates it. This additional simulation work is a tradeoff; the
exporter microbenchmark does not measure it.

## Consumer compatibility and history

No family name, label key, position alias, transport encoding or CSV column
changes. Existing schema/compatibility tests and historical CSV tests cover
those interfaces. There are no tracked Grafana dashboard definitions in this
checkout; the documented [Grafana/PromQL queries](../metrics/overview.md) retain
their selectors. External dashboards were not inspected. The current Overview
uses the application APIs, whose telemetry/source contracts are unchanged.

Inactive mission series are now **absent**, replacing the previous inconsistent
mix of stale 1, unrelated empty-route 0 and retained NaN children. Consumers
should select `mission_active_info == 1`; absence means no currently published
owner. A missing ETA remains NaN, an unobserved measurement is never assigned 0,
and actual zero transport/duration/timing values retain their meaning.

Removing exporter children stops future samples. Prometheus staleness handling
removes them from instant queries after the next successful scrape, but earlier
samples remain queryable with their original labels. TSDB head series can
include retained stale identities. Retention/compaction and disk recovery are
separate; this change neither deletes historical series nor claims immediate
disk-space recovery. The real Prometheus control checks both current absence and
disjoint retained history for synthetic missions 0 and 1.

## Reproduce the controls

Use the tracked backend Python environment and a wall-clock limit. From
`backend/starlink-location`, substitute an archived baseline backend root to run
the identical workload against baseline code:

```sh
timeout --kill-after=10s 10m uv run --with-requirements requirements.txt \
  python ../../tools/benchmark_metric_lifecycle.py --backend-root .

STARLINK_TEST_DATA_DIR=/tmp/issue393-tests timeout --kill-after=10s 10m \
  uv run --with-requirements requirements.txt pytest \
  --basetemp=/tmp/issue393-pytest \
  tests/unit/test_mission_metric_lifecycle.py \
  tests/integration/test_metric_poi_label_lifecycle.py \
  tests/integration/test_metrics_replay_commit.py
```

The benchmark performs 200 deactivate/activate/route-label changes, writes all
mission gauges, measures 100 warmed scrapes, then clears the final owner. It
reports sample/byte counts, retained traced Python allocation, process peak RSS,
mutation wall time, scrape CPU and p50/p95/p99 latency. Tracing is disabled for
scrape timing. Peak RSS includes imports and is not a leak slope.

From repository root, use an existing backend dependency image for the focused
real Prometheus control (this source mount is not production-image acceptance):

```sh
timeout --kill-after=90s 10m python3 tools/check_metric_lifecycle_prometheus.py \
  --exporter-image YOUR_BACKEND_IMAGE \
  --backend-root backend/starlink-location \
  --output /tmp/issue393-evidence/prometheus
```

Use `--baseline` with an archived baseline root to record the known stale
behavior instead of requiring corrected cardinality. The control records its
PID/process group, task-specific Compose project, image identities, private
volume and temporary paths before startup. It preserves logs and summaries, then
tears down containers/network/volume in `finally` and verifies empty
project-scoped listings. TERM enters cleanup; allow its 90-second termination
grace. After forced termination inspect `owner.json` and remove only that
project's resources. No workers/services are intentionally retained.

## Measurements and limits

Three baseline and three final candidate microbenchmark runs, reporting medians
unless a count is exact:

| Measurement after 200 transitions          |                Baseline |             Candidate |
| ------------------------------------------ | ----------------------: | --------------------: |
| Mission samples before final clear         |                   1,999 |                     9 |
| Mission samples after final clear          |                   2,000 |                     0 |
| Exporter bytes before final clear          |                 138,031 |                12,090 |
| Scrape p50 / p95 / p99 (ms)                | 9.543 / 11.386 / 13.379 | 0.352 / 0.507 / 0.597 |
| CPU seconds for 100 scrapes                |                   0.986 |                 0.037 |
| Retained traced Python bytes               |               1,410,340 |               206,048 |
| Process peak RSS (KiB)                     |                  66,716 |                66,376 |
| Mutation wall time for 200 transitions (s) |                   0.094 |                 0.129 |

Exporter bytes decreased 91.2%, median scrape p95 decreased 95.6%, and retained
traced allocations decreased 85.4% in this fixture. Mutation work increased
37.4% (about 0.18 ms extra per transition) because exact child removal replaces
the previous cheap accumulating writes. RSS was effectively unchanged. The first
pair was visibly affected by concurrent host work: baseline p95 ranged
9.533–49.573 ms across runs and candidate p95 ranged 0.361–0.645 ms. Do not
interpret these figures as capacity budgets or production gains.

The real Prometheus fixture used 202 transitions, holding the first two and
final identities long enough for 1 Hz ingestion and measuring a final 10-second
scrape window. The baseline exposed 403 mission-info series before clear and 404
after; the candidate exposed 1 and 0. Real scrape p50/p95/p99 were
56.485/67.609/71.533 ms before and 1.454/1.740/1.874 ms after in this single
paired run. TSDB head series, including Prometheus self-monitoring and retained
history, were 2,684 and 691 respectively; these counts are sampling-dependent
and are not a bound on long-term retained cardinality. Both runs retained
distinct synthetic-0 and synthetic-1 histories, and histogram count stayed 1
across every transition.

Compact [microbenchmark evidence](metric-lifecycle-2026-10-28/before.json),
[candidate evidence](metric-lifecycle-2026-10-28/after.json),
[Prometheus baseline](metric-lifecycle-2026-10-28/prometheus-before.json),
[Prometheus candidate](metric-lifecycle-2026-10-28/prometheus-after.json), and
project-scoped cleanup records are checked in. The dependency image was
`perf391-diag-408-corrected-c-backend:31b1fbbf` at image ID
`sha256:a703a9660e84b151e3e2ffa86c09c5b6d17c490bb4a34003d121c97e6fad5046`;
current/baseline source was mounted read-only and executed as its appuser.

Host: Intel i9-10900K, 20 logical CPUs, Linux x86_64, Python 3.11.16. The
microbenchmark is single-process, no browser, no network source and no mission
filesystem workload. Real Prometheus uses v3.5.0, 1 Hz scrape and disposable
synthetic fixture data. Detailed evidence is retained under
`/tmp/issue393-evidence`; compact measurements accompany this report.

The 200-edit POI integration control uses real POIManager CRUD, route manager
replacement, phase/ETA-mode changes and the actual derived-refresh owner. It
verifies exactly current names/categories/route names, unknown NaNs, genuine
zero timing flags and empty families after deletion. Concurrent mission
mutation/scrape tests verify a single consistent owner, while existing replay,
preflight, source-admission and read-only HTTP tests protect provenance.

Full production-image/Nginx/browser acceptance and sustained production-like
soaks are separate gates before approval/merge. These scoped controls do not
claim to have passed those gates. Rollback is a revert of this PR, restoring the
known baseline stale-series behavior; it does not alter TSDB history.
