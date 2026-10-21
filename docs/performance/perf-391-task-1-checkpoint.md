# Issue 391 Task 1 checkpoint

Specification and six-task plan approved at `c7792320`. Task 1 only is
implemented on `perf/391-readonly-metrics`, PR #403. **Stop for review:** Tasks
2–6, production registration/writers, deployment, merge and issue closure are
not authorized by this checkpoint. The existing application still has its
original scrape behavior.

## Foundation and boundaries

[frames.py](../../backend/starlink-location/app/core/metrics/frames.py) adds
frozen scalar identities, nested immutable sample tuples, immutable publication
heads, a one-head store, one public-API collector and limited gauge views. No
application file imports or registers the new collector yet.

Preparation owns temporary dictionaries in a thread/task-scoped context. Label
binding alone creates no visible child; writes outside that context fail.
Sealing detaches and validates a complete schema. The owner explicitly publishes
against its captured head after source admission. Abandonment discards staging;
an admitted preparation failure calls `fail(expected, reason)`. A context does
not automatically mark failure because it cannot know admission or whether work
was deliberately abandoned. An obsolete publish/failure cannot replace a newer
head. Invalidation increments the input revision and publishes pending status.

A reader captures one head and emits all 29 families and the position alias from
it. Validation, label/value conversion, allocation, family construction and
serialization stay outside the pointer mutex. Pending/failed collection masks
the coupled domain to NaN while retaining old labels and the old metric-update
timestamp. It retains the last committed frame internally. Valid publication
recovers without a retry worker. Field-specific ordinary unavailability remains
Task 2 producer work; lifecycle admission remains Tasks 3–4.

The existing registry, standard serializers and all 18 independent Gauges, seven
Counters and four Histograms are untouched. There are no private-client
accesses, mutable Gauge shadows, text encoder, whole-registry retries or
retained generation chain in the foundation. The isolated standard-Gauge control
exists only in tests to compare exposition.

Views deliberately support only positional/keyword `.labels()`, context-only
`.set()`, and whole-family `.collect()`. A bound view's collect returns its
whole family; it does not emulate raw Gauge child collection. Views are not
Gauge instances and have no `_value`, `_metrics`, clear/remove/inc/dec or
callback-gauge emulation. No operational caller requires those coupled methods.
Import shims stay unchanged; their existing 70-object identity regression covers
all 29 names. Sequential individual view reads are not a multi-family snapshot;
registry collection must use the single full collector.

## Compatibility and consumer audit

The
[frozen schema](../../backend/starlink-location/tests/fixtures/metrics-coupled-schema.json)
records all 29 names, help strings and label orders from `c7792320`. Tests
compare actual existing public Gauge metadata, exact standard-registry text
including escaped labels, type/unit, NaN behavior and position alias dimensions.
The [consumer inventory](probes/perf391-task1-consumers.json) records each
family's definition/import/call/read references and generic consumers, with
file/line/source evidence. AST tracing was supplemented by repository-wide
search and manual inspection for dynamic handles and private registry access.

Every row below has prefix `starlink_`. All 29 are re-exported unchanged by
`app.core.metrics` and its legacy module; normal reads use registry/sample
collection. `U` = `app/core/metrics/metric_updater.py`, `E` =
`app/api/metrics_export.py`, `C` = `app/simulation/coordinator.py`, `M` =
`main.py`.

| Family                                | Existing writers                 |
| ------------------------------------- | -------------------------------- |
| dish_latitude_degrees                 | U                                |
| dish_longitude_degrees                | U                                |
| dish_altitude_feet                    | U                                |
| dish_speed_knots                      | U                                |
| dish_heading_degrees                  | U                                |
| network_latency_ms_current            | U                                |
| network_throughput_down_mbps_current  | U                                |
| network_throughput_up_mbps_current    | U                                |
| network_packet_loss_percent           | U                                |
| dish_obstruction_percent              | U                                |
| signal_quality_percent                | U                                |
| uptime_seconds                        | U                                |
| eta_poi_seconds                       | U, E via dynamic registry lookup |
| distance_to_poi_meters                | U, E via dynamic registry lookup |
| flight_phase                          | U                                |
| eta_mode                              | U                                |
| flight_departure_time_unix            | U                                |
| flight_arrival_time_unix              | U                                |
| time_until_departure_seconds          | U                                |
| route_progress_percent                | U, C                             |
| current_waypoint_index                | U, C                             |
| route_has_timing_data                 | E                                |
| route_total_duration_seconds          | E                                |
| route_departure_time_unix             | E                                |
| route_arrival_time_unix               | E                                |
| route_segment_count_with_timing       | E                                |
| service_info                          | U                                |
| mode_info                             | U                                |
| metrics_last_update_timestamp_seconds | M                                |

**Integration constraint:** E currently uses private
`REGISTRY._names_to_collectors` to obtain ETA/distance Gauge objects. After full
collector registration those names resolve to the collector, which intentionally
has no `.labels()`/`.set()`. Remove this path through the approved read-only
scrape work before treating an integrated candidate as runnable. Do not add a
collector proxy or preserve that private dependency. This is an existing caller,
not a new foundation dependency; Tasks 2–5 require coordinated integration.

The autouse fixture in `tests/conftest.py` uses `isinstance(Gauge)`,
`REGISTRY._collector_to_names`, `_metrics` and direct position-dictionary
writes. Task 2 must replace coupled resets with explicit frames while preserving
independent resets. `_current_position` is read by PositionCollector and
`/position-table`; their planned replacement must use one captured frame. The
remaining `_value.get()` tests concern independent mission instruments and need
no coupled proxy. History seed tooling consumes metric names on the wire, not
Python Gauge objects. General label/cardinality cleanup remains #393.

## Verification and review

Both client **0.19.0 and 0.26.0 passed 72 focused tests each**: 30 foundation
checks plus existing metrics, exporter, ETA and import regressions. They cover
barrier-paused readers, concurrent writer/three-reader/invalidation stress,
source revision changes, stale success/failure, abandoned/failed preparation,
0/10/100/1,100 POIs, duplicate labels, retained iterators, weak-reference
retention, source/replay timestamps, custom registries and mutex release.
Independent Counter/Histogram checks include idle label initialization,
buckets/count/sum, exemplars/created series and an independent read callback.

Independent review passed all 30 foundation tests at both versions against
matching hashes. It found no remaining Critical/Important issue. The two
inherited-context ownership failures were reproduced before their fix.
Black/Ruff checks on all added Python files pass.

The broad backend attempt collected 4,322 tests and hit its ten-minute limit
(exit 124), during a SIGMET decoder worker timeout test (the final log flushed
after termination). It recorded 3,663 passes and 58 failures before timeout. The
[complete observed failure list](probes/perf391-task1-suite-results.json) is
retained; **no full-suite success is claimed**. An isolated GFS vertical check
reproduced missing `eccodes` in the cached test environment (13 passes, 1
failure). That diagnosis does not prove every broad failure has that cause. The
application files involved are unchanged. Full declared-environment acceptance
and the remaining regressions stay future gates.

## Component measurements

[Executable measurement](probes/perf391_frames.py) and
[complete component results](probes/perf391-task1-results.json). Each row uses
200 iterations after ten warm-ups on Python 3.11.16, on the host. These are
sequential component runs with no task-owned suite overlap, not the Docker
application baseline. Quantiles are median/nearest-rank p95; CPU uses thread
time, wall latency is recorded separately. Allocation runs use tracemalloc
separately from timing. No CPU affinity or statistical application-speedup claim
is made.

| Client | POIs |   Freeze ms | Stage/seal ms | Validated publish ms |  Collect ms | Serialize ms |
| ------ | ---: | ----------: | ------------: | -------------------: | ----------: | -----------: |
| 0.19.0 |    0 | 0.013/0.015 |   0.062/0.064 |          0.005/0.006 | 0.032/0.034 |  0.095/0.101 |
| 0.19.0 |   10 | 0.020/0.022 |   0.092/0.095 |          0.011/0.014 | 0.043/0.044 |  0.144/0.265 |
| 0.19.0 |  100 | 0.073/0.089 |   0.352/0.405 |          0.023/0.023 | 0.128/0.131 |  0.576/0.604 |
| 0.19.0 | 1100 | 0.860/0.964 |   3.507/3.965 |          0.185/0.189 | 1.158/1.705 |  5.428/7.762 |
| 0.26.0 |    0 | 0.013/0.014 |   0.060/0.071 |          0.005/0.006 | 0.030/0.031 |  0.201/0.285 |
| 0.26.0 |   10 | 0.019/0.020 |   0.090/0.097 |          0.007/0.007 | 0.040/0.042 |  0.214/0.239 |
| 0.26.0 |  100 | 0.073/0.076 |   0.350/0.362 |          0.023/0.023 | 0.128/0.135 |  0.952/0.987 |
| 0.26.0 | 1100 | 0.828/0.895 |   3.541/3.966 |          0.185/0.194 | 1.198/1.516 | 9.479/11.022 |

Freeze copies already detached samples. Stage/seal includes temporary label
maps, normalization, task/thread ownership and validation; it excludes source
admission, ETA/route calculations and initial fixture-label creation. Validated
publish includes another full schema/duplicate-label check, head capture, new
state allocation and CAS; the traversal happens outside the mutex. Serialize
uses standard `generate_latest` over the 29 families plus position alias,
without unrelated instruments. Costs are separate and must not be added to
another operation that already includes them.

At 1,100 POIs there are 2,230 samples including both POI families and the
position alias. Uncontended capture median is about 0.4 microseconds. During
each 30-second run one 1-Hz writer and three 1-Hz readers completed 30
operations each, with zero mixed frames and zero surviving threads. Capture wall
p95 was 5.39 microseconds at 0.19.0 and 4.72 at 0.26.0; validated publish wall
p95 was 0.230/0.227 ms respectively. These are call latencies, not mutex
hold-time measurements or a simultaneous full-application lifecycle test.

| POIs | Reachable frame bytes (0.26) | Stage/seal allocation peak | Serialization allocation peak |
| ---- | ---------------------------: | -------------------------: | ----------------------------: |
| 0    |                        5,192 |                     16,962 |                        25,746 |
| 10   |                       11,892 |                     22,818 |                        36,240 |
| 100  |                       72,012 |                     84,962 |                       109,954 |
| 1100 |                      746,612 |                    663,442 |                       848,770 |

Reachable frame size counts shared objects once, including pre-existing label
strings. Traced peaks measure incremental allocations, so these columns have
different boundaries. Retained traced blocks/current bytes for each operation
are in JSON. At every size/version only one of 100 replaced frame weakrefs
remained live after GC. Paused-reader tests also prove an older frame survives
until its collector releases it; the store has no history. Memory therefore
scales with active readers/builders and input size, not number of publications.

The measured pointer synchronization is small relative to dense-frame work.
Preparation/collection remain real O(N) costs: these results do not establish
net service CPU savings or justify comparing the 1,100-POI host fixture to the
frozen application workload. Matched system measurement and retention soaks
remain required before claiming the optimization succeeds.

## Evidence, deviations and next gate

All 2,072 original #390 files and 128 before-change #391 files match their
retained inventories. The application SHAs, frozen harness, comparison guards,
rejected comparison and package-inventory correction remain unchanged. The
matched original/current-dev/candidate controls and minimum 60-minute acceptance
remain Task 6 requirements; this component run does not substitute for either.

Task 1 adds a shared schema fixture/helper, measurement script, complete
consumer inventory and this report beyond its three named code/test files. This
supports the requested audit and reproducible measurements without production
wiring. Thread/task identity enforcement was strengthened after review
reproduced inherited-context writes. No architecture or dependency-manifest
change.

Minor review item retained for future tests: the bound whole-family view read is
currently asserted with one label set, rather than two distinct children. Its
intentional semantics are disclosed above. Existing import-identity tests were
reused rather than duplicated. No Critical/Important review findings remain.

Raw logs, commands, review notes, benchmark JSON, baseline verification and
cleanup evidence are retained in the open worktree at
`.superpowers/sdd/2026-10-21-perf-391-metrics-publication-tasks/evidence/`. The
committed compact results and scripts permit review without that directory.

Rollback of this unwired foundation removes the Task 1 additions; there is no
durable migration or running service to reverse. Integrated rollback build/test
and separately authorized deployment remain Task 6. No new APIs are imposed on
existing callers yet; the new module's preparation/store/collector/view API is
internal and additive. Source-admission validation remains its producer's duty.

Host `/proc` verification found no task-owned runtime survivors after both
bounded benchmark runs and the suite timeout. No Compose project, Docker
network/volume, browser or persistent service was created for Task 1. Private
client/cache/test directories were removed. Evidence and the open PR worktree
are retained; no task-owned listener remains.

Stop here for the Task 1 go/no-go review. No Task 2 work has begun.
