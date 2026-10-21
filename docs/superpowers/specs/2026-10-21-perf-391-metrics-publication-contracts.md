# Metrics publication ownership and acceptance

This is a required part of the proposed
[written specification](2026-10-21-perf-391-metrics-publication-design.md),
awaiting separate approval. It defines the complete ownership/lifecycle
contract, retained baseline, regression matrix, measurement gates, and rollback.

## Evidence and comparison identity

- Frozen original application: `25e34168f0e2cecb149b0323f1f5a795cb28cae0`.
- Investigation base and current `origin/dev` when branched:
  `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` (PR #402).
- Matched measurement harness: `13cbf1d54b526307747578ecd4fc691562846834`.
- Worktree: `.worktrees/perf-391-readonly-metrics`, branch
  `perf/391-readonly-metrics`; the primary checkout stays on `dev`.
- Original evidence and methodology remain unchanged. See
  [baseline](../../performance/perf-390-baseline.md) and
  [comparison contract](../../performance/perf-390-methodology.md).

Retained investigation evidence is outside Git at
`/home/oracle-worker/Work/starlink-dashboard/.superpowers/sdd/2026-10-20-perf391/evidence`.
It contains `source-audit.json`, `characterization.json`, both before-change
runs, accepted comparisons, rejected-comparison details, focused-test output,
application-user packages, cleanup verification, and `sha256.json`. Do not
overwrite these files or the original #390 inventory.

The controlled 100-scrape characterization in live configuration constructed 100
simulators, generated 100 frames, and constructed 100 ETA calculators. POI
distance changed from 157,249 m to 8,692,186 m while published position and
network gauges remained unchanged. This proves the mixed-source path in a
controlled fixture, not observed corruption of production missions.

Matched warmed controls use two Overview viewers plus Operator, a 1,800-second
history window, 120 seconds of warm-up, and 180 measured seconds. Hardware is
i9-10900K, 20 logical CPUs; services have two-CPU/2-GiB limits. The browser is
headless Chromium with SwiftShader at 1920 by 1080 and DPR 1. The workload is
synthetic simulation with real 1-second Prometheus scraping and evaluation.

| Measurement                              |        Frozen original | Unchanged investigation base |
| ---------------------------------------- | ---------------------: | ---------------------------: |
| Backend cores, instrumentation off       |                 0.2268 |                       0.2298 |
| Prometheus cores, instrumentation off    |                 0.0190 |                       0.0206 |
| History p95 ms, instrumentation off      |                  362.6 |                        362.2 |
| Preparation CPU p50/p95/p99 ms, counters |     5.07 / 5.90 / 7.01 |           5.02 / 5.88 / 8.06 |
| Metrics ASGI p50/p95/p99 ms, counters    | 7.44 / 106.65 / 255.64 |       7.14 / 108.16 / 194.30 |

Off and counter comparisons passed the unchanged current report tool against
their applicable frozen cases. Comparison against original counter run 1 was
rejected because sparse storage-probe spans differed by more than 10 seconds;
counter run 2 passed. Keep that rejection. No savings are claimed. The corrected
application-user inventory matches the original: 89 packages, SHA-256
`f4cf11f533ade1605b73e5e3a18e460d7151bb2ae2a7257c6389b0a5458f13ba`.

## Metric ownership and publication boundaries

The following groups exhaust all 58 definitions; the custom position family is
included in the first row. Existing dormant definitions remain dormant.

| Families                                                                                                                                                                                                                                                                                                                 | Authoritative producer and event                                            | Time and cleared state                                                                                                                                      |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `starlink_dish_{latitude_degrees,longitude_degrees,altitude_feet,speed_knots,heading_degrees}`; `starlink_aircraft_position`                                                                                                                                                                                             | Accepted telemetry frame; never the scraper                                 | Original position/speed observation times; NaN on disconnect or unavailable frame                                                                           |
| `starlink_network_{latency_ms_current,throughput_down_mbps_current,throughput_up_mbps_current,packet_loss_percent}`; `starlink_dish_obstruction_percent`; histograms `starlink_network_{latency_ms,throughput_down_mbps,throughput_up_mbps}`                                                                             | Accepted telemetry, with existing field availability and mode/status labels | Source observation; unavailable gauges NaN, no unavailable histogram observation                                                                            |
| `starlink_signal_quality_percent`, `starlink_uptime_seconds`                                                                                                                                                                                                                                                             | Existing telemetry/environmental producer                                   | Preserve current semantics; signal clears on disconnect, existing uptime retention stays                                                                    |
| `starlink_ground_entry_point_{latitude_degrees,longitude_degrees,location,info}`                                                                                                                                                                                                                                         | Existing resolver or simulation PoP producer; one atomic four-family group  | Existing source time/identity; preserve existing NaN and previous-identity removal behavior                                                                 |
| `starlink_eta_poi_seconds`, `starlink_distance_to_poi_meters`                                                                                                                                                                                                                                                            | Same full frame as its position/route/phase, or controlled derived refresh  | Bind to accepted observation and input revision; current affected values NaN when uncomputable                                                              |
| `starlink_flight_phase`, `starlink_eta_mode`, `starlink_flight_{departure_time_unix,arrival_time_unix}`, `starlink_time_until_departure_seconds`                                                                                                                                                                         | Existing FlightStateManager or replay state, included in full frame         | Existing actual/planned/replay distinction; retain phase encodings and zero undetected event times                                                          |
| `starlink_route_progress_percent`, `starlink_current_waypoint_index`                                                                                                                                                                                                                                                     | Simulation frame publisher; remove coordinator's early gauge writes         | Same frame as position; no new live progress algorithm                                                                                                      |
| `starlink_route_{has_timing_data,total_duration_seconds,departure_time_unix,arrival_time_unix,segment_count_with_timing}`                                                                                                                                                                                                | Route-state preparation, committed with current derived frame               | Accepted route revision, planned Unix times; flag 0 for active untimed route, unavailable fields NaN                                                        |
| `starlink_service_info`, `starlink_mode_info`                                                                                                                                                                                                                                                                            | Startup and accepted configuration lifecycle                                | Existing version/mode schema; mode changes invalidate old-source frame before refresh                                                                       |
| `starlink_metrics_{scrape_duration_seconds,generation_errors_total,last_update_timestamp_seconds}`                                                                                                                                                                                                                       | Producer completion/error accounting                                        | Preserve current meanings: duration is existing producer timing; last update is successful telemetry publication, not acquisition or a derived-only refresh |
| `simulation_updates_total`, `simulation_errors_total`                                                                                                                                                                                                                                                                    | Existing accepted-update/error paths, including historical live behavior    | Monotonic; derived refresh and scrape add no updates or observations                                                                                        |
| `mission_phase_state`, `mission_comm_state`, `mission_next_conflict_seconds`                                                                                                                                                                                                                                             | Existing replay frame; explicit compatibility functions remain available    | Replay mission clock or supplied mission context; preserve existing encodings/sentinels                                                                     |
| `mission_active_info`, `mission_timeline_generated_timestamp`, `mission_degraded_seconds`, `mission_critical_seconds`                                                                                                                                                                                                    | Existing compatibility helpers; no new production callers                   | Caller-supplied mission/timeline times; preserve helper behavior, including deferred #393 bug                                                               |
| `starlink_device_location`; `starlink_dish_{uptime_seconds,thermal_throttle,outage_active}`; `starlink_{connection_attempts_total,connection_failures_total,outage_events_total,thermal_events_total}`; `starlink_eta_to_waypoint_seconds`, `starlink_distance_to_waypoint_meters`, `starlink_route_segment_speed_knots` | No new producer; compatibility definitions retained                         | Do not fabricate observations or activate dormant counters; preserve existing disconnect clears                                                             |

A full frame includes position, current network/availability, phase/mode,
applicable simulation progress, route timing, POI values, and replay-owned
mission values. Histograms and accepted-update accounting join only when a new
observation is admitted. GEP and explicit compatibility/service operations may
use smaller transactions, but cannot clear a full-frame failure or satisfy a
pending full-frame input revision. The health last-scrape-attempt timestamp is
an intentional non-registry request-side update, unchanged by this issue.

Track only the current frame's label keys and input identity as lifecycle
metadata, not duplicate numeric metric values. The argument-free
`clear_telemetry_metrics()` compatibility function invalidates coupled observed
POI values as well as telemetry. Without full current inputs it cannot satisfy a
pending input revision or clear a full-frame fault; the owning refresh must
complete that work. Planned route timing is not cleared merely by disconnect.

## Lifecycle refresh and source identity

`MetricInputIdentity` carries mode, coordinator lifecycle identity, observation
identity/timestamps, active route revision, POI input revision, phase revision,
and replay runtime/run/revision plus simulation time where applicable. Its
process-local revision is invalidation metadata, not a new mission filesystem
cache. Revalidate authoritative inputs through existing admission; do not
replace cross-process source checks with this local revision.

Successful mutators mark input dirty under existing repository admission,
increment the local revision, and signal refresh. Notifications must not query
managers, calculate ETA, or recursively publish. For nested mission operations,
the signal can occur early, but the refresh captures only after repository
admission is released. A rolled-back operation refreshes the restored state; it
never publishes intermediate route/POI combinations.

| Event                                                                                                                                        | Notification site and required refresh                                                                                                                                                          |
| -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Startup, including disabled background mode                                                                                                  | After managers/state are ready, publish actual existing initial telemetry or a complete unavailable frame plus route/phase state; never call coordinator `update()` to serve a scrape           |
| New accepted live or legacy simulation observation                                                                                           | Existing background tick prepares one full frame and existing observation accounting                                                                                                            |
| Replay start/step/completion                                                                                                                 | `activate_leg_transaction` and `SimulationRunService.collect` join metric transaction with `commit_tick`; source UTC and mission time remain separate                                           |
| Route activation/deactivation, active reload/replacement/removal, reload-all, failed parsing of the active route                             | `RouteManager` mutation boundaries notify; refresh timing, phase, applicable progress, and POI metrics even without telemetry                                                                   |
| POI create/update/delete, scoped/bulk deletes, projection changes, restore/reload                                                            | `POIManager` accepted in-memory/persisted publication boundaries notify, including detected external file reload; coalesce bulk changes                                                         |
| Manual/automatic phase or mode transition, departure/arrival correction, reset, route-context update/clear, replay state application/restore | `FlightStateManager` accepted changes notify, including timing-only changes that do not invoke phase callbacks                                                                                  |
| Accepted POST/PUT config replacement and coordinator reset                                                                                   | Notify within existing config admission; invalidate previous coordinator/mode identity; refresh from the resulting source without an extra source update                                        |
| Mission/leg switch, planning commit or rollback, replay cancel/failure                                                                       | Existing route/POI/flight notifications plus explicit end-of-transaction notification in leg activation and replay service; no new mission enumeration                                          |
| Telemetry unavailable, unchanged, or disconnected                                                                                            | Every existing background deadline still checks current route/POI/state and source expiry; publish NaN/derived/planned values as appropriate rather than returning early on `telemetry is None` |
| Wall-clock preflight countdown or source freshness expiry                                                                                    | Existing background deadline only; unchanged acquisition identity is not a new observation                                                                                                      |
| Shutdown                                                                                                                                     | Stop notification admission, drain owned refresh work, then close managers; no callbacks survive lifespan                                                                                       |

When background updates are enabled, the existing loop waits for either its
normal collection deadline or the dirty event. A dirty wake performs a
**refresh-only** job and leaves the original collection deadline unchanged; it
does not call live collection or advance simulation. If a normal tick already
incorporates the dirty revision, no duplicate refresh is needed.

When background updates are disabled, a notification schedules at most one
owned, coalesced, one-shot refresh task on the lifespan event loop. It has no
timer and exits after draining dirty revisions. Keep one task handle and drain
it at shutdown. Never spawn one task per POI. Unannounced external edits in this
test mode need an explicit manager reload/refresh; no filesystem work is moved
into scraping to discover them. In production, the existing periodic producer
checks remain active even when observations stop.

Serialize access to the metrics ETA singleton's mutable speed/passed-POI state
with a dedicated computation guard that no scraper or API reader acquires.
Capture manager inputs before acquiring it; do not acquire repository or
publication locks inside that guard. Derived-only refresh skips speed-history
append, passed-POI tracking, event detection, archive writes, histogram observe,
and accepted-update counters. It calculates against detached existing smoothing
state. Only the accepted-observation path changes that state. Extend the
internal ETA service interface to distinguish these two operations explicitly.

Live acquisition UTC, legacy simulation observation UTC, paced replay mission
time, scheduled route UTC, and service publication time are distinct fields.
Derived refresh does not mutate any telemetry timestamps, replay runtime
revision/frame, or the successful-telemetry last-update gauge. An accepted
coordinator observation can retain existing semantics even if values are equal;
copying the same observation for a lifecycle refresh cannot count it again.

Preserve anticipated route ETA semantics, including the current planned-duration
fallback after scheduled departure, and the existing 150-knot fallback for
preflight ETA with a usable position. That assumed speed never becomes an
observed speed. If there is no usable position, distance is NaN; publish a
planned anticipated ETA only when existing waypoint/projection timing can
determine it without fabricated coordinates. Otherwise ETA is NaN. In-flight
unavailable position/speed must not become a fictional live ETA or an implicit
switch to planned timing. Preserve existing Unix timing values under the
baseline timezone; broader timestamp-conversion correction is a separate issue.

## Regression and acceptance matrix

| Area                   | Deterministic proof                                                                                                                                                                                                  |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Read-only scraping     | 100 sequential and concurrent scrapes instantiate zero simulators/calculators, perform zero route/POI calculation/access, and make zero storage writes                                                               |
| Generation consistency | Pause writer after position but before ETA; pause reader between families; only complete old/new tuples may succeed; overlap is retried or explicitly fails                                                          |
| Lock boundary          | Assert calculation, file access, collection, serialization, waits, and replay finalization execute without publication mutex held                                                                                    |
| Rollback               | Inject failure after each operation class and replay finalization; restore gauges, position, histogram sum/buckets/exemplars, counters, created timestamps, and new-child membership; failed restoration quarantines |
| Lifecycle concurrency  | Config replacement, route reload, mission activation/rollback, POI bulk edit, and telemetry preparation barriers reject superseded input identity; no deadlock                                                       |
| Source provenance      | Fixed live observation differing from simulator defaults cannot change on scrape; derived refresh retains original acquisition and last-update times                                                                 |
| Simulation and replay  | Repeated/concurrent scrapes and dirty refresh do not advance source frame, run revision, mission clock, speed smoothing, detector dwell, or archive events                                                           |
| Replay failure         | Failure before/after runtime finalization restores its checkpoint or enters existing failed-run lifecycle with metrics unavailable; no successful scrape of an uncommitted frame                                     |
| Preflight              | Timed/untimed routes, future/past departure, zero speed, unavailable speed, usable/missing position, matching/nonmatching waypoint, anticipated labels and default-speed fallback                                    |
| Missing source         | Startup/live disconnect/recovery, missing metrics, stale speed, no route/POIs/mission, unchanged observation, source expiry; planned state still refreshes                                                           |
| Disabled background    | Startup plus CRUD/config/phase events refresh through a single owned one-shot task; explicit reload observes external edits; scraping never becomes the producer                                                     |
| Prometheus contracts   | Dedicated/custom registries, PositionCollector dimensions, all existing family schemas, buckets, monotonic totals, created series, NaN, single EOF, content type, safe fallback and health                           |
| Resource ownership     | At most one coalesced refresh task; cancellation drains tasks/workers; detached callbacks cannot recreate work after shutdown                                                                                        |
| Operational acceptance | Real 1-Hz ingestion and qualified history; Overview/Operator reads and transitions, normal exports/restart; no input acknowledgments or display changes                                                              |

## Performance acceptance and rollback

Use the frozen per-case harness, current strict report tool, private projects,
and append-only evidence exactly as described in #390. First run the transaction
component benchmark with 0, 10, 100, and 1,100 POIs: capture attempts, writer
reservation duration, actual mutex hold time, undo bytes, allocations and CPU.
Compare a raw client collection diagnostic separately; the release comparison is
complete original versus candidate request and service cost. Instrumentation for
mutex/reservation/retry diagnostics stays outside production endpoints and uses
bounded buffers. Profile allocations separately from primary timings.

Run three matched original and candidate warmed controls with instrumentation
off, then matched counter runs. Preserve comparisons to frozen original and
immediately preceding dev separately. Record distributions, sample coverage,
hardware/build identity, source grids, failures, memory and storage slopes.
Require zero on-scrape simulator/ETA work, no contention 503s under ordinary
1-Hz steady state, no material tail/freshness/interaction regression, and a
repeatable net reduction in exporter/service CPU beyond control variability. If
journaling/retries erase the savings, do not ship based on object counts: return
to design review with the measured result. No numeric savings target or new
lock-duration SLO is invented before measurements.

Run at least 3,600 measured seconds of original and candidate soak per
applicable major workload. Use 120-second warm-up and 3,660-second requested
duration to leave sampling-span margin. Cover real Prometheus, ordinary
Overview, Operator, and mission lifecycle transitions; the plan gives separate
steady/activity commands. Accepted-live fixture checks, restart/export, and
physical GPU evidence remain separately labeled; synthetic simulation cannot
qualify them. Final integrated eight-hour acceptance stays in #390.

Rollback is a reviewed revert of the #391 implementation commits, built and
tested as its own candidate. There is no durable data migration or dependency
change to undo. Reverting restores the known scrape-time synthetic overwrite
hazard; document that tradeoff rather than calling it a correctness fix. If the
only defect is publication failure, prefer leaving failed scrapes explicit until
a tested fix is reviewed. Preserve all mission/Operator/archive evidence and
original benchmark artifacts. Rollback deployment needs separate approval.
