# Independent investigation of PR #403 / #391

Investigation date: 2026-10-22. Reviewed starting commit
`e1f657986f7b988a967ddd2bef8ca4626e30b5de`; its application tree matches the
measured candidate `aa05a00a`. **Recommendation: retain NO-GO.** Neither the
cadence gate nor the net CPU improvement gate is satisfied. This investigation
changes documentation and disposable diagnostic tools only. Corrective
implementation requires approval. No new soak, deployment, merge, or issue
closure was performed.

## Evidence and independence

Read #389, #390, #391, #392 and #398; PR #403 and its review comments; the
architecture decision, specification, ownership contract and six-task plan; Task
6's report, review, results and retained raw evidence. The written design's old
“awaiting approval” wording is superseded by the actual
[approval at c7792320](https://github.com/bcl1713/starlink-dashboard/pull/403#issuecomment-6305273526)
and subsequent task approvals. Its selected boundary remains one immutable
29-family gauge frame plus position alias, standard independent instruments, and
the existing registry/serializer. No global registry transaction or byte cache
is approved.

The investigation worktree was created on a new branch from `origin/dev`
(`33b60fa8`) and advanced to the requested starting commit for inspection and
execution. The submitted documentation branch contains only investigation
artifacts relative to `dev`; PR #403's application changes remain in #403.

Independent checks performed:

- Streamed and verified **all 5,385 files / 7,623,254,994 bytes** in the final
  Task 6 raw manifest: zero missing files or hash mismatches.
- Recomputed the three sustained-run capture-gap distributions directly from
  JSONL, inspected the surrounding acquisition/publication identities, Nginx
  logs, resource samples and host records, and read all nine retained v2
  original/dev/candidate tick and scrape profiles.
- Ran two bounded component measurement passes and a final script rerun, using
  real candidate functions, private stores and 0/2/10/100/1,100 POIs. The first
  pass omitted the 2-POI case.
- Ran a **36-second** HTTP timing experiment and final script rerun using the
  unchanged v2 monitor, actual source/frame capture, candidate producer loop and
  admission gate. Deliberate stalls tested the diagnostic's ability to
  distinguish mechanisms. This was not an acceptance run or a reproduction of
  the historical cause.

The frozen strict harness (`13cbf1d5`) and v2 harness (`f3029024`) were neither
edited nor rerun as acceptance. Their worktrees have no tracked modifications.
Original and failed candidate evidence remains unchanged. The 1.5-second bound
is unchanged.

[Compact measurements and input hashes](probes/perf391-independent-results.json)
accompany this report. Full diagnostic traces, profiles, ownership records and
the GitHub context snapshot are retained privately under
`.worktrees/perf391-independent/.superpowers/perf391-independent/`.

## Cadence: what the historical evidence establishes

These intervals are between **server capture timestamps**, not browser receipt
timestamps, Prometheus evaluation times, or exact source-acquisition counts.

| Measured run              | Capture intervals | p95 / p99, seconds | Maximum, seconds | Over 1.5 seconds |
| ------------------------- | ----------------: | -----------------: | ---------------: | ---------------: |
| Original                  |             3,660 |      1.101 / 1.151 |         1.336914 |                0 |
| Candidate, full           |             3,660 |      1.111 / 1.208 |         1.754899 |                1 |
| Candidate, stopped repeat |             1,653 |      1.109 / 1.193 |         1.583978 |                1 |

The original passed sustained acceptance. Both candidate failures remain
failures. The full candidate's raw Prometheus scrape interval maximum was 1.034
seconds, versus 1.020 seconds for original; the retained independent
scrape/history replays passed their subchecks. Regular scrapes can repeatedly
serialize the same source observation, so these passes do not establish regular
acquisition or satisfy source-observer coverage.

**First failure, 23:00:24.477549 UTC:**

| Capture UTC, seconds within minute | Published acquisition UTC, seconds within minute | Age, seconds | Capture body, ms |
| ---------------------------------- | -----------------------------------------------: | -----------: | ---------------: |
| 22.722650                          |                                        21.882152 |     0.840498 |            0.171 |
| 24.477549                          |                                        22.889998 |     1.587551 |            0.560 |
| 24.738082                          |                                        24.580470 |     0.157612 |            0.182 |

There is a capture delay followed by a short 0.261-second catch-up interval. The
delayed capture also finds a genuinely older **published observation**; this is
more than a late delivery of an otherwise fresh response. The next sampled
published acquisition timestamp jumps 1.690472 seconds. However, the adapter
reads the candidate's frame identity, not an independent acquisition stream. It
cannot determine whether acquisition itself paused, whether an acquired sample
waited for publication, or whether intermediate observations were missed. Do not
call this proof of a physical telemetry outage or a precise 1.690472-second
acquisition gap.

Both bracketing frames are ready, with matching source/route bindings and
unchanged input revision. That establishes state at those captures only. Nearby
browser resource batches include a 972.8-ms history request, 803.5-ms status
request and 518.8-ms Operator context request. Their exact overlap with the gap
is not recorded. Their breadth supports investigating shared
scheduling/queueing; it does not identify the responsible route.

**Repeat, 23:49:37.413576 UTC:** capture age is 1.028525 seconds, body time
0.187 ms, and the next capture follows 0.413 seconds later. Nearby sampled
acquisition increments are 1.007404 and 1.046962 seconds. Unlike the first
failure, this window does not demonstrate a comparably large published
acquisition increment. It is compatible with a delayed observer while the
producer continues. Nearby history and Operator context batch maxima are 921.9
and 617.8 ms. They cannot establish the observer's HTTP duration.

Across the measured full runs, maximum observed acquisition age is 1.198 seconds
for original and 1.588 seconds for candidate; the repeat maximum is 1.456
seconds. Sampled distinct-acquisition counts are 3,503, 3,540 and 1,610. These
are sampled counts. In particular, approximately two-second jumps between
sampled timestamps occur even in original and can arise from missed samples;
they are not automatically two-second source stalls.

## Scheduling, HTTP, admission and host attribution

The v2 monitor has an absolute one-second schedule (`next += 1000`), serialized
reads and a one-second request deadline. It records neither scheduled wake time,
actual send time, response arrival nor observer event-loop lag. A request can
complete inside its deadline yet the interval between captures exceeds 1.5
seconds: the previous capture may have been prompt and the current one delayed
by more than 500 ms. A late prior response can also delay the next serialized
request. Synchronous JSONL writes share the Node observer's event loop with
browser/resource sampling. Their durations are unmeasured in the failed runs.

The source-state endpoint is a synchronous FastAPI route. Its path includes
Nginx, ASGI scheduling, AnyIO worker admission, the repository gate, capture,
response conversion/serialization and network delivery. The recorded
`capture_wall_ms` starts **after** acquiring the repository gate and ends before
HTTP response serialization. The sub-millisecond bodies at the failures exclude
all those other waits. They do rule out expensive work _inside the capture body
at those particular points_ as the 0.6–0.75-second cause.

The producer runs in `asyncio.to_thread`. It captures source bindings under
admission, collects, then prepares and revalidates the frame while holding the
repository gate. Simulation `update()` also takes that gate. Frame preparation
therefore competes with the observer and model readers/writers through
repository admission, even though Prometheus frame reads do not. The fair local
queue prevents overtaking; it does not bound a holder's work or accumulated
wait. Cross-process file locking is another wait boundary.

For ordinary simulation, both original and candidate sleep for the configured
interval **after tick completion**. Thus actual start-to-start cadence is the
interval plus tick work, dispatch delay and wake delay. The candidate's added
producer work can increase this existing drift. Replay uses its runtime's
`seconds_until_next_tick()`; do not substitute a wall-clock policy for replay.
The lifecycle owner preserves a deadline across dirty wakes but a refresh that
runs past that deadline can still delay collection. No retained evidence proves
such a refresh caused either failure.

Host records bracket each worst capture at approximately 30-second resolution.
Busy CPU was 62.7% and 63.0% near the candidate failures; it was 63.4% near
original's worst capture. Candidate load averages were about 19 and 16 on a
20-logical-CPU host. I/O wait was approximately 0.2%, with zero recorded steal
time. This neither establishes nor rules out short host scheduling delays,
per-core contention, cgroup throttling, GIL contention or slow filesystem calls.
The frozen sampler discards Docker throttling counters and lacks scheduler/PSI
and per-thread runnable-time evidence. Average spare host CPU is insufficient to
exonerate scheduling; similar original load is insufficient to blame it.

### Controlled discrimination experiment

A private loopback Uvicorn server used the real gate/capture and candidate
producer, with the **unchanged v2 monitor** as its Node consumer. Three separate
800-ms stalls were deliberately introduced. No browser, Nginx, Prometheus,
physical dish or production lifespan was started.

| Injected boundary   | Capture gap, s | Observer send lateness, ms | HTTP duration, ms | Admission wait, ms | Capture body, ms |
| ------------------- | -------------: | -------------------------: | ----------------: | -----------------: | ---------------: |
| Repository gate     |          1.580 |                       0.27 |            582.80 |             580.77 |            0.108 |
| Backend event loop  |          1.581 |                       0.73 |            582.30 |               0.52 |            0.116 |
| Observer event loop |          1.600 |                     600.35 |              1.75 |               0.30 |            0.109 |

Backend event-loop delay appeared as 580.69 ms from send to ASGI arrival;
ASGI-to-worker dispatch took only 0.28 ms in that case. Gate contention also
delayed acquisition in this experiment: the maximum directly recorded source
timestamp increment was 1.565889 seconds. The observer-only stall left adjacent
source increments near 1.003 seconds. The initial nine undisturbed captures had
a maximum interval of 1.001138 seconds. No derived refresh ran during the
experiment despite attaching the real lifecycle owner.

This confirms that all three mechanisms can produce the historical signature of
a long capture interval, short catch-up and cheap capture body. It does **not**
select a historical cause. The added boundaries are necessary for that
selection. No natural recurrence was claimed from this short, unloaded run.

## CPU: confirmed added work and measured costs

The matched retained controls still show backend CPU effectively unchanged:
original 0.23424 cores, candidate 0.23473 cores; paired change +0.21%, with the
reported descriptive interval crossing zero. Counter timings show scrape
preparation 4.794 → 2.376 ms and producer ticks 2.898 → 5.760 ms. These are
different instrumentation/cohort measurements, not an additive CPU budget.
Moving work out of scraping established purity; it did not establish efficiency.

The retained cProfiles independently confirm structural differences on the
actual two-POI benchmark workload. Each file profiles one tick, so times are
examples, not distributions or uninstrumented CPU costs:

| Work per profiled tick                                     | Original | Candidate |
| ---------------------------------------------------------- | -------: | --------: |
| Recursive `deepcopy` invocations, including nested calls   |      105 |       805 |
| `get_active_leg_lock()` calls                              |        7 |        16 |
| Active-route reads, including ingestion-profile resolution |        2 |         6 |
| `source_is_current()` checks                               |        0 |         3 |
| `model_dump_json()` calls                                  |        0 |        17 |
| Complete frame builds / validation traversals              |    0 / 0 |     1 / 2 |

Candidate `FrameInputs` copying takes 1.04–1.82 ms inclusive in these three wall
profiles; all recursive copying takes 1.44–2.47 ms. The three
`source_is_current` checks together take 1.69–1.82 ms; JSON dumping takes
0.57–0.63 ms. These overlap and **must not be summed**. Active-route reads take
2.42–9.38 ms inclusive. One profile spends 33 ms in `mkdir`, illustrating why
wall profiles cannot be reported as CPU costs. Gate acquisition, canonical path
resolution, directory checks and route-profile resolution materially increase
call count and exposure to slow filesystem/scheduling events.

The producer computes POI ETA once per captured tick, with the calculator call
about 0.04–0.06 ms in these wall profiles. There is no evidence here of twice
running the full ETA algorithm or building two frames per accepted tick. The new
copies and source checks are a better explanation of the added work than ETA
arithmetic on this small route. Repeated derived refreshes outside those
profiled ticks remain unmeasured; the controlled trace observed zero.

### Copying, hashing and frame construction

`POIManager.list_pois()` returns deep copies. `FrameInputs.__post_init__`
deep-copies those POIs again, plus telemetry, config, route and status.
`eta_service._prepare_eta_metrics()` deep-copies the already detached POIs a
third time. The read-only derived branch additionally detaches calculator
smoothing/passage state; that state copy is required for its semantics and
should not be confused with redundant POI copying.

The main producer captures a configuration serialization and route-source hash,
then checks `source_is_current` before the updater, at updater entry and before
publication. Frame preparation also hashes telemetry, route, POIs and phase, and
post-preparation validation rechecks route, POIs and phase. In the retained
two-POI tick, the 17 model dumps comprise four config dumps, six route dumps,
one telemetry dump, four POI dumps and two phase dumps. The source-admission
checks protect real races; their duplication does not authorize deleting final
validation or relying only on local dirty revisions.

The frame path normalizes labels/values through views/builders and again while
freezing; `seal()` validates the frame and `publish()` validates it again.
Per-POI bound views also scan schema membership and per-set owner checks query
the current producer context. These are smaller targets than POI copying in the
large-POI measurement. The pointer swap is already small and remains the right
atomic-publication boundary.

Fresh component measurements below are **mean unprofiled thread CPU per call,
ms**, with 100 iterations at 0/2/10 POIs and 30 at 100/1,100. They use a simple
five-point untimed route and real private manager/gate state, without the
production route-profile resolver or service/browser load.

| Operation                                   | 2 POIs | 10 POIs | 100 POIs | 1,100 POIs |
| ------------------------------------------- | -----: | ------: | -------: | ---------: |
| Complete background tick                    |  2.730 |   3.306 |    9.652 |     88.594 |
| Manager POI copy, including its access gate |  0.284 |   0.416 |    1.958 |     18.859 |
| Complete `FrameInputs` copy                 |  0.292 |   0.326 |    1.814 |     19.076 |
| Additional ETA POI copy alone               |  0.036 |   0.165 |    1.653 |     18.706 |
| One POI identity hash, including JSON       |  0.008 |   0.034 |    0.325 |      3.601 |
| POI ETA calculation alone                   |  0.004 |   0.013 |    0.115 |      1.310 |
| Complete derived-frame preparation          |  0.297 |   0.565 |    3.534 |     36.939 |
| Immutable sample freeze alone               |  0.014 |   0.019 |    0.075 |      0.853 |
| One frame validation                        |  0.005 |   0.006 |    0.021 |      0.184 |
| Full registry scrape serialization          |  1.111 |   1.190 |    2.046 |     13.747 |

Operations overlap; this is not a sum-of-parts table. The first independent
component run measured 88.036 ms/tick and 18.551 ms for the extra ETA POI copy
at 1,100 POIs, supporting the scale of the result. The second run's full
distributions are retained, including the small-case variation. Instrumented
profile timings are kept separate; the first component profile used a thread
clock with substantial per-event overhead, and the second used default wall
profiling. Neither profile's absolute durations are used as CPU savings.

New diagnostics use Python 3.11.16 rather than retained Docker 3.11.17, and
FastAPI 0.158.1 rather than 0.156.8. Pydantic 2.14.1, filelock 4.2.4 and
prometheus-client 0.26.0 match. These figures identify costs; they do not
replace matched production-image comparisons. Live/replay CPU, long-route
scaling, loaded worker queues and physical hardware remain unmeasured here.

[Ranked remediation options and proposed corrective plan](perf-391-corrective-plan.md)
require approval before implementation.

## Validation and resource disposition

All diagnostic commands used external wall-clock limits and forced-termination
grace: retained verification/component runs 180 seconds + 5 seconds; HTTP timing
70 seconds + 5 seconds. The successful timing run stopped its producer and
lifecycle owner, drained workers, reaped Node, closed Uvicorn and its ephemeral
loopback listener. It reported zero duplicate derived refreshes; component runs
reported zero remaining threads. No Docker project, network or volume was
created. No test service is being left running.

The initial component attempt failed on missing required synthetic
`RouteMetadata` fields before measurement. The diagnostic fixture was corrected;
application code was untouched. Its incidental Matplotlib temporary cache and
all private diagnostic stores/environments are removed after preserving
evidence. Script syntax, report formatting/links, the documentation-only diff,
frozen-source identities and host resource cleanup are checked before handoff.
No fresh full backend suite or production acceptance pass is claimed.
