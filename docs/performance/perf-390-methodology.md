# Original baseline and comparison contract (epic 389)

Issue [#390](https://github.com/bcl1713/starlink-dashboard/issues/390)
establishes the pre-optimization reference and closes **last**, after the
integrated eight-hour soak. This kickoff changes acceptance tooling and
documentation only. It does not authorize production changes, rollout, merge,
lower freshness, or relaxed mission and Operator semantics. Preserve the
completed #211 and #224 scopes.

## Immutable reference

The original application is `25e34168f0e2cecb149b0323f1f5a795cb28cae0`. Archive
that exact commit before building; never build a dirty application tree. The
external harness has its own committed SHA, independent of the application SHA.
Each new output directory is write-once by convention; the runner refuses to
reuse it. Preserve original evidence and its SHA-256 inventory. Correct a bad
run by adding another run with an explanation, never overwriting it.

Use the **same harness revision** for original and candidate runs. If
measurement code changes, rerun the original application with the new harness,
retain both sets, and explain the difference. A newer baseline supplements the
original; it does not replace it. Record comparisons to original and immediately
preceding `dev` separately. Never aggregate speedups across unlike workloads.

## Reproduce a run

Use the configured actor Docker daemon and existing installed Playwright. No new
service, application dependency, production endpoint, or monitoring deployment
is introduced. Run from an isolated worktree containing the committed harness:

```sh
timeout --kill-after=20s 90m python3 tools/acceptance/performance/run.py \
  --sha 25e34168f0e2cecb149b0323f1f5a795cb28cae0 \
  --project starlink-operator-perf390-original-two-r1 \
  --output /tmp/perf390-evidence/original-two-r1 \
  --viewers 2 --operator --window 1800 --warmup 60 --duration 600 \
  --total-timeout 5300
```

Select a unique project and output for **every** run. Use no concurrent
benchmark projects. Each service has two CPU equivalents and 2 GiB RAM by
default; these are limits, not reserved or pinned cores. Browser and harness use
the host allocation. Capture host contention/load separately when reproducing on
another machine. Builds use the checked-in production Dockerfiles, image
revision labels and production Nginx proxy. Cache state and pulled base images
affect build/startup; build duration is not an application latency measurement.
Retain actual image IDs, source archive digest, Compose configuration, Docker
version/storage driver, host CPU/kernel/RAM/filesystem, browser version/renderer
and resource limits. Do not commit registry configuration, credentials, real
missions, IPs or provider secrets. Review raw logs before distributing them.

The runner reuses Operator acceptance's `Owner` for admission, command
deadlines, PID/process-group ownership, signal cleanup, disposable volumes,
image tags and optional loopback relay. If a platform requires that relay,
record it and compare only with the same transport: a Docker exec per connection
can dominate latency.

## Fixed fictional workload

`perf390-v1` reuses the existing Operator demo seed: two saved missions with two
legs each and six genuine Operator records (notes, conferences, transport
reports). It adds an explicitly fictional equatorial ocean route with five route
points. The real production startup, system clock, simulation coordinator,
background tick, mission activation/timeline generation and Prometheus scrape
remain active. Activation selects the first leg through the public API. This is
synthetic simulation, not evidence from a live dish or an accepted live archive.

The existing history seed supplies 4,201 seconds of 11 metric series with finite
zeros, spikes and varying values. Real Prometheus loads these into a private
TSDB. Current data comes from normal **one-second scrape and rule evaluation**.
The frontend's independently configured **one-second history polling** is left
unchanged. Retain seed endpoint/time and fixture hashes. Synthetic historical
density must not be presented as physical source-observation freshness.

Viewers are independent browser contexts/pages at 1920×1080 and DPR 1. The
currently installed browser runs headlessly with explicit SwiftShader support;
record its actual renderer. Headless viewport emulation is **not** physical
fullscreen or representative hardware GPU acceptance. Do not assert 10-foot
display FPS from this lane. An Operator client opens the actual Operator page;
the sampler also performs one explicit records read per five seconds. With
`--operations`, measured quarter points switch to leg two, deactivate the
mission, and reactivate leg one; each operation also writes one idempotent
journal note through the real API. Keep this activity workload separate from
steady state.

Required matrix, with coverage recorded per cell rather than inferred:

| Dimension  | Cases                                                                                    |
| ---------- | ---------------------------------------------------------------------------------------- |
| Clients    | No viewer; one Overview; two Overview clients; Operator only; two Overview plus Operator |
| History    | 300, 900, 1800, 3600 seconds                                                             |
| State      | Cold process/history; warm active mission; mission/leg transitions                       |
| Inputs     | Simulation; accepted live-like telemetry; missing metrics; failure/recovery              |
| Display    | Optional overlays off/on; visible; hidden/resume; focus changes                          |
| Operations | Operator reads/writes; restart; export under load                                        |

The compact runner automates the first three rows and Operator reads/writes. Use
existing acceptance journeys for overlays, failure/recovery, restart and export.
Record unexecuted cells as **not measured**, never passed. The fixed simulation
seed does not prove live SQLite recording or live source freshness. Use a
synthetic live adapter before applying archive/active-mission budgets to live
optimizations; do not substitute the mock-transport microbenchmark.

## Measurement and overhead

Primary timings use `--instrumentation off`: fixture inputs only, no backend
monkeypatches or profilers. Every five seconds sample cumulative service CPU and
cgroup memory/I/O, browser process CPU, available RSS/PSS, JS heap, task
duration, frame intervals/long tasks and actual API request completion latency.
Browser metrics retain page and process owners. RSS sums are descriptive and may
double count shared pages; they are never a leak diagnosis. Missing PSS or I/O
counters must be marked unavailable rather than claimed as zero activity.

Every 30 seconds, a short owned backend exec reads file sizes/allocated blocks,
SQLite database/WAL bytes and Prometheus series/churn/storage metrics. It does
not open application SQLite databases or run checkpoints. `data` includes the
mission and Operator subdirectories: do **not** sum these overlapping
categories. Prometheus WAL/head/block byte gauges are separate from application
files.

Repeat matched runs with `--instrumentation counters` for bounded in-memory
backend ASGI wall timing, per-tick and metrics-preparation thread CPU/wall time,
event-loop delay, SQLite connection/statement/explicit transaction counts, real
Prometheus range-query count and planned evaluation spans/points. The query
counter reuses the existing `QueryTrace`; planned evaluation points are an
estimate, **not actual Prometheus samples scanned**. SQLite trace counts
describe SQL statements, not rows changed, fsyncs or automatic checkpoint
frequency. Each timing buffer holds at most 4,096 values and is drained on
sampling. Counter runs add tracing and transport wrapping; report them
separately from primary timings. Thread CPU for `_prepare_metrics` includes
export construction/serialization; ASGI wall timing includes scheduling. It is
not exclusive async request CPU.

Record sampler wall-time per sample; sampling time/interval is observer duty,
not CPU attribution. Observer HTTP reads and short exec processes also create
load. Estimate overhead using matched off/counters runs and repeated original
controls. Do not subtract noisy differences as if exact. Use the existing
`tools/profile_overview_history.py` and opt-in HTTP cProfile for separate
first-order diagnostic profiles; never mix profiler timings into normal p95.
`tools/benchmark_overview_history.py` uses MockTransport and cannot replace
them.

Quantiles use nearest rank and report sample counts. Warm-only ordinary least
squares slopes include time span and endpoints. A short startup-heavy slope or a
positive noisy slope does not establish a leak. Discard warm-up consistently;
repeat at least three canonical runs and report min/median/max variability
before attributing a performance gain. Report errors, late samples and
outstanding work. Keep large samples/traces/screenshots outside Git; check in
compact reports and hash inventories referencing their retained location.

## Comparison and operational gates

```sh
python3 tools/acceptance/performance/report.py \
  /retained/original-one-r1/summary.json \
  /retained/candidate-one-r1/summary.json > /retained/comparison.json
```

The comparison refuses changed workload, hardware, runtime, instrumentation,
browser, harness revision or materially different measured duration. Inspect
coverage and missing measurements as well as deltas. Record absolute and
percentage CPU/RAM/disk/latency changes, correctness, negative results, CI
proof, rollback and risk in **every dependent PR**. Keep the rollup linked to
original run IDs and original application SHA.

Budgets are provisional until established with measured variability and
operational needs. A warmed history p95 below 500 ms is a **proposed gate to
validate**, not an assumed baseline result. Preserve 1 Hz qualified history,
source acquisition provenance, status responsiveness, active-leg truth,
Starshield default availability and durable Operator/flight evidence. Separate
genuine validation from estimate-confidence disclaimers.

For each major hot-path change, run matched minimum 60-minute steady-state soaks
after warm-up (`--warmup 300 --duration 3660 --total-timeout 7200` under an
outer 125-minute timeout, allowing build and cleanup). Once the epic integrates,
target eight measured hours (`--duration 28860 --total-timeout 32400` under an
outer 550-minute timeout). Hardware browser/fullscreen and the remaining matrix
need their existing acceptance journeys too. Require no unbounded resource trend
attributable to changed code and no material interaction/FPS/service regression.
If hardware or coverage is unavailable, report that limitation and leave the
gate open. This kickoff cannot close #390 or establish the final integrated
result.

## Failure and teardown

On failure or signal the owner terminates and reaps owned command groups, closes
browser contexts/server, removes its Compose containers/networks/private
volumes, removes owned image tags and archive/source directories, and verifies
loopback listeners are free. Evidence remains. `ownership.json`, `run.json` and
`browser-cleanup.json` record results. Never infer cleanup solely from a
successful test. A hard kill cannot run cleanup handlers: inspect recorded PIDs
and confirm host process ownership before terminating verified survivors. Do not
use broad process kills or Docker pruning.

For interrupted cleanup, use the retained `compose.json` and **recorded**
project:

```sh
docker compose -p starlink-operator-perf390-original-two-r1 \
  -f /tmp/perf390-evidence/original-two-r1/compose.json down --volumes --remove-orphans
docker ps -aq --filter label=com.docker.compose.project=starlink-operator-perf390-original-two-r1
docker network ls -q --filter label=com.docker.compose.project=starlink-operator-perf390-original-two-r1
docker volume ls -q --filter label=com.docker.compose.project=starlink-operator-perf390-original-two-r1
```

Verify recorded process groups/browser PID and both ports on the host as well.
Preserve acceptance evidence and the open-PR worktree; keep no task service
alive.
