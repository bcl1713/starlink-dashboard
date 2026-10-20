# Original performance baseline: #390 kickoff

This is the frozen pre-optimization reference for epic #389. No production
behavior changed. Issue #390 remains open until integrated eight-hour acceptance
and its final report; these short runs do not establish long-term stability.

## Identity and conditions

- Original application: `25e34168f0e2cecb149b0323f1f5a795cb28cae0`.
- Measurement harness: `02cdf20a219fa3aca7beebbd53619cfe7e3b2de8`,
  `13cbf1d54b526307747578ecd4fc691562846834`,
  `dedf68a1a07ec5e6b09aa68fa413b7b4c5e9cbdb`; each case pins its measurement
  revision for comparisons.
- CPU: Intel Core i9-10900K, 20 logical CPUs; 65,915,523,072 bytes host RAM.
- Ubuntu 26.04.1 LTS, kernel 7.0.0-34-generic, Docker 29.8.1/overlayfs; evidence
  filesystem reports `ext2/ext3`, 4,096-byte blocks.
- Each backend, Prometheus and Nginx service: two CPU equivalents, 2 GiB RAM.
  Quotas are not reservations; browser/observer share the host CPU allocation.
- Production backend/frontend Dockerfiles and production Nginx proxy, real
  Prometheus v3.5.0, localhost published-port networking. Exact image IDs,
  dependency hashes, fixture hashes and backend/browser versions are in the
  [index and summaries](baseline-2026-10-20/index.json).
- Browser: Chromium 153.0.8010.12, Node v22.12.0, 1920×1080, DPR 1, **headless
  SwiftShader software rendering**. Physical fullscreen and hardware-GPU
  acceptance were not available in this lane. Independent contexts share a
  browser GPU process, unlike separate physical displays.

The original package inventory ran as root and did not describe application
dependencies. The
[runtime correction](baseline-2026-10-20/runtime-package-correction.json)
retains that limitation and supplies the verified `appuser` inventory (89
packages). All 17 backend images have identical filesystem layers and
configuration, matching the archived diagnostic runtime; differing OCI
attestation IDs do not imply different application packages. Future comparisons
must verify the application-user inventory rather than rely on the legacy hash.

`origin/dev` advanced to `9ccc54e1` during collection through
release-documentation PR #400; its application sources match the original
commit. The application SHA above stayed fixed for every reference run.

## Workload and measurement

See the [reproduction contract](perf-390-methodology.md). Every case starts with
fresh private data: two fictional missions with two legs each, six Operator
records, a timed five-point ocean route, and 4,201 seconds of dense synthetic
history across 11 metrics. Optional overlays stay at their default off settings.
Prometheus scrape/evaluation and the browser's configured history delay are each
one second; actual browser request-start spacing is measured separately.

The startup/preparation cases discard 30 seconds and measure 120 seconds.
Existing customer-slide preparation can continue into those windows. Their CPU
and memory include that real background work, so they are not quiescent
steady-state results. The separate warmed cases discard 120 seconds and measure
180 seconds. The transition control uses 10 seconds plus 45 measured seconds,
switches legs, deactivates/reactivates the mission and saves three actual
journal records.

Network latency uses Playwright's browser `responseEnd` offset, independent of
observer callback delivery. Disk probes run asynchronously. Earlier
callback-based runs are retained separately as superseded diagnostics and are
not reference latency evidence. No application speedup is claimed between
measurement revisions.

All accepted cases recorded 11 series with expected non-null point counts at the
beginning and end (one-second output through 30 minutes; two seconds at 60
minutes). The v2 cohort did not independently enforce finite values or timestamp
spacing; v3 added finite-point checks, with exact shared timestamp
bounds/spacing enforced from `13cbf1d5`. The case index records validation
coverage. Accepted cases also had sustained successful browser polling, zero
unexpected request failures and verified teardown. These checks establish
synthetic history coverage, not physical source-acquisition freshness or
accepted live archive truth.

## Original measured values

CPU is average consumed cores, not percent of an unspecified machine. History is
browser network p50/p95/p99; status is the observer's HTTP read plus JSON parse.
Quantiles are nearest rank with counts. Each row is its own workload.

[Full CPU and latency tables](baseline-2026-10-20/measurements.md#cpu-and-service-latency)
retain every case and sample count.

[Memory tables](baseline-2026-10-20/measurements.md#memory-and-measured-slopes)
separate backend, Prometheus, browser PSS and JS heap, with measured spans and
slopes.

[Storage tables](baseline-2026-10-20/measurements.md#persistent-storage-and-measured-slopes)
separate SQLite, application files and Prometheus TSDB components.

Repeated startup/preparation controls (three original runs each; same windowed
workload and harness):

| Controls                                          | Metric         | Min     | Median  | Max     |
| ------------------------------------------------- | -------------- | ------- | ------- | ------- |
| one-r1, one-r2, one-r3                            | Backend cores  | 0.472   | 0.476   | 0.480   |
| one-r1, one-r2, one-r3                            | History p95 ms | 254.584 | 265.668 | 285.753 |
| two-operator-r1, two-operator-r2, two-operator-r3 | Backend cores  | 0.547   | 0.558   | 0.560   |
| two-operator-r1, two-operator-r2, two-operator-r3 | History p95 ms | 359.306 | 374.017 | 386.956 |

These ranges measure run-to-run variability, not uncertainty bounds or
application gains.

## Attribution and instrumentation limits

The separate real-Prometheus replay passed: one 1,800-second cold fetch took
106.1 ms with 16 queries and 46,826 planned evaluation points. Thirty
incremental updates had p50/p95/p99 28.9/36.7/44.3 ms, 480 queries and 9,360
planned points; all query spans were 11 seconds. Duplicate/concurrent reuse
added zero queries, and upstream active work ended at zero. JSON serialization
alone measured 25.1/26.3/31.0 ms. This historical replay runs as fast as
possible against real Prometheus; it is neither an HTTP/browser latency result
nor a wall-clock soak.

A separately profiled warmed `SlideCoordinator.reconcile_all` call used about
75.1 ms of **thread CPU**, including 47.7 ms in renderer-revision discovery and
26.4 ms in leg reconciliation. Directory walking, path sorting and SQLite work
appear in that call. Source inspection shows recurring reconciliation in the
coordinator loop. One call is a first-order diagnostic lead, not a complete
service CPU attribution or evidence of an optimization benefit.

Post-measurement one-call wall profiles showed `_prepare_metrics` at 12.4 ms
(including 6.3 ms exposition and 2.8 ms coordinator construction) and a
background tick at 4.3 ms (including admission/repository gates and metric
updates). These profiles include profiler/scheduling effects; they are not
normal latency percentiles or exclusive request CPU. The repeated counter
distributions below provide the less intrusive tick/preparation thread-CPU
measurements. The warmed fullscreen one-viewer process records attribute
approximately **9.576 cores to Chromium's GPU process**, 0.146 to its renderer,
0.009 to network and 0.005 to the browser process over the measured window. This
is SwiftShader CPU rendering, not hardware GPU utilization. Frame callbacks were
p50 100.0 ms, p95 116.7 ms and p99 149.9 ms (1,785 intervals). These callbacks
are descriptive; they do not measure physical display refresh or prove a product
regression.

Warmed fullscreen browser PSS ended at about 1,175 MiB with a positive
short-window OLS slope, while JS heap ended lower than its first measured
sample. Keep process ownership and longer warm traces before diagnosing a leak.
The real startup/preparation controls also include existing slide-cache
generation for four saved legs. Their higher backend CPU/memory cannot be
compared as an optimization delta with the later warmed cases.

| Matched warmed windowed workload | Backend cores | Prom cores | History p50 / p95 / p99 ms (n) | Max sampler wall ms |
| -------------------------------- | ------------- | ---------- | ------------------------------ | ------------------- |
| warm-two-operator                | 0.227         | 0.019      | 230.5 / 362.6 / 394.8 (240)    | 863.1               |
| counters-warm-two-r1             | 0.247         | 0.020      | 217.2 / 342.5 / 385.4 (242)    | 1006.3              |
| counters-warm-two-r2             | 0.246         | 0.020      | 219.9 / 355.4 / 392.2 (245)    | 816.4               |

Counters-minus-off backend differences: counters-warm-two-r1: +0.020 cores
(+8.8%), counters-warm-two-r2: +0.019 cores (+8.3%). The counter CPU overhead is
material for attribution; primary timings remain off. These serial controls
include host/run variability; do not subtract them as an exact instrumentation
correction. Five-second sampling and 30-second file probes remain present even
in off controls. Sampler wall time includes waiting, not just observer CPU.

Counter timings are p50/p95/p99 milliseconds, with sample counts:

| Case                 | Timing                         | p50 / p95 / p99 ms (n)    |
| -------------------- | ------------------------------ | ------------------------- |
| counters-warm-two-r1 | Tick wall                      | 3.0 / 37.1 / 143.2 (177)  |
| counters-warm-two-r1 | Tick thread CPU                | 2.9 / 3.8 / 4.4 (177)     |
| counters-warm-two-r1 | Metrics preparation wall       | 5.2 / 34.6 / 59.9 (181)   |
| counters-warm-two-r1 | Metrics preparation thread CPU | 5.1 / 5.8 / 8.3 (181)     |
| counters-warm-two-r1 | Metrics ASGI wall              | 31.7 / 64.3 / 208.8 (181) |
| counters-warm-two-r1 | Event-loop delay               | 0.4 / 74.6 / 104.8 (179)  |
| counters-warm-two-r1 | Operator observer HTTP + parse | 8.9 / 248.2 / 289.5 (37)  |
| counters-warm-two-r2 | Tick wall                      | 2.9 / 23.8 / 64.8 (176)   |
| counters-warm-two-r2 | Tick thread CPU                | 2.9 / 3.6 / 4.3 (176)     |
| counters-warm-two-r2 | Metrics preparation wall       | 5.2 / 25.7 / 59.2 (180)   |
| counters-warm-two-r2 | Metrics preparation thread CPU | 5.1 / 5.9 / 7.0 (180)     |
| counters-warm-two-r2 | Metrics ASGI wall              | 7.4 / 106.6 / 255.6 (180) |
| counters-warm-two-r2 | Event-loop delay               | 0.4 / 75.8 / 134.4 (179)  |
| counters-warm-two-r2 | Operator observer HTTP + parse | 9.8 / 46.2 / 156.1 (37)   |

Cgroup memory includes service children and page cache; it is not Python RSS.
Browser PSS, RSS and JS heap are distinct. Positive short-window slopes and
summed RSS do not establish a leak. Persistent size measurements include logical
and allocated bytes; the `data` category includes mission and Operator
subdirectories and must not be summed with them. Missing rootless block-I/O
counters are unavailable, not zero writes. SQLite WAL snapshots can miss
short-lived WAL files; SQL trace counts are statements/explicit transactions,
not rows, fsyncs or automatic checkpoints.

Prometheus query counts/spans are from the real client transport. Planned
evaluation points are not actual samples scanned by Prometheus. Profiled replays
and one-call profiles are diagnostic attribution, excluded from normal latency
distributions. Counter attribution uses the delta between first and last
measured snapshots; process-start totals are not reported as measured activity.
SQLite work belongs to the backend process, so its exclusive CPU and RAM are
unavailable here.

| Counter case         | Measured s | SQLite opens/s | Statements/s | Explicit commits/s | Range queries/s | Planned points/s |
| -------------------- | ---------- | -------------- | ------------ | ------------------ | --------------- | ---------------- |
| counters-warm-two-r1 | 180.0      | 22.60          | 42.89        | 8.58               | 13.96           | 533.87           |
| counters-warm-two-r2 | 180.0      | 22.70          | 43.09        | 8.63               | 13.51           | 525.78           |

The recorded incremental range spans are predominantly short trailing windows.
The initial full-window fetch remains in raw counters but outside these measured
deltas. SQLite trace counts include recurring application maintenance and reads;
they are not journal row counts or evidence of accepted-live archive batching.

Nginx CPU, SQLite-exclusive CPU/RAM, actual Prometheus samples scanned, physical
acquisition age and automatic SQLite checkpoint rates remain attribution gaps.

## Provisional budgets and remaining gates

These are comparison rules, not validated production SLOs:

| Subsystem          | Reference and proposed gate                                                                                                                                                    | Qualification still needed                                                                                                               |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Backend            | Preserve same-workload core use and warmed memory envelope; investigate deltas beyond repeated-original variability. Keep status p95 responsive; proposed history p95 <500 ms. | Repeat warmed controls and run each changed hot path for at least 60 measured minutes; live tick attribution remains open.               |
| Prometheus         | Preserve qualified grid/source contracts and series lifecycle; compare CPU, query spans/points and TSDB growth with the original.                                              | Actual scanned samples and long retention/compaction cycles are not measured here.                                                       |
| Browser            | Compare app mode, renderer, page ownership, PSS/heap slopes, frame p95 and interactions separately.                                                                            | Software-rendered ~10 Hz frame callbacks cannot set a physical-display FPS budget; hardware-GPU acceptance remains open.                 |
| SQLite             | Preserve journal/archive semantics and durability; compare statements/transactions, DB/WAL bytes and latency under the same activity.                                          | This simulation is not an accepted-live archive-write control; rows/checkpoints/fsync and exclusive CPU/RAM are unmeasured.              |
| Persistent storage | Compare logical/allocated bytes and category slopes without summing overlapping directories; preserve mission/Operator evidence.                                               | Short flat simulation data is not a retention budget. Run export/restart and long-lived evidence workloads before claiming disk savings. |

Service limits of two CPU equivalents and 2 GiB are experimental configuration,
not operational budgets. Do not set a savings target from one favorable run,
trade CPU savings for missing samples, or interpret low snapshot WAL size as
proof of lower write amplification. Record regressions and unavailable metrics.

The simulation matrix does not qualify accepted live telemetry/archive writes,
Starshield status transitions, overlay-on workloads, hidden/resume, restart or
export under load. Use the existing acceptance journeys and add matched original
controls before claiming improvements in those paths. Retain mission/Operator
semantics, one-second qualified history and source timestamps in every change.

Every major optimization still needs a matched minimum 60-minute soak. Final
integration targets eight measured hours on representative display hardware,
including the remaining workload matrix. No continuous 60-minute or eight-hour
soak is claimed by this kickoff.

## Evidence, validation and cleanup

Compact summaries, raw-file SHA-256 inventory and representative captures are in
[the baseline directory](baseline-2026-10-20/index.json). The
[final archival inventory](baseline-2026-10-20/final-archive-sha256.json) also
covers the measurement Git bundle, original image archive, metadata correction,
negative controls and final host/check evidence. Raw logs, samples, profiles,
commands and retained original image binaries remain outside Git at:

`/home/oracle-worker/Work/starlink-dashboard/.superpowers/sdd/2026-10-20-perf390-baseline/evidence`

Original evidence is never replaced with preceding-PR-only measurements. Add new
controls and comparisons; preserve all existing references. The
[epic rollup](perf-389-rollup.md) keeps gains/losses separated by change and
workload.

Focused verification: **109 tests and six subtests passed**, plus 12 static
contract tests. Black, Ruff, Node syntax checks, Markdown style and filename
checks passed. Internal docs files/anchors passed; 12 external link availability
errors were nonblocking. The broader tools attempt was interrupted after 414
passes and three failures. A focused rerun with the correct inherited Python
path passed the parent-death cleanup test; two pre-existing Dockerfile contract
tests still fail. Their Dockerfiles and test sources match the original
application commit. They expect older COPY paths and prohibit the existing
revision label. This kickoff changes none of those files and does not claim a
green full repository suite.

A separate metadata control passed against the collector correction, verifying
the application-user package hash and the same original filesystem/config hash.
The initial diagnostic attempt failed due to root's Python environment and
cleaned up; the corrected application-user replay passed. Both are retained.

Each run removes its private containers, networks, volumes, image tags, source
archive, source directory and listeners. Chromium PID/group identity is checked
on the host after Node exits. A separate SIGTERM negative control also recorded
complete teardown. Final host inventory is retained with the evidence. The open
PR worktree remains isolated; it has no runtime service left running.

Rollback removes the benchmark tooling and documentation. Preserve original
measurement artifacts. Production application files are unchanged.
