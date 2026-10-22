# 391 rank 1 measurement protocol

This accompanies the [proposed specification](perf-391-rank-1-specification.md)
and [implementation plan](../superpowers/plans/2026-10-22-perf-391-rank-1.md).
Commands below are for the separately approved implementation session. No new
measurement run or application change is authorized in this planning session.

## Structural expectations

On the fixed successful no-event two-POI fixture, main's source binding performs
initial capture + admitted entry + final check: 3 config serializations and
planned-source hashes, versus 4. Main route reads decrease from 5 to 3. Keep
separate coordinator-internal route reads and event/replay/refresh work. The
investigation's total 6 route reads/17 model dumps are whole-tick profile
counts; do not turn fixture-specific counts into production constants.

The updater and preparer direct wrapper acquisitions disappear on main's
admitted path (2 fewer); other real model/read/write acquisitions remain. Do not
promise removal of all 9 added gate lookups in the historical profile. No-event
source validation decreases from 3 checks to 2; live events retain their
distinct post-event check. POI copy/hash, phase/telemetry frame hashing, frame
creation, both schema validations and publication CAS counts stay intact.

Expected result: lower median per-tick thread CPU and fewer canonical path,
directory and profile-resolution calls. Admission depth-zero hold CPU should
fall on matched work; wall hold/wait may remain noisy due to scheduling and
filesystems. The 202.938-ms completion-delivery tail and historical cadence
failures have no promised improvement from this change.

## Resource and source prerequisites

Read cloud runtime instructions; preserve actor DOCKER_HOST/context and use the
configured user daemon. Record run owner PID/PGID, full command, output and
temporary paths, private project, volumes and image tags before starting. Use
the existing cleanup-owning runners and exit/signal handlers; close and reap all
workers/browser children and verify host processes, listeners and project
containers/networks/volumes after each run. No concurrent performance jobs. Stop
after timeout and verify old process tree before any retry.

Use clean exact application commits and identical package inventories/fixture,
hardware, production Dockerfiles, Nginx, limits, 1 Hz Prometheus and 30-minute
history. Preserve frozen harnesses: strict `13cbf1d5`, availability-v2
`f3029024b5950a267645195476da5cbca326f16a`. Use PR #405's unchanged diagnostics
from `f2a5b439` or its documentation-only descendant. Never copy corrected app
files into a frozen harness checkout. Record all output hashes.

Roles: original `25e34168f0e2cecb149b0323f1f5a795cb28cae0`, dev baseline
`33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96`, uncorrected candidate
`e1f657986f7b988a967ddd2bef8ca4626e30b5de`, corrected clean candidate full SHA.
If current dev differs, document it and stop for cohort/base revalidation. The
old candidate contains the measured `aa05a00a` application bytes.

Set these task-local shell variables to actual recorded absolute paths before
commands: `perf391_docs` (PR #405 tools checkout), `perf391_source` (one exact
application checkout), `perf391_output` (new private evidence parent),
`perf391_python` (private Python 3.11 interpreter with identical requirements),
`perf391_frozen` (clean v2 checkout), `perf391_sha` (full role SHA),
`perf391_project` (unique name per role/mode/repetition). Verify browser runtime
dependencies as in the original runners; do not substitute software versions.

## Component CPU and profile control

Run one component command per role/check-out and repetition (candidate pair, 3
repetitions, sequential, alternating order). Each output path must be new. It
records unprofiled thread CPU/wall time at 0/2/10/100/1,100 POIs and separate
cProfiles, using real producer/private stores, with no application lifespan:

```bash
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=10s 5m "$perf391_python" \
  "$perf391_docs/docs/performance/probes/perf391_independent.py" component \
  --root "$perf391_source" --output "$perf391_output"
```

Use the 2-POI tick as the primary component result. Report all sizes, sample
counts, CPU median/p95 and paired mean changes; counts and individual profile
callers identify removed work. Do not sum overlapping cumulative function times,
extrapolate a large-POI copy saving (copies unchanged), or compare wall cProfile
times as CPU. No fixed percentage threshold is invented here.

## Short production-path CPU controls

Run all four roles, 3 repetitions each, separate `off` and `counters` cohorts.
Rotate role order by one each repetition; use reverse order for the counter
cohort. No tracing/profiling during off runs. Use two Overview contexts plus
Operator at the existing 1920×1080 configuration. Each run has 120-second warmup
and 180-second measured duration, never a new sustained soak.

From the frozen v2 checkout, for each role/mode/repetition, choose a fresh
`starlink-operator-perf390-rank1-...` project/output and run:

```bash
PYTHONDONTWRITEBYTECODE=1 timeout --kill-after=110s 25m "$perf391_python" \
  "$perf391_frozen/tools/acceptance/performance_availability/run.py" \
  --sha "$perf391_sha" --project "$perf391_project" \
  --output "$perf391_output" --viewers 2 --operator --window 1800 \
  --warmup 120 --duration 180 --total-timeout 1300 --cpus 2 --memory 2g \
  --instrumentation off
```

Use `--instrumentation counters` in separate runs with distinct outputs. Use the
unchanged v2 report/comparability validator and retain every rejection. No
sparse-coverage workaround, threshold change or retry-until-pass. Compare
corrected/precorrection pairs first, corrected/original and corrected/dev next.
At least 3 accepted comparable pairs per claim/cohort are required. Present
per-run backend/Prometheus/browser CPU cores and paired mean/range/descriptive
95% interval, plus scrape p50/p95/p99 and producer thread CPU distributions.
Never mix off/counters cohorts or subtract estimated observer overhead.

The frozen counter probe's complete `_background_update_tick` boundary remains
valid. Public preparation wrappers bypassed by main may have no calls after the
refactor: label those spans absent, never zero-cost. Do not modify the frozen
probe to restore them. Per-tick component counts and complete tick CPU are the
primary producer comparison.

## Short admission/timing diagnostics

For uncorrected/corrected, run 3 paired repetitions per unloaded and loaded
workload with trace on. Use 5-second warmup/30-second measurement. Off workload
controls remain separate; add matching diagnostic off runs for calibration.
Reverse application order in repetition 2. Do not use `matrix.py`: its hardcoded
candidate is `e1f65798`; passing that matrix off as corrected evidence is wrong.

From PR #405 tools checkout, each fresh run:

```bash
PERF391_FROZEN_ROOT="$perf391_frozen" \
PERF391_BROWSER_ROOT="$perf391_browser" PYTHONDONTWRITEBYTECODE=1 \
  timeout --kill-after=110s 15m "$perf391_python" \
  "$perf391_docs/tools/diagnostics/perf391/run.py" \
  --sha "$perf391_sha" --project "$perf391_project" \
  --output "$perf391_output" --instrumentation trace \
  --viewers 2 --operator --warmup 5 --duration 30 --total-timeout 800
```

`perf391_browser` is the recorded existing Playwright dependency root. Use
`--viewers 0` and omit `--operator` for unloaded; `--instrumentation off` for
matching calibration runs. Analyze only completed directories, with a new
summary output:

```bash
timeout --kill-after=10s 2m "$perf391_python" \
  "$perf391_docs/tools/diagnostics/perf391/analyze.py" "$perf391_runs" \
  --output "$perf391_summary"
```

Record depth-zero producer repository wait/hold wall and thread CPU p50/p95/p99/
max, gate lookup counts, tick wall/thread CPU, collection, frame preparation,
final source validation, publication, source capture gaps, acquisition age,
observer wake/send/receipt, backend completion delivery, heartbeat lag,
throttling/scheduler pressure and dropped-event count (must be zero). Unchanged
`frame_inputs_are_current`, gate class and tick wrappers still trace the
optimized path. Existing public `producer_prepare` and updater callback
`source_binding_validation` spans no longer cover private main calls; mark those
unavailable and do not compare their durations/counts. Final-check call
counts/order are proven by regression spies, not invented trace coverage.

## Decision and stop rules

Structural reductions plus lower per-tick CPU demonstrate this optimization's
local effect. Whole-backend benefit requires comparable uninstrumented paired
savings beyond variation (descriptive paired interval wholly below zero);
otherwise report it unproven and stop for review. Gate hold/wait and scrape
latency must show no repeatable regression; an ambiguous tail requires review,
not a larger tolerance. Short capture intervals must still satisfy 1.5 seconds.

Any changed metric values/provenance, source acceptance, unavailable behavior,
independent accounting, replay order, schema/alias or stale-head behavior is a
correctness failure. Stop on failed tests, timeout, missing/ambiguous boundary,
workload/package mismatch, dropped events, cleanup failure or insufficient
accepted pairs. Retain negative/outlier attempts and exact remaining resources.

Do not infer a historical cadence cause, declare Task 6 passed, or launch a
60-minute soak even if all short controls pass. Publish results and request
separate review of any sustained qualification. Both existing PRs remain
unmerged; #391 remains open.
