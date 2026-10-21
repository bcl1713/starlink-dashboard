# #391 availability-contract investigation — review required

Date: 2026-10-21. Candidate application:
`aa05a00a626faea475046544737fe218435dd6ab`. Frozen #390 harness:
`13cbf1d54b526307747578ecd4fc691562846834`.

**Finding:** the strict finite-history check conflicts with intentional source
unavailability. A bounded, explicitly recorded transition exception is justified
for review. No application or acceptance-methodology change has been made. This
finding does not establish that all Task 6 failures have the same cause, and
does not waive the outstanding performance or 60-minute acceptance gates.

## Runs paused and evidence retained

The active fourth off-instrumentation control was allowed to finish. Its
original and current-dev runs passed; the candidate completed its measurement
but failed final dense-finite history validation (`browser.mjs:559`). Its cold
history was finite. This is consistent with a transition sample entering the
later rolling window, but that run did not retain the exact final response, so
that particular failure is not attributed conclusively. All raw results, logs,
and cleanup records remain retained; the failed candidate is not an accepted
control.

The orchestration parent was suspended while its already running isolated child
finished, then terminated through its normal signal handler after child exit and
cleanup. No further counter controls, activity runs, or soaks were started. The
manifest's interrupted in-flight entry is supplemented by
`availability-review-current-control-result.json`; the original manifest is not
rewritten to relabel the failure as a success.

A separate diagnostic used the existing candidate production images, production
Nginx, real Prometheus at 1 Hz, normal background collection, and synthetic dish
RPC. It recorded publication commits and collected values outside publication
locks. This instrumentation changes timing; its results are diagnostic evidence,
**excluded from every performance comparison**. It completed in under a minute
of application activity with explicit seven-minute wall limit and owned cleanup.

## Exact timing and limits of the first capture

The original failing capture proves that all 11 raw **query evaluation points**
at Unix `1792601478` (2026-10-21 16:51:18 UTC) were `NaN`, while the API
returned 1,800 finite points rather than 1,801. Follow-up health was already
ready. That capture used `query_range`, which returns evaluation coordinates,
not acquisition or necessarily scrape timestamps. It did not record publication
transitions or raw range-vector sample times. The original TSDB was removed by
required cleanup; its exact scrape instant and pending duration cannot now be
recovered. Earlier wording attributing that sample specifically to `pending` was
too definite.

The new reproduction records actual stored scrape sample times using an instant
range-vector query, separately from publication commit times:

| Event                                             | Publication not ready                        | Observation unavailable                                          | Actual Prometheus result                                                              |
| ------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| First mission activation                          | 424.964 ms                                   | 1,425.965 ms                                                     | All 11 stored `NaN` at 17:11:01.374 UTC                                               |
| Two further activations                           | 74.394 / 83.255 ms                           | Same as not-ready interval                                       | No transition NaN caught by the scheduled scrape                                      |
| Three deactivations                               | 4.303 / 5.211 / 6.406 ms                     | Same as not-ready interval                                       | No transition NaN caught by the scheduled scrape                                      |
| Configuration reset                               | 2.228 ms                                     | 1,003.520 ms                                                     | All 11 stored `NaN` at 17:11:08.374 UTC                                               |
| Paced replay activation                           | 9.656 ms                                     | 9.656 ms for position                                            | Position recovered; replay-unavailable fields remain individually unavailable         |
| Replay cancellation                               | 6.196 ms                                     | 521.585 ms                                                       | An additional diagnostic collection caught NaN; scheduled scrape missed the short gap |
| Deliberate live disconnect                        | Remained ready with unavailable observations | 3,241.675 ms from first unavailable commit to recovered position | Three all-11 NaN scrapes; duration includes the intentionally held outage             |
| Deliberate input preparation failure and recovery | 2,497.982 ms including failed state          | 3,288.645 ms                                                     | Three all-11 NaN scrapes; duration includes the intentionally held fault              |

For the first activation, the sequence was:

1. 17:11:00.539549: mission persistence invalidated the old publication.
2. 17:11:00.957598: activation HTTP request completed successfully.
3. 17:11:00.964513: complete **ready, observation-unavailable** frame committed.
4. 17:11:01.374: Prometheus assigned its stored NaN sample timestamp; collector
   ran at approximately 17:11:01.376007.
5. 17:11:01.965513: complete finite observation frame committed.

Thus the recorded NaN in this reproduction came from a complete ready frame, not
an incomplete publication or the earlier pending interval. Ready means that the
frame preparation/commit succeeded; it does not guarantee a usable source
observation. Configuration reset behaved similarly: ready-unavailable at
17:11:08.053543, finite again at 17:11:09.054835.

The mechanism is visible in
[`refresh_inputs.py`](../../backend/starlink-location/app/core/metrics/refresh_inputs.py):
a derived refresh can reuse only the current source's previously admitted
observation. Reset-generated defaults, changed source identities, and
uncommitted observations are rejected. A complete frame with `telemetry=None` is
then valid. The next normal accepted observation restores finite values. The
diagnostic does not establish a universal duration bound under other loads or at
1,100 POIs; the numeric limits proposed below are acceptance policy for review.

Existing deterministic tests also verify expiration after advancing a retained
live source by 11 seconds: observation identity becomes unavailable, observation
timestamps and independent instruments do not advance, and no scrape or derived
refresh manufactures an observation. This was tested rather than reproduced by
waiting for an additional long-running runtime scenario.

## What should become unavailable

The 11 history families are five position/motion values (latitude, longitude,
altitude, speed, heading), four current network values (latency, down/up
throughput, packet loss), obstruction, and signal quality. **None is route
timing or an independent counter/histogram.** When no whole observation is
admissible, all 11 legitimately become NaN together.

That is not an assertion that their availability must always match. The
diagnostic also found the expected narrower cases:

- During replay, four network fields and obstruction were unavailable while
  position remained finite, reflecting the replay availability flags.
- The first recovered live position did not yet have a usable speed acquisition;
  speed remained NaN for one additional scrape while other observations
  recovered.
- A position-only freshness failure need not erase independently available
  network fields. Per-field availability is applied during complete preparation.

There are two different publication policies in
[`frames.py`](../../backend/starlink-location/app/core/metrics/frames.py):

- **Pending/failed:** the coupled collector masks all existing coupled samples
  except the retained successful-update timestamp. That includes planned values
  whose applicability to the changed inputs has not yet been revalidated.
  Readers still capture exactly one immutable head. No old frame is advertised
  as a current finite generation.
- **Ready but no observation:** only observation-dependent/otherwise unknown
  fields are unavailable. Current phase, source-mode information, route
  metadata, scheduled times, and calculable preflight estimates are prepared
  normally. In the captured first activation, phase and mode were finite and the
  active untimed-route flag was correctly zero despite all 11 observation values
  being NaN. Its ETA/distance values were unknown. Existing
  timed-route/preflight tests cover available planned values and the 150-knot
  estimate without fabricating observed position or speed.

Independent standard gauges, counters, histograms, mission planning instruments,
and GEP instruments do not participate in this mask; their own producer and
explicit disconnect contracts still apply. Their values are not required to
share the coupled frame generation. The retained update timestamp stayed fixed
through the deliberate disconnect/failure; ordinary independent counters
remained collectable. This distinction preserves the approved ownership
boundaries.

## Prometheus, history API, and Overview

Prometheus retained ordinary NaN samples. The reproduction's stored range vector
has eight common NaN sample timestamps across all 11 series: activation,
configuration reset, three disconnect samples, and three preparation-failure
samples. Additional per-field NaNs during replay/speed recovery are recorded
separately. A source comment saying Prometheus will not store NaN is inaccurate;
ordinary explicit NaNs must not be confused with stale-series markers.

The history API intentionally projects **finite samples only** in
[`overview_history_prometheus.py`](../../backend/starlink-location/app/services/overview_history_prometheus.py).
It preserves each remaining timestamp; it does not compact or shift the time
axis, replace NaN with zero, or fill from an old observation. Its rolling
statistics are also withheld at evaluation steps without a finite raw point. The
original exact capture confirms that the missing API point corresponds to a raw
NaN at the same evaluation coordinate. All seven history implementation files
are byte-identical to the frozen original application.

Omitting that timestamp is therefore expected existing filtering, not a new API
projection regression. The newly visible unavailable source interval is an
observable behavior change and must be measured, even though the API behavior is
unchanged. The Overview projector explicitly inserts chart gap markers and
avoids drawing a continuous line across missing intervals. Its existing tests
passed unchanged.

A finite query grid alone never proved 1 Hz acquisition: Prometheus lookback can
reuse a prior value at successive evaluation steps. Availability-aware
validation must therefore preserve the scrape/source freshness checks as well as
the grid.

## Proposed narrow acceptance rule — not implemented

Retain the strict original harness and every rejected/partial run. Create a
separately versioned harness only after approval. Do not merely replace the
length assertion with a percentage check.

1. **Exact expected grid and projection:** keep window, inclusive bounds,
   `step_seconds=1`, the expected 11 metric names, ordering, uniqueness, and
   aligned timestamps. Reconstruct an analysis-only 1,801-slot grid. Each API
   point must match the finite raw Prometheus evaluation at its exact timestamp;
   each omitted point must be explained by an explicit raw NaN and a permitted
   source/event interval. Missing raw samples, arbitrary holes, infinities,
   duplicate/ambiguous identities, or shifted timestamps fail. Never return this
   reconstructed grid as application telemetry or fill it with finite values.
2. **One bounded setup exception:** for steady synthetic controls/soaks, allow
   at most three unavailable 1-second evaluation slots per series attributable
   to the single recorded initial activation. Require usable telemetry recovery
   within **2 seconds of successful activation completion**, with the actual
   unavailable scrape interval bounded and recorded. Require at least **99.8%
   finite coverage** of each 30-minute window; 3 missing of 1,801 is 99.833%.
   These proposed caps are reviewable policy, not existing documented SLOs.
3. **Strict measured steady state:** the setup exception may explain old points
   still inside a rolling 30-minute history window. It may not excuse any new
   unavailable sample during the 180-second control or minimum 60-minute steady
   soak. The existing 120-second warmup, measured durations, workloads, latency,
   resource sampling, and comparison guards stay unchanged. A spontaneous
   pending/failed publication, source loss, stalled refresh, HTTP error, or new
   unexplained NaN fails steady acceptance.
4. **Cadence and provenance:** independently verify actual Prometheus target
   scrape timestamps/up at 1 Hz and the existing polling-gap limits; a finite
   resampled grid is insufficient. Record `/api/status` metric source and
   acquisition times, `/api/simulation/run` runtime/run/revision/mission clocks,
   mode and retained update timestamp around each controlled event. Do not treat
   that metric's publication timestamp as the acquisition timestamp. Ready alone
   is insufficient. Dedicated diagnostic tests continue to assert frame
   identity, atomicity, rejected-source behavior, no clock renewal, and counter
   semantics.
5. **Separate transition workloads:** retain per-field availability
   expectations. Replay may legitimately lack network measurements; initial
   recovered speed may require two positions. Deliberate disconnection or
   injected failure must have a predeclared event interval, truthful
   NaNs/health, fixed old acquisition times, and a bounded recovery deadline
   after the source/fault is restored. Such intervals are reported separately,
   never whitelisted into steady-state controls. For mission/configuration
   activity, require the same 2-second recovery and at most three affected grid
   slots per declared event; report total unavailable time and a predefined
   total event budget. Do not adopt a global permissive missing-data percentage
   for uncontrolled source loss.
6. **Versioned comparisons:** archive original and revised harness SHA/source
   hashes, exception policy, event/availability evidence, and observer settings.
   Use identical revised instrumentation and workload for original/current-dev/
   candidate controls, at least three matched repetitions per cohort. Keep
   instrumentation off and counters separate. Do not compare old-harness and
   revised-harness measurements as equivalent or reuse old accepted controls as
   the revised cohort. Any availability observer adds overhead and must be
   identical in all roles; retain and report that overhead explicitly.

Before adopting the new validator, its tests must reject wrong grids,
unexplained single holes, long/all-NaN windows, missing raw data, stale lookback
reuse, mode or run mismatch, expired recovery deadlines, excessive exceptions,
and gap/finite API disagreement. They must accept exactly the approved bounded
setup event, while preserving the gap and its provenance in evidence. Original
strict tests remain runnable and continue to reject that same fixture.

The activity workload's total budget and per-field replay/recovery deadlines
need explicit agreement before changing those separate acceptance rules; they
are not needed to approve the narrowly bounded initial-activation exception.

## Alternatives and recommendation

Recommend the separate, availability-aware harness with the bounded setup rule
above. It validates honest unavailability and retains meaningful steady-state
failure detection. No production change is currently justified by this evidence.

Retaining strict finite history and waiting at least 30 minutes for every setup
gap to age out would avoid this validator conflict, but materially changes the
workload startup/measurement schedule, delays every control, and does not test
the permitted behavior. It would also require explicit versioning and fresh
matched controls. Making activation wait for a usable source observation would
change the application API/lifecycle contract, could block indefinitely on a
real disconnected source, and requires separate design approval. Filling gaps or
presenting stale observations as current is rejected.

The narrow validator/probe change can be isolated to acceptance tooling. It does
not require new publication architecture, changes to metric schemas, a periodic
worker, #392 caching, or #393 label cleanup. Independent regression/static,
rollback image qualification, evidence reduction, and report work can proceed
separately after review without waiting for revised performance results. A
60-minute steady soak still depends on resolving its finite-history validator;
none is claimed complete. Current CPU evidence also has **not established a net
backend improvement**; resolving availability validation does not waive that
gate.

## Verification and evidence

- 91 existing backend tests passed in 2.40 s under a three-minute wall limit:
  history projection, immutable frames, lifecycle sources/expiry, replay, reload
  failure recovery, and concurrency.
- 50 existing frontend history/chart tests passed in 1.14 s under a two-minute
  wall limit. No assertions were relaxed.
- 2,525 original and Tasks 1–5 evidence files reverified: zero mismatches.
- Diagnostic runtime completed, with containers, network, private volumes, child
  processes, temporary source paths/images, and published ports cleaned. Final
  host verification is retained separately.

All evidence is under
`.superpowers/sdd/2026-10-21-perf-391-metrics-publication-    tasks/evidence/task6/`:
`cold-history-exact-analysis.json`, `availability-review-analysis.json`,
`availability-timeline-r1/*-trace.json`, `*-raw-samples.json`, `*-history.json`,
`result.json`, command logs and ownership journal; the interrupted-control
sidecar; focused test owner/log files; and
`availability-review-baseline-verification.json`. The initial offline reducer's
over-broad assumption that all per-field NaN sets matched across replay/recovery
was rejected and retained in `availability-analysis-parser-diagnostic.json`;
common whole-source gaps and legitimate per-field gaps are reported separately.

**Stop for review.** Application remains at `aa05a00a`; original harness and
baseline are unchanged. PR #403 remains draft/unmerged; #391 and #390 remain
open.
