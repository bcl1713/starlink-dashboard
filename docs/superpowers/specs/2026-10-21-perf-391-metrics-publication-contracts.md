# Gauge snapshot ownership and acceptance contract

This is a required part of the revised
[written specification](2026-10-21-perf-391-metrics-publication-design.md),
awaiting approval with the
[architecture decision](2026-10-21-perf-391-metrics-publication-decision.md). It
retains the frozen evidence and lifecycle/preflight requirements while replacing
global registry transactions with a bounded coupled-gauge snapshot.

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

## Exact ownership and consistency domains

The table exhausts the 58 existing definitions. There are 29 frame-backed Gauge
families plus the custom position alias, 18 independent standard Gauge families,
seven standard Counters, and four standard Histograms. The name/help/
label/type/unit schemas remain unchanged; the classification changes backing
state and consistency claims, not Prometheus queries.

| Family group                                                                                                                                                                                                                       | Owner and publication boundary                                                              | Time and unavailable policy                                                                                                               |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| Frame: `starlink_dish_{latitude_degrees,longitude_degrees,altitude_feet,speed_knots,heading_degrees}` and `starlink_aircraft_position` alias                                                                                       | Accepted observation; one captured gauge frame for all position forms                       | Original position/speed observation times; NaN for missing/disconnected observations                                                      |
| Frame: `starlink_network_{latency_ms_current,throughput_down_mbps_current,throughput_up_mbps_current,packet_loss_percent}`, `starlink_dish_obstruction_percent`, `starlink_signal_quality_percent`, `starlink_uptime_seconds`      | Same accepted telemetry frame; preserve individual availability and environmental semantics | No fabricated metric source; existing uptime retention stays; unavailable observed fields NaN                                             |
| Frame: `starlink_eta_poi_seconds`, `starlink_distance_to_poi_meters`                                                                                                                                                               | Accepted observation or refresh-only derivation tied to position/route/phase identity       | Preserve anticipated/estimated labels; NaN unknown values; default cruise speed is only an estimate                                       |
| Frame: `starlink_flight_phase`, `starlink_eta_mode`, `starlink_flight_{departure_time_unix,arrival_time_unix}`, `starlink_time_until_departure_seconds`                                                                            | Existing flight state or replay context, published with applicable ETA                      | Existing encodings, actual versus scheduled times, zero undetected event times                                                            |
| Frame: `starlink_route_progress_percent`, `starlink_current_waypoint_index`                                                                                                                                                        | Accepted legacy simulation/replay frame, not an early coordinator gauge write               | Same simulation frame as position; no new live progress calculation                                                                       |
| Frame: `starlink_route_{has_timing_data,total_duration_seconds,departure_time_unix,arrival_time_unix,segment_count_with_timing}`                                                                                                   | Accepted route revision and current derived frame                                           | Planned Unix times; active untimed route flag 0; missing fields NaN                                                                       |
| Frame: `starlink_service_info`, `starlink_mode_info`, `starlink_metrics_last_update_timestamp_seconds`                                                                                                                             | Source/config identity and existing successful telemetry accounting                         | Mode must agree with frame provenance; derived refresh/failure never renews telemetry last-update time                                    |
| Independent: `starlink_ground_entry_point_{latitude_degrees,longitude_degrees,location,info}`                                                                                                                                      | Existing resolver/simulation PoP producer and its own source lifecycle                      | Preserve current removal/NaN behavior; not forced to aircraft acquisition time                                                            |
| Independent: `starlink_network_{latency_ms,throughput_down_mbps,throughput_up_mbps}` and `starlink_metrics_scrape_duration_seconds`                                                                                                | Standard Histograms, existing accepted sample/producer timing paths                         | Preserve buckets, cumulative count/sum, exemplars and created series; no observe on scrape or derived refresh                             |
| Independent: `simulation_updates_total`, `simulation_errors_total`, `starlink_metrics_generation_errors_total`, `starlink_{connection_attempts_total,connection_failures_total,outage_events_total,thermal_events_total}`          | Standard Counters; existing owners and dormant behavior                                     | Monotonic event totals, original labels/created times; no retry/recovery rollback or re-observe                                           |
| Independent: `mission_active_info`, `mission_phase_state`, `mission_next_conflict_seconds`, `mission_timeline_generated_timestamp`, `mission_comm_state`, `mission_degraded_seconds`, `mission_critical_seconds`                   | Existing per-mission planning/replay/compatibility helpers                                  | Own mission ID, plan generation or replay clock; not represented as an aircraft acquisition frame; preserve current sentinels and helpers |
| Independent dormant: `starlink_device_location`, `starlink_dish_{uptime_seconds,thermal_throttle,outage_active}`, `starlink_eta_to_waypoint_seconds`, `starlink_distance_to_waypoint_meters`, `starlink_route_segment_speed_knots` | Preserve existing definitions and explicit disconnect clears; no new producer               | Do not activate dormant measurements or invent finite observations                                                                        |

Per-mission phase, communication state and next-conflict values are planned or
replay-domain measurements keyed by mission ID. They are not observations of
aircraft position/network acquisition. Existing replay owners still determine
their times and meaning. We do not add cross-domain rollback to make a single
scrape transactional over them and the aircraft frame. Tests must verify their
existing producer behavior, and explicitly avoid asserting equal generations
between these independent groups. GEP likewise retains its independent owner; no
new whole-GEP or whole-registry consistency promise is introduced by #391.

The coupled snapshot contains the same POI set returned by the existing
producer, not a new active-only filter. Deduplicate samples by existing (name,
category, eta_type) labels with the current last-write-wins behavior. Keep one
current frame, in-flight builders, and reader-owned references; retain no
generation queue. Frame size is O(current producer data), not O(scrape count).
Temporary serialization allocations are separately measured.

Only directly superseded active frame keys receive unavailable values during
route/POI/mode/mission transitions. Retain no process-lifetime series history
inside the new snapshot. This replacement behavior is limited to the families
moved to the frame and their active lifecycle. Do not sweep independent client
children, repair `mission_active_info`, prune missions, or claim general
cardinality savings; those remain #393. Record any changed series lifecycle in
the full regression/ingestion tests rather than hiding it as a performance gain.

## Lifecycle refresh and source identity

`FrameIdentity` carries mode, coordinator lifecycle identity, observation
identity/timestamps, active route revision, POI input revision, phase revision,
and replay runtime/run/revision plus simulation time where applicable. Capture
`metric_source` and per-field `metric_availability` with these inputs; mode must
reflect the accepted producer, not newly generated defaults. Its process-local
revision is invalidation metadata, not a new mission filesystem cache.
Revalidate authoritative inputs through existing admission; do not replace
cross-process source checks with this local revision.

Successful mutators mark input dirty under existing repository admission,
replace publication status with pending, and signal refresh. Notifications must
not query managers, calculate ETA, or recursively publish. For nested mission
operations, the signal can occur early, but the refresh captures only after
repository admission is released. A rolled-back operation refreshes the restored
state; it never publishes intermediate route/POI combinations.

| Event                                                                                                                                        | Notification site and required refresh                                                                                                                                                          |
| -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Startup, including disabled background mode                                                                                                  | After managers/state are ready, publish actual existing initial telemetry or a complete unavailable frame plus route/phase state; never call coordinator `update()` to serve a scrape           |
| New accepted live or legacy simulation observation                                                                                           | Existing background tick prepares one full frame and existing observation accounting                                                                                                            |
| Replay start/step/completion                                                                                                                 | Prepare during the existing replay callback, swap the gauge frame only after successful `commit_tick`; source UTC and mission time remain separate                                              |
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
FrameStore locks inside that guard. Derived-only refresh skips speed-history
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

## Regression matrix and stop go checkpoint

| Area                    | Required proof before release                                                                                                                                                                     |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Scrape purity           | 100 sequential/concurrent scrapes: zero simulator/ETA construction, manager access, calculation, storage writes, clock/source advancement or detector changes                                     |
| Snapshot atomicity      | Reader paused between position and ETA; old frame retained across a pointer swap and dynamic-label changes; only complete old/new tuples succeed, without retries                                 |
| Compatibility           | All 29 actual gauge schemas plus position alias, helper/import identities, positional/keyword labels, read views, staged writes, custom registries and test reset; no hidden raw Gauge dependency |
| Independent instruments | Real Counter/Histogram types and unchanged created/buckets/count/sum/exemplars/labels; frame abort does not roll them back; no observe on refresh/retry                                           |
| Failure                 | Builder failure at any staged field, abandoned label binding, source invalidation/CAS loss and failure masking; no partial or falsely fresh frame; recovery from existing owner                   |
| Read isolation          | Registered coupled collector has no callback inputs; detached values/labels survive later publications; independent callback collectors are explicitly read-only and outside the frame            |
| Source identity         | Fixed live observation versus different simulator defaults; derived refresh preserves acquisition and successful-observation timestamp; stale prepared source rejected                            |
| Replay                  | Scrapes/dirty wakes do not advance frame/run/clock; no snapshot publication before successful runtime commit; existing error handling remains, no new replay checkpoint machinery                 |
| Lifecycle               | Every trigger below, timing-only corrections, external reload with no telemetry, config/mission races, unchanged source, source expiry and no route/POIs/mission                                  |
| Disabled background     | Complete startup frame; at most one event-driven one-shot refresh; explicit reload for unannounced file edits; shutdown drains work and detaches callbacks                                        |
| Preflight               | Timed/untimed, future/past departure, zero/unavailable speed, usable/missing position, waypoint match and fallback labels; no invented observed position/speed                                    |
| HTTP and health         | Existing format, EOF, safe fallback and position table; truthful NaN and degraded publication diagnostics; no contention-driven 503; genuine serializer failure explicit                          |
| Operations              | Real 1-Hz ingestion and qualified history, Overview/Operator, mission switch/cancel, restart/export, no confidence acknowledgments or display changes                                             |

Before editing production replay/lifecycle paths, stop after isolated schema,
compatibility and concurrency tests. Proceed only if the selected mechanism has
one numeric authority, no private client access, no mixed coupled frames,
bounded state and acceptable component cost. Any raw-Gauge compatibility
blocker, mission-domain consistency dependency, or erased CPU benefit returns
the design to review; it does not authorize a proxy expansion or journal
implementation.

## Performance gate and rollback

The [decision record](2026-10-21-perf-391-metrics-publication-decision.md)
contains small-probe results, including allocation and retained-frame
measurements. Those results are not application savings, a live-source test, or
sustained acceptance. Use the unchanged #390 methodology and the plan's
frozen-runner commands for three matched original/current-dev/candidate warmed
controls, separate off and counter runs, distributions, sample coverage and host
variability. Keep rejected comparisons and original evidence intact. Add no
always-on production probe.

Measure total service/exporter CPU and per-scrape allocation/latency, frame
preparation/publication cost, independent histogram/counter behavior, source
freshness, event-loop delay, memory/storage slopes and actual 1-Hz ingestion.
Require zero scrape-triggered domain work, no material
operational/tail/freshness regression, and net CPU improvement beyond
repeated-control variability. If the frame/view compatibility layer erases the
benefit, stop for review rather than claiming victory from constructor counts or
adopting a byte cache silently.

Run original and candidate soaks with at least 3,600 measured seconds, using
120-second warm-up and 3,660-second requested duration for sampling margin. Keep
steady and activity cases separate. Synthetic simulation does not qualify
physical GPU, real dish acquisition, live archive durability, or the final
eight-hour integration gate in #390. Preserve those limitations and remaining
regression/operational gates.

Rollback is a reviewed revert of #391 application commits, built/tested as a
separate candidate. There is no durable migration, dependency pin or production
configuration change. Reverting restores the known scrape-time synthetic hazard;
disclose that tradeoff. Retain all source mission/Operator/archive data, probe
results and frozen baseline evidence. Deployment, merge and issue closure still
require separate authorization.
