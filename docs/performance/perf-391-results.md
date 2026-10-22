# #391 Task 6 performance and operational verification

Status: **NO-GO for Task 6 acceptance**. Matched controls and operational
verification are recorded, but no net backend CPU improvement is demonstrated
and candidate sustained source-observer cadence failed twice. The original
passed its 61-minute measured soak. No application, frozen harness, or threshold
was changed during this resume. PR #403 remains draft; #390 and #391 stay open.
No merge or deployment is authorized.

## Frozen sources and comparison boundaries

| Role                    | Application revision                       |
| ----------------------- | ------------------------------------------ |
| Original                | `25e34168f0e2cecb149b0323f1f5a795cb28cae0` |
| Current dev             | `33b60fa85c0d0b80d9b82ea5eac7d612a54f4c96` |
| Candidate               | `aa05a00a626faea475046544737fe218435dd6ab` |
| Availability-v2 harness | `f3029024b5950a267645195476da5cbca326f16a` |

Every new comparison uses that exact detached harness revision and
[availability contract](perf-391-availability-contract-v2.md). The original
strict harness at `13cbf1d5`, its original application baseline, failed
attempts, and all earlier evidence remain retained. Strict and v2 measurements
are separate cohorts. `origin/dev` was rechecked during sustained verification
and still resolves to the revision above.

Controls use production images/Nginx, real 1 Hz Prometheus, two Overviews,
Operator, a 30-minute history, 120-second warmup and 180-second measurements,
with rotated application order. All roles match Python 3.11.17, 89 installed
packages (SHA-256
`03cf956e500c08952d7b1a1747f24e391f6d0c5cf32a675a93c55847c92e9a40`), resource
limits and fixtures. Retained historical dependency drift prevents numerical
equivalence with the earlier strict cohort.

The host is an i9-10900K, 20 logical CPUs, approximately 64 GB RAM, rootless
Docker 29.8.1. Chromium 153.0.8010.12 uses SwiftShader at 1920×1080, DPR 1.
Physical GPU/display and live dish performance are unmeasured. Browser CPU
therefore describes this software-rendered diagnostic environment.

## Matched controls

All 21 individual runs passed availability, source, browser/API, and owned
cleanup gates: four uninstrumented repetitions and three counter-instrumented
repetitions for each application. The fourth uninstrumented triad replaces
comparison coverage lost in repetition 2. Both rejected comparisons remain
retained; their sparse Prometheus storage resource spans were incompatible. No
guard was changed. Each application pair has at least three accepted comparisons
in each instrumentation cohort; original/candidate has four off and three
counter comparisons.

CPU below is mean cores used ± sample standard deviation across individual runs.
One core means one CPU-second per wall-clock second. Counter results are
separate measurements.

| Instrumentation | Application | Backend cores     | Prometheus cores  | Browser cores     |
| --------------- | ----------- | ----------------- | ----------------- | ----------------- |
| Off, n=4        | Original    | 0.23424 ± 0.00187 | 0.02074 ± 0.00070 | 9.62304 ± 0.00584 |
| Off, n=4        | Dev         | 0.23469 ± 0.00400 | 0.02105 ± 0.00091 | 9.62412 ± 0.00650 |
| Off, n=4        | Candidate   | 0.23473 ± 0.00144 | 0.02112 ± 0.00067 | 9.62143 ± 0.00675 |
| Counters, n=3   | Original    | 0.25087 ± 0.00088 | 0.02094 ± 0.00051 | 9.60599 ± 0.00630 |
| Counters, n=3   | Dev         | 0.24885 ± 0.00554 | 0.02087 ± 0.00084 | 9.60614 ± 0.00810 |
| Counters, n=3   | Candidate   | 0.24774 ± 0.00321 | 0.01980 ± 0.00040 | 9.60839 ± 0.00517 |

For accepted uninstrumented original/candidate pairs, backend CPU changed
**+0.21%**, ranging from −0.68% to +0.92%. The descriptive paired t 95% interval
is **−0.84% to +1.27%**. There is no demonstrated whole-backend CPU saving
beyond variation. The counter cohort's −1.25% mean change also has an interval
crossing zero (−3.72% to +1.21%). These small sequential samples are not
production confidence estimates or independent hardware replication.

### Preparation cost and transferred work

Mean per-run thread CPU timings from the counter cohort:

| Work                     | Original | Dev      | Candidate |
| ------------------------ | -------- | -------- | --------- |
| `/metrics` preparation   | 4.794 ms | 4.715 ms | 2.376 ms  |
| Producer background tick | 2.898 ms | 2.945 ms | 5.760 ms  |
| Event-loop delay, mean   | 7.322 ms | 8.804 ms | 6.984 ms  |

Scrape preparation uses approximately **50.4% less thread CPU** than original.
Producer tick CPU approximately doubles. These observations support the intended
transfer of work out of scrapes, but do not establish net CPU savings. The first
measured counter snapshot is excluded from timing-array aggregation because its
interval straddles warmup; cumulative counters use final minus first measured
snapshot. Individual timing counts and distributions remain retained, including
unequal acquisition counts.

Counter instrumentation adds approximately 7.21% backend CPU for original, 6.82%
for dev and 5.68% for candidate, comparing corresponding off/counter
repetitions. The v2 read-only source observer also has measured overhead and
different baseline/candidate capture implementations. No speculative overhead
subtraction is used to claim application savings.

Mean per-run Overview history request p95 was 341.0/329.4/325.0 ms for
original/dev/candidate with instrumentation off; 342.8/342.1/327.6 ms with
counters. These are descriptive averages of per-run percentiles. All individual
request distributions, sample counts, memory/storage slopes and comparison
rejections are retained in the evidence.

## Sustained acceptance: candidate gate not met

| Run                         | Measured duration        | Raw successful scrapes    | Maximum raw scrape interval    | Result                                |
| --------------------------- | ------------------------ | ------------------------- | ------------------------------ | ------------------------------------- |
| Original                    | 3,660.000 s              | 3,661                     | 1.020 s                        | Passed                                |
| Candidate, first            | 3,659.979 s sampled span | 3,660                     | 1.034 s                        | Rejected: source capture gap          |
| Candidate, identical repeat | 1,650.002 s sampled span | Partial evidence retained | Not a completed acceptance run | Stopped after another known violation |

The first candidate completed the requested full measured interval. Its frozen
raw cadence, full measured-value and final history/projection validators pass
when replayed independently. This does **not** convert it into an accepted
result. Source observation coverage failed once: **1.754899 seconds** between
captures against the unchanged **1.5-second** bound, at
`2026-10-21T23:00:24.477549Z`. Original maximum capture gap was 1.336914
seconds. All six rolling history checkpoints, including four overlapping
intermediate checks, are retained for both full-duration runs.

One predeclared identical candidate repetition reproduced a **1.583978-second**
capture gap at `2026-10-21T23:49:37.413576Z`. It could no longer pass, so its
owned parent received SIGTERM and completed normal cleanup. Partial evidence
remains rejected. No further long soak was launched, and neither bound was
relaxed.

At the captures bracketing the first gap, publication was ready with unchanged
source, route, configuration revision and coordinator identity; all 11
observation fields were available. State inside the unsampled interval is
unobserved. Acquisition age was 0.8405 seconds before and 1.5876 seconds after.
The capture body took 0.560 ms; its timer starts **inside active-leg
admission**, so it excludes queue/admission wait and HTTP
scheduling/serialization. It cannot exonerate those paths. A nearby history
request took 972.8 ms. The evidence does not isolate host scheduling,
backend/event-loop/admission delay, or observer scheduling sufficiently to
classify an application regression or a harness contract defect. Treat this as
an unresolved acceptance failure, not an assumed environmental exception.

The original source sampler observed 3,503 distinct acquisition timestamps; the
rejected full candidate observed 3,540. These are sampled distinct values, not
exact producer observation counts or proof of exact 1 Hz acquisition. Raw scrape
cadence and source freshness/provenance are separately checked. The original
source-capture body averaged 1.016 ms CPU and candidate 0.183 ms; this
additional observer favors candidate by about 0.00083 cores in these runs. It
excludes framework and admission costs. No speculative subtraction is used.

### Memory, storage and series observations

The following candidate figures are **rejected-run diagnostics**, not an
accepted soak performance comparison:

| Full-duration measurement                    | Original         | Candidate, rejected |
| -------------------------------------------- | ---------------- | ------------------- |
| Backend CPU, cores                           | 0.24072          | 0.23929             |
| Prometheus CPU, cores                        | 0.01887          | 0.01912             |
| Browser CPU, cores                           | 9.62445          | 9.62570             |
| Backend cgroup memory, first → last          | 338.7 → 356.6 MB | 341.4 → 359.3 MB    |
| Server PSS, first → last measured capture    | 382.5 → 395.8 MB | 380.9 → 397.9 MB    |
| Browser PSS, first → last                    | 2.065 → 2.631 GB | 2.076 → 2.601 GB    |
| Browser PSS fitted growth                    | 5.51 MB/min      | 5.53 MB/min         |
| Prometheus cgroup memory, first → last       | 39.2 → 54.8 MB   | 33.8 → 58.0 MB      |
| Prometheus logical WAL, first → last sampled | 0.121 → 4.861 MB | 0.158 → 4.884 MB    |

Positive memory trends remain visible; a one-hour observation does not prove
long-term boundedness. Server PSS analysis uses only the measured interval. The
first analysis accidentally included warmup for that supplemental series; both
its original output and the corrected analysis are retained. Browser startup
growth is larger than its later trend, so short-control slopes must not be
extrapolated as hourly steady growth. The eight-hour integration and physical
GPU qualification remain necessary.

SQLite database bytes were 1,986,560 and WAL bytes zero in both full runs;
mission bytes 1,832,537 and Operator bytes 164,025 remained constant in steady
operation. Continuous history updates are real Prometheus ingestion; this does
not claim steady Operator writes. Prometheus blocks remained at their seeded
size while its WAL grew normally. Docker log allocation/rotation is not part of
the frozen storage sampler; combined Compose logs are preserved as evidence, not
a substitute for measuring engine log allocation.

Head-series counts plateaued at **198 original / 201 candidate** from the first
five-minute populated TSDB snapshot through completion. The difference is
consistent with three existing route timing families now explicitly published as
NaN when unavailable (duration, departure, arrival); the old scrape writer
created their labeled children conditionally. Status-labeled independent
histograms retain their existing initialization behavior. No broader #393
cardinality cleanup was performed.

Both full-duration containers plateaued at one server plus 18 zero-RSS defunct
Chromium children after startup. Original process-state inspection confirms
state `Z`; candidate supplemental process counts and zero-RSS entries match.
Aggregate process PSS is explicitly incomplete for these entries; server PSS
remains separately measurable. Renderer/slide-cache sources are unchanged
between original and candidate. This pre-existing process residue is retained as
an operational risk; all task containers and their processes are removed.

## Separate controlled mission and Operator activity

All four frozen-v2 transition runs passed: original/candidate, off/counters,
with two Overview clients and Operator. They performed three measured mission
activation/deactivation operations plus the frozen journal workload. Maximum
observed recovery after a measured operation completed was 282.1 ms for original
and 234.7 ms for candidate, below the unchanged two-second gate. Candidate setup
recovery reached 1,012.6 ms in one run and passed its explicit setup rule.
Values, provenance, clocks, raw grids, polling and HTTP gates were checked
outside event-specific availability windows. Every run cleaned up. These passes
do not waive the steady-soak capture failures.

## Snapshot component and compatibility checkpoint

The unchanged component probe ran separately against final code, 200 iterations
at 0/10/100/1,100 POIs, on prometheus-client 0.19.0 and 0.26.0. At 1,100 POIs:

| Component wall median           | Client 0.19.0 | Client 0.26.0 |
| ------------------------------- | ------------- | ------------- |
| Detached freeze                 | 0.865 ms      | 0.846 ms      |
| Stage and seal                  | 3.555 ms      | 3.488 ms      |
| Validated publication           | 0.187 ms      | 0.188 ms      |
| Capture head                    | 0.689 µs      | 0.680 µs      |
| Collect                         | 1.136 ms      | 1.154 ms      |
| Standard registry serialization | 5.423 ms      | 9.517 ms      |

A frame owned approximately 746,612 reachable bytes; exactly one committed frame
remained after 100 replacements. Stage/seal peak traced allocation was 663,442
bytes, collect about 630–648 KB and serialization about 849 KB. Both 30-second
one-writer/three-reader contention probes completed all operations, reported
zero mixed frames and zero remaining owned threads. These are component figures,
not application savings or sustained acceptance. Full quantiles, allocations,
version identity and all POI sizes are in the results artifact.

## Regression and rollback evidence

The bounded application fix added during Task 6 before these measurements
captures one position frame and maps nonfinite values to JSON null, fixing a
reproduced `/position-table` HTTP 500 during ordinary unavailability. It leaves
Prometheus NaNs intact and adds seven regression cases. Two additional tests
cover overlapping successful/failed exposition diagnostics. Application bytes
have remained unchanged at `aa05a00a` throughout all v2 controls and soaks.

Canonical backend: **4,486 passed, 20 skipped**, one existing Cartopy warning,
630.26 seconds under a 30-minute limit. Earlier static, client compatibility,
concurrency, scrape-purity and frontend passes remain retained in the
[v2 checkpoint](perf-391-task-6-availability-checkpoint.md). Application bytes
have not changed; final documentation checks are recorded separately.

The broad tooling suite is not green: its bounded attempt timed out. Focused
follow-up with the correct subprocess Python path passed 14 of 17 cases; two
unchanged Dockerfile contract assertions and a missing `pdftoppm` dependency
remain documented. All three were independently reproduced on the dev-equivalent
rollback tree (3 failures in 1.39 seconds). No assertions were weakened or
unrelated code changed. The frontend dependency recovery incident and rejected
first short run are retained in the
[v2 checkpoint](perf-391-task-6-availability-checkpoint.md).

The verified revert candidate is `bbcdde453480d98a4f3c4f3eea310cbbbedba0db`,
whose full tracked tree matches current dev. Its 114 focused tests passed, and
production Docker/Nginx/Prometheus smoke passed. Bundles and tree proof are
retained. No rollback was deployed. Reversion restores the former
scrape-triggered simulator/ETA hazard; it needs no durable data migration and
retains existing storage contracts.

## Operational qualification

The separate production qualification passed 14 phases with real Prometheus, two
Overviews and Operator; only dish acquisition was synthetic. It exercised live
disconnect/recovery, preparation/exposition failure and recovery, configuration,
replay clocks/cancellation, mission export, restart durability and UI recovery.
Four workers completed 726 concurrent scrapes with zero unexpected failures
across three backend incarnations.

Audits verified one frame read for each coupled collection, all 29 families plus
position alias, and zero scrape-triggered simulator, ETA, manager, filesystem,
storage or source-advancement calls. Thirteen stored Operator records including
ten notes survived restart unchanged. Screenshots were visually reviewed after
bounded UI recovery. All 233 recorded browser failures were classified as
explicit restart/fault or existing optional-source unavailability; none were
silently discarded. Earlier failed qualification attempts remain retained.

Existing live-to-simulation configuration does not replace its coordinator;
qualification used within-mode changes and explicit restart. Optional simulation
flight-archive availability and physical hardware remain limitations. Retained
concurrency tests cover overlapping successful/failed exposition diagnostics.

## Evidence and disposition

[Machine-readable results](probes/perf391-task6-results.json) retain per-run
counts, distributions, paired variability, rejected comparisons, component
allocations, actual source observations and failed-soak diagnostics. Expanded
analysis and raw evidence remain under the Task 6 workspace. A final immutable
path/hash manifest accompanies the result digest; original inventories are
retained and reverified independently.

**Task 6 is not accepted.** The whole-backend CPU improvement gate is unmet and
there is no successful candidate sustained acceptance run. A sampling/admission
trace that distinguishes request scheduling, admission wait, backend wakeup and
response time is the next diagnostic needed; any acceptance-policy or
architecture change requires review. No speculative application or validator fix
was made. Keep #403 draft/unmerged, #391 open and #390 open for its final
eight-hour gate. See [review and rulings](perf-391-task-6-review.md) and the
[final evidence manifest](probes/perf391-task6-manifest.json) for baseline
verification and cleanup. No production deployment occurred.
