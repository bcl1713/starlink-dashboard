# First diagnostic phase for 391

**Historical failure not reproduced; retain NO-GO.** Sixteen short matched runs
produced no natural source-capture interval over 1.5 seconds. The largest was
1.254532 seconds. These diagnostics establish scheduling and admission tails,
not the cause of the historical 1.754899/1.583978-second failures. No producer
optimization, acceptance-policy change, sustained qualification, merge or
deployment was performed.

This implements the diagnostic prerequisite in the
[approved corrective plan](perf-391-corrective-plan.md), following investigation
`6d4098b0`.
[Results, distributions, request joins and evidence hashes](probes/perf391-diagnostic-results.json)
and the
[opt-in tool and reproduction instructions](../../tools/diagnostics/perf391/README.md)
accompany this report. Full raw events, input snapshots, rejected attempts and
ownership records remain under `.superpowers/diag391/` in the retained
`perf391-diagnostics` worktree; the tracked results contain their path/hash
manifest.

## Mechanism and controls

The separate synthetic wrapper records planned/actual observer wake, fetch
invocation, Undici wire send, headers/body receipt, ASGI arrival/response,
worker dispatch/service/completion delivery, repository wait and nested hold,
producer dispatch/start/end, collection return, detached inputs, source
validation and frame preparation/publication. Backend identities are hashed;
telemetry values, mission payloads, query strings and exception messages are
excluded. Records are buffered, capped at 200,000 backend events, and written on
graceful shutdown.

Each process uses its own monotonic clock. `diag-N` joins requests across the
observer/backend boundary. Only process-local durations are compared: HTTP RTT
minus ASGI duration is a combined proxy/transport/client residual, not a one-way
network or pre-ASGI queue measurement. Async dispatch spans do not attribute CPU
accumulated by unrelated event-loop work to the worker.

The frozen `availability-v2` harness at `f3029024`, its adapter and limits are
unchanged; both frozen harness worktrees remain clean. This separate probe uses
an absolute 1 Hz monotonic schedule, serialized requests and a one-second
request deadline. It does not execute the frozen acceptance validator or claim
acceptance. The original application is `25e34168`; candidate `e1f65798` retains
the measured `aa05a00a` application bytes.

Two separate repetitions per application/workload/mode used production images,
Nginx, real 1 Hz Prometheus, the same fictional fixture and 30-minute history.
Each run had five seconds warmup and 30 seconds requested measurement. Workloads
were unloaded or two real Overview contexts plus Operator at 1920×1080. Loaded
runs verified visible roots, recurring successful per-page history/status and
Operator health traffic. All had zero browser/network/HTTP errors. Application
order reversed in repetition two; off/trace modes were separate. All sixteen
runs had identical diagnostic input snapshots and backend package inventories;
Python was 3.11.17. No trace events were dropped. All 496 source reads
succeeded, covering 480 monotonic capture intervals.

## Natural timing and attribution

Maxima below combine the two repetitions in each cell. Different columns can
refer to different requests and must not be added.

| Application and workload | Off capture gap s | Trace capture gap s | Traced observer admission ms | Traced producer tick ms |
| ------------------------ | ----------------: | ------------------: | ---------------------------: | ----------------------: |
| Original unloaded        |             1.081 |               1.065 |                        0.405 |                    82.5 |
| Candidate unloaded       |             1.020 |               1.092 |                        1.089 |                    26.5 |
| Original loaded          |             1.211 |               1.231 |                       51.652 |                    74.8 |
| Candidate loaded         |             1.255 |               1.175 |                      122.955 |                   190.1 |

**Confirmed tail bottlenecks are scheduling/completion delivery and repository
admission.** The slowest traced candidate observer request, loaded repetition
one `diag-8`, took 314.540 ms end to end. Its backend ASGI duration was 206.871
ms: worker queue 1.354 ms, synchronous service 0.804 ms, and post-service
completion delivery/resumption 202.938 ms. Within service, admission was 0.282
ms and source capture 0.170 ms. The remaining 107.669 ms is unallocated
HTTP/client/proxy time. This demonstrates a delayed backend completion without
expensive capture work in that request; it does not identify the responsible
competing operation.

Across candidate loaded runs, separate requests reached 149.059 ms worker queue
wait and 122.955 ms observer repository wait. Outer producer holds reached
67.841 ms; other request/refresh holds reached 161.047 ms. The trace identifies
operation/thread ownership, but does not label every unrelated route or split
local FIFO versus cross-process file-lock admission.

Candidate unloaded producer tick median/p95 was 4.606/7.531 ms, collection
0.479/0.747 ms, complete preparation 1.622/2.334 ms and publication 0.018/0.025
ms. Loaded tick median/p95 was 8.179/49.491 ms; same-thread tick CPU p95 was
9.179–9.911 ms across repetitions. Elapsed tails include substantial
waiting/descheduling rather than an equivalent amount of producer CPU. Frame
publication itself remained below 0.063 ms. Nested preparation/validation
measurements overlap and cannot be summed into savings.

Backend heartbeat lateness reached 208.976 ms on original and 193.102 ms on
candidate; observer heartbeat lateness reached 252.081/247.046 ms. Actual
candidate observer scheduled-wake lateness peaked at 9.511 ms, fetch-to-wire at
1.695 ms and headers-to-body at 4.563 ms. Heartbeat stalls therefore do not
necessarily coincide with a scheduled source read. Collection-return intervals
peaked at 1.263 seconds on candidate; returned timestamp tokens were retained,
but collection can return retained telemetry, so this is not a physical
acquisition census.

Per-thread one-second scheduler-wait increments reached 410.443 ms. Every traced
run recorded cgroup throttling: 44–56 throttled periods in its approximately
28–30-second backend analysis window. The actor daemon uses cgroup v2/systemd; a
representative lifecycle container confirmed a private cgroup and the requested
two-CPU limit. Counters cover the whole backend container, including its child
processes. They do not identify which child consumed the CPU or prove that a
particular quota event caused a particular stall. Throttled microseconds and
overlapping thread waits are not additive wall time. These current pressure
observations cannot be assigned retrospectively to the historical failures.

## Attribution validation and cleanup

An isolated loaded control injected eleven explicitly marked 700 ms delays. All
eleven boundary assertions passed: dispatch 700.273 ms, worker execution 700.133
ms, admission 705.392 ms, collection 790.573 ms, frame preparation 701.142 ms,
source validation 703.756 ms, publication 700.333 ms and response stage 700.282
ms. A real 700.201 ms repository holder caused other admissions to wait up to
593.459 ms. Backend loop lateness was 672.545 ms; an observer-only stall delayed
send by 700.092 ms and its heartbeat by 693.242 ms. Artificial failures remain
separate from natural distributions. A separate installed-Node regression
verifies wire-send correlation against its actual Undici event.

Real browser/Compose cases exercised an exception after setup, SIGTERM
cancellation and a 15-second owned command timeout, including forced termination
of the timed-out Node group. All browser groups and backend workers were
closed/drained, processes reaped, and private containers/networks/volumes,
listeners and image tags removed. Final host verification checked 23 distinct
task projects: zero owned processes, zombies, listeners, image tags or Docker
resources remained. Open-PR worktrees and evidence remain; no service is left
up.

Retained exclusions include the first observer-output ReferenceError, a config
token startup failure on `SimpleNamespace`, two preliminary matrices stopped for
review/wire-header corrections, two sandbox unit-test timeouts, early injected
controls and a late CPU-detail read after its container was already removed.
Their available traces, logs, timing distributions and cleanup records are
preserved. None was substituted into the final cohort. The metadata defects have
regression tests. The independent review's async-CPU, browser-workload and
unsupported-option findings were corrected; unsupported transitions/fullscreen
options were removed. Postcollection analysis also distinguishes deliberately
disabled backend tracing from a failed observer request.

## Instrumentation overhead and limits

Whole backend-container CPU changes for trace versus the matched off control
were:

| Workload | Original repetitions | Candidate repetitions |
| -------- | -------------------: | --------------------: |
| Unloaded |       +0.70%, +1.30% |        +1.43%, +5.06% |
| Loaded   |       +1.60%, −0.40% |        +0.50%, +0.80% |

Two short pairs do not isolate instrumentation cost from warmup, scheduling and
container-child variability; retain the negative result and the +5.06% outlier.
No estimated overhead is subtracted to claim application CPU savings. A separate
same-container Python calibration measured median CPU of approximately 1.03 µs
per enabled event and 5.32 µs per enabled span, versus 0.087/0.768 µs disabled.
It includes clocks/locking/buffering, but excludes application metadata hashing
and periodic host sampling. Observer process CPU, including HTTP and browser
control, was 144–152 ms per unloaded traced run and 1.013–1.119 seconds loaded;
this is a total probe/control budget, not isolated recorder overhead.

These are short, synthetic, software-rendered diagnostics with a five-second
warmup on a shared host. Live hardware, replay transitions, long-run growth,
ancestor cgroup effects and sustained acceptance remain unqualified. Sampling
cannot assign every off-CPU interval to I/O, runnable contention or quota. The
largest natural capture interval occurred in an off control, where detailed
backend attribution was intentionally disabled. A short absence of failure does
not change #403's NO-GO verdict.

## First optimization for review

Implement corrective-plan rank 1 first: **consolidate repeated source capture
and admission within one producer operation, retaining final authoritative
revalidation and stale-source rejection**. The small-fixture candidate spends
measurable CPU on repeated input capture/identity/admission, while frame commit
is already very short. Keep the proposed owned POI snapshot as the next scaling
target. This is a bounded CPU-efficiency recommendation supported by the prior
profiles and these timings, not a demonstrated fix for either historical cadence
failure. Scheduling/completion and quota pressure need separate causal follow-up
before selecting a cadence or admission architecture change.

Validation: 14 Python tests and four Node tests passed, including cross-clock
attribution and the installed Undici wire event. Python/Markdown formatting and
lint, filename conventions, internal links and diff checks passed.
