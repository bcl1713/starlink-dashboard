# Overview history efficiency follow up design

Approved addendum to the existing Overview history design and implementation
plan, following Brian's approval in this session. Continue issue
[224](https://github.com/bcl1713/starlink-dashboard/issues/224) from current
`dev` rather than rebuilding the optimizations shipped by
[PR 228](https://github.com/bcl1713/starlink-dashboard/pull/228). The intended
outcome is efficient one-second history polling with truthful telemetry, bounded
retained state and continuous chart motion. Default promotion remains
conditional on measured acceptance.

## Inspected baseline and remaining evidence

Inspection used clean `dev` at `913175dc0e19a349a9d724d1e7efcb32f1489099`. PR
228 merged the demand-driven incremental cache, stable sampling grid,
completed-result reuse, shielded refreshes and memoized chart processing. Its
original
[implementation plan](../plans/2026-10-01-overview-history-efficiency.md) and
cache semantics remain the starting contract.

The
[qualified operator acceptance](https://github.com/bcl1713/starlink-dashboard/pull/228#issuecomment-5935222378)
records a completed 3600.053-second Forge soak at
`9803ee21b4ee774de18f066bb0294e8ab19c9338`, using real Prometheus, production
Nginx/backend, public simulation, one viewer and a 30-minute window:

- History p95 was 360 ms and p99 was 371 ms, with zero captured errors.
- Backend plus Prometheus CPU increased 16.555 percentage points of one core
  against the baseline, with unequal history coverage and phase durations.
- Endpoint JS heap grew 25.008 MiB. Browser summed RSS grew 377.625 MiB overall;
  the last 20 minutes had a bounded working set and a fitted slope of +0.49
  MiB/min, which Brian accepted for merging that candidate.
- A configured one-second delay produced median request-start spacing of 1.344
  seconds. That evidence does not establish strict one-Hz arrivals.
- Chromium used SwiftShader. Recording was waived for that run; screenshots and
  native fullscreen observations were retained.

Those findings justify follow-up measurement, not an assumed root cause or a
retroactive failure of the approved merge. The original fixture report and plan
contain pending items predating this operator decision; preserve them as
historical records and record new evidence separately.

Current code keeps history polling active in background tabs, following
`26933ac6` for issue 257. Chart motion pauses while hidden. Overview user
guidance reflects this; the API cadence section still describes paused interval
polling and needs correction. Preserve the shipped cross-window refresh contract
when measuring or optimizing background work.

## Approach selection

Use controlled profiling of the shipped design first. Measure warm tail queries,
backend projection/merge and response serialization independently; measure
browser parsing, React Query processing, retained chart buffers,
projection/scale scans and uPlot uploads. These are hypotheses about cost
centers, not established causes.

Completed-response serialization reuse is a possible targeted follow-up if
profiling demonstrates repeated serialization is material. It must be keyed by
the published snapshot generation, bounded to the active configuration, and
invalidated atomically without changing the full-bundle API or errors.

Prometheus recording rules are an alternative only if authoritative rollup
evaluation remains the measured bottleneck. Their sustained CPU/storage,
warm-up, missing backfill and deployment effects warrant a separate design
decision. A browser delta protocol likewise changes the interface and is not
selected in this follow-up.

## Measurement design

Use Forge, matching the previous operator-directed execution location. Before
execution, verify current access, available source artifacts and host hardware.
The local actor Docker daemon was reachable at
`unix:///run/user/1002/docker.sock`, Docker 29.8.1 with overlayfs; this is
runtime discovery, not evidence that earlier and current runs use identical
hardware or allocations. The current executor reports hostname `forge`; run
task-owned work here after recording hardware rather than adding an SSH hop. No
cloud status tool or network policy snapshot was available locally, so
credential readiness is not established by that discovery.

Use a task-owned Compose project with production Dockerfiles, Nginx and
Prometheus configuration, loopback ports and isolated volumes. Archive exact
tracked candidate inputs, preserve proxy/CA trust, refuse existing project
resources, and remove only resources created by the run. Record candidate SHA,
dirty state, image IDs, dependency versions, hardware, renderer and actual API
responses. Keep sensitive configuration out of evidence.

Compare original full-range five-second computation, current incremental
five-second polling and current incremental one-second polling on the same host
and comparable fixed-density telemetry. Use a bounded harness adapter for the
full-range control with the existing authoritative query function; report
differences from the historical pre-cache SHA. Never use older frontend layouts
as an unqualified browser baseline. Separate cold loads, ordinary tail updates
and scheduled full reconciliations in the results, and include reconciliations
in the overall warm latency distribution.

Run 5/15/30/60-minute and 3601-second custom windows, transitions in both
directions, one and two viewers, sequential same-interval reads, hidden/resume,
resize/fullscreen, failures and recovery. Record upstream query count, queried
span and evaluation points, active refreshes and outstanding HTTP work. Measure
CPU as both core-seconds per wall-second and percentage of one core; record
logical CPU count rather than switching normalization between phases.

For browser memory, record ordinary heap samples and comparable retained heap
after controlled GC in separate series. Preserve endpoints and late-run trend
evidence; an uncollected endpoint difference alone cannot identify a leak.
Measure chart processing/upload counts independently of page clock ticks, long
tasks and frame continuity at 1920 by 1080, DPR 1. Disclose software rendering
and keep physical-GPU claims outside this evidence.

Measure configured timer delay and actual request-start/response intervals
separately. Assess slow responses and error backoff explicitly. Do not change
the scheduler to promise strict one-Hz starts or introduce queued/overlapping
browser requests without a reviewed scheduling design.

## Acceptance and delivery

Apply the existing proposed budgets on the recorded representative host: healthy
warm p95 below 500 ms; combined backend/Prometheus CPU increase at most 10
percentage points of one core over the comparable five-second baseline; backend
RSS and browser retained heap growth at most 16 MiB after warm-up over at least
60 minutes. Record all phase durations and data density. Treat the previous
operator RSS exception as acceptance of that candidate, not an automatic waiver
for a new default-promotion decision.

Keep raw/aggregate reference comparisons, masking, source authority, gaps,
immutable snapshots, settings invalidation, cancellation, bounded retry and
shutdown controls. Preserve one shared history subscription, aircraft trail,
background refresh, scale hysteresis and chart motion. Query/cache timestamps
must never replace source acquisition timestamps.

Profile and publish the baseline before selecting product changes. Any targeted
fix must include a reproducing control and before/after measurements. Run
relevant repository checks, exact-candidate production controls, a fresh
60-minute soak and rendered motion/lifecycle evidence after material changes.
Capture video if supported; any alternative to required recording must be
explicitly accepted rather than inheriting the prior run's waiver.

Promote the one-second default only when the applicable performance and behavior
gates pass. Retain explicit five-second build rollback and five-second error
polling. Correct API/operator guidance with the measured behavior and
limitations. Deliver a separate reviewed PR against then-current `dev`.
Production deployment and closure of issues 211/213 remain outside scope; link
independently relevant findings without claiming their root causes.

This addendum preserves the prior design and approvals. Its follow-up
implementation plan will name the benchmark/profiling interfaces, isolated
project resources, verification commands and execution method.
