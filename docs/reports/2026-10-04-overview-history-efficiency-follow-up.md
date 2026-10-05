# Overview history efficiency follow up

Issue 224's incremental reader and chart memoization were already delivered in
PR 228. This work amends their existing spec and measures the remaining HTTP,
browser and sustained resource costs. Both one- and two-viewer one-hour runs
qualify the one-second cadence. The default promotion is tracked separately
below.

## Measurement environment

The current Forge executor uses an Intel Core i9-10900K, 20 logical CPUs and
65,915,523,072 bytes of host memory. Its actor-owned rootless Docker daemon is
29.8.1 with overlayfs; the configured socket/context are preserved. Native
Chromium 153.0.8010.12 is checked against its provisioned descriptor. The
viewport is 1920 by 1080, DPR 1; WebGL reports ANGLE Vulkan SwiftShader. This is
software rendering evidence, with no physical-GPU claim.

The isolated `starlink-224-history` project builds production backend/frontend
Dockerfiles and uses production Nginx and Prometheus configuration. Instrumented
backend controls replace only the history reader/entrypoint. Ports
18224/15224/19224 and all named volumes belong to this task. The full-range
control uses the existing fixed-grid query function without completed-result
reuse; it is a computation control with the current frontend, rather than the
historical pre-cache UI/build.

A deterministic OpenMetrics seed contains 4,201 one-second observations for each
of 11 raw metrics, with the production `job` and `instance` labels. Public
simulation supplies current scrapes. The 30-minute cold bundle contains 46,826
points across 11 raw and 15 aggregate traces. These are synthetic historical and
simulation observations. Query evaluation counts are requested points, not a
measurement of Prometheus's internal rolling-window work.

Request timing runs through real Nginx, FastAPI and Prometheus; healthy history
responses are never browser-intercepted. Backend/Prometheus CPU uses cumulative
container CPU seconds divided by measured wall seconds. The budget uses
percentage points of **one core**; host normalization divides by 20 and is
reported separately. Browser heap uses CDP `Runtime.getHeapUsage.usedSize` and
sums actual viewer pages. Ordinary and retained post-GC samples are separate. GC
occurs after warm-up, at five-minute intervals and at the measured endpoint;
those interruptions are outside undisturbed frame-continuity claims.

## Pre-change attribution

Real Prometheus replay at candidate `bb0d5d4f` covered 300/900/1800/3600/3601
second windows at identical historical endpoints, for full-range 5s, incremental
5s and incremental 1s. All 15 cases passed the populated-history guards. A
30-minute one-second advance requests 312 evaluation points rather than 46,826
full-window points. A second sequential same-interval incremental reader adds
zero queries; cancellation and concurrent-reader controls pass.

An opt-in HTTP cProfile at `9ca21619` recorded 0.380 seconds, including 0.351
seconds in FastAPI's recursive `jsonable_encoder` conversion. The bundle already
contains JSON primitives. This is attribution under profiler overhead, rather
than an uninstrumented latency distribution. The separate replay's ordinary JSON
encoding diagnostic was about 21 ms per 30-minute update. Neither diagnostic
supports a strict one-Hz request-start promise.

The original full-range 5s diagnostic at exact candidate
`2bd5c7e083ec4a7cc7a58a15c8e77df27f54aa85` recorded 108 healthy history requests
and no HTTP errors. Its resource interval was at most 5.123 seconds; measured
duration was 599.99955 seconds after 300 seconds of warm-up:

| Observation                            |              Diagnostic result |
| -------------------------------------- | -----------------------------: |
| Warm request p50 / p95 / p99           | 549.914 / 674.316 / 742.875 ms |
| Actual request-start spacing p50 / p95 |                5.550 / 5.670 s |
| Backend + Prometheus CPU               |            13.126% of one core |
| Host-normalized combined CPU           |                         0.656% |
| Backend RSS endpoint growth            |                      0.129 MiB |

This phase is **not release qualification**. Three pre-warm-up simulation
GPS/cancellation logs were misclassified as unexpected control errors, one
separate curl diagnostic added a read, and the resource endpoint was 0.45 ms
short of the requested deadline. Its retained-heap result lacks a final GC
sample and is not a sustained-memory result. The failed artifacts are preserved.
The corrected harness scopes fixture-declared errors to their controls and
requires a final GC sample at or beyond the deadline. An invalid baseline cannot
pass the CPU comparison gate.

## HTTP response change

The history reader already publishes an immutable bundle of JSON primitives.
Returning it as a `JSONResponse` skips FastAPI's redundant generic recursive
conversion while retaining the full bundle and normal JSON rendering. A real
ASGI regression first failed on the old endpoint's duplicate conversion, then
passed with byte-identical compact JSON, the same media type, no mutation of the
shared snapshot and zero generic-conversion calls. Cache/coalescing, scheduling,
source authority and statistics remain unchanged.

A separate after-change profile at `e688f7e6` records 1,429 calls and 0.03343
profiled seconds, with zero generic-encoder calls. Its production app tree is
identical to frozen candidate `ae8397bf692a6ad0aad839ce3eb0d0745079f26f`. The
earlier diagnostic recorded 1,407,104 calls and 0.380 seconds, including 140,563
generic-encoder calls. Both are separate attribution diagnostics; the healthy
production-path distributions below establish acceptance latency.

## Controlled comparisons

Candidate `ae8397bf692a6ad0aad839ce3eb0d0745079f26f` uses the same host,
30-minute populated history, native renderer, viewport and one viewer. Each
finished phase follows 300 seconds of warm-up and measures at least 600 seconds.
Both finished phases have zero HTTP/browser errors and passed owned cleanup.

| Phase          |   Warm p50 / p95 / p99 (ms) | Combined CPU (% one core) | Requested evaluation points |
| -------------- | --------------------------: | ------------------------: | --------------------------: |
| Full-range 5s  | 325.795 / 400.620 / 424.211 |                     9.375 |                   5,291,338 |
| Incremental 5s | 165.942 / 206.583 / 413.530 |                     5.538 |                     141,596 |

The incremental phase includes two full reconciliations in its overall warm
quantiles. Requests overlapping full-window query completion have p95 458.405
ms; ordinary/completed-result requests have p95 197.803 ms. This classification
uses observed query spans within request intervals and includes shared readers;
it does not infer a new scheduler state. Healthy upstream counts use completion
monotonic timestamps between measured resource endpoints, excluding warm-up and
controlled outages. Whole-run traces preserve those controls separately.

Actual five-second request-start spacing has p50/p95 5.324/5.398 seconds for
full-range and 5.165/5.205 seconds for incremental polling. Configured delay is
separate from response time and source acquisition cadence. The short phases
correctly remain incomplete for sustained-memory acceptance.

## Native behavior controls

The real-path controls cover both cadences, one/two native viewer windows, all
five history windows and transitions in both directions. They observe accepted
bundle windows and the displayed selected-window label. Native fullscreen,
resize, real background-tab visibility/polling, resume, app-link remount and
stationary axes with a moving chart surface are checked. Bounded native JPEG
frames encode to WebM with the pinned VP8 encoder; browser CPU profiling and
recording end before warm-up.

A task-owned Prometheus outage verifies 503, retained last-good plots and
recovery. Expected fault logs are recorded separately; unexpected browser
exceptions and healthy-phase HTTP/console errors fail the phase. Per-page
request counts and maximum overlap check shared subscriptions rather than
extrapolating from backend coalescing. Canvas clears are redraw observations,
not an exact uPlot `setData` count; the existing component controls verify that
clock-only updates do not reproject or upload data.

A full-document navigation control crashed native Chromium with a seccomp
failure in syscall `0x25`. The required component remount subsequently uses the
app's actual navigation links, retaining the native sandbox. Repeated full-page
reload is not covered by this run. The earlier PR 228 recording/RSS exceptions
have not been inherited.

## One-viewer sustained result

At frozen product candidate `ae8397bf692a6ad0aad839ce3eb0d0745079f26f`,
incremental 1s polling completed 3,600.040932 measured seconds after 300 seconds
of warm-up: 3,137 requests and zero HTTP/browser errors. Warm p50/p95/p99 are
148.122/169.093/208.510 ms. Combined CPU is 13.399% of one core, an increase of
4.025 percentage points over the qualified one-viewer full-range 5s baseline.
Backend RSS growth is 1.055 MiB and retained browser heap growth is 4.340 MiB.
The last 1,193.406 seconds have retained-heap range 3.517 MiB and slope -4,890
bytes/minute. Actual request-start p50/p95/p99 are 1.147/1.168/1.208 seconds.

Twelve requests overlap full-range reconciliation query completion; their p95 is
362.743 ms and they remain included in the overall warm distribution. The probe
observes one parse per history response, average parse time 6.417 ms, and five
plot canvas clears per accepted bundle across 45,622 frame observations. This
corroborates the deterministic clock-only processing controls; canvas clears
remain an observation rather than an exact uPlot upload counter.

The initial post-down port check failed on a closed connection's TCP TIME_WAIT.
Docker had removed owned containers/volumes and native browser cleanup passed. A
separate checked Docker inventory, `ss` live-listener inventory and reusable
bind audit confirmed all resources/listeners absent. Its checksum is cited by
the derived summary; the original failed metadata/logs remain unchanged.
Functional preflight/post-down regressions reproduce the false failure and pass
after `SO_REUSEADDR`, while occupied live listeners remain rejected. This is
actual later cleanup verification; no performance budget is waived.

All seventeen one-viewer gates pass with that explicit cleanup receipt. The
two-viewer baseline's first native attempt crashed during the pre-warm-up
hidden-tab control: Chromium reported a CFI SIGILL followed by seccomp failure
0x25. It has no acceptance measurements; cleanup passed. A fresh retry at the
same candidate passed every native control and the 600-second baseline. The
subsequent two-viewer hour also passed, without browser security or rendering
flag changes. The failed attempt remains preserved and unqualified.

## Two-viewer sustained result

Acceptance-tool candidate `a3ac77357bfd599eeb413b9ecb6d7a4e73d48346` changes
only the post-down/preflight TIME_WAIT audit and its regressions. The entire
backend and frontend trees are identical to `ae8397bf`; both two-viewer phases
use the same new tooling candidate, host, history, renderer and native controls.

| Observation                         |      Full-range 5s baseline |    Incremental 1s sustained |
| ----------------------------------- | --------------------------: | --------------------------: |
| Measured seconds after 300s warm-up |                     600.009 |                   3,600.008 |
| Healthy requests / errors           |                     226 / 0 |                   6,274 / 0 |
| Warm p50 / p95 / p99 (ms)           | 301.278 / 326.474 / 337.256 | 148.823 / 192.098 / 221.088 |
| Request-start p50 / p95 / p99 (s)   |       5.300 / 5.324 / 5.335 |       1.147 / 1.191 / 1.221 |
| Combined CPU (% one core)           |                      15.169 |                      18.977 |
| Host-normalized combined CPU (%)    |                       0.758 |                       0.949 |
| Requested evaluation points         |                  10,582,676 |                   1,648,712 |
| Backend RSS endpoint growth (MiB)   |          6.738 (short only) |                       1.578 |
| Retained heap endpoint growth (MiB) |         -2.497 (short only) |                      -3.202 |

The sustained CPU increase is 3.809 percentage points of one core. Its 715
resource samples have maximum gap 5.556 seconds. The last 1,175.744 seconds of
post-GC samples have range 4.817 MiB and slope -200,842 bytes/minute. Twelve
full reconciliations are included; 24 overlapping requests have p95 431.690 ms
and the other 6,250 requests have p95 189.993 ms. Native browser and owned
project/listener cleanup passed immediately. All seventeen gates pass.

Each actual viewer records 3,136 parse completions, mean parse time 6.497/6.444
ms, and 15,680 plot clears. The endpoint counter boundary explains the
difference from 6,274 request completions. The two pages record 20,444/20,468
frame callbacks across the hour. These software-rendered native observations
include GC and are not a 60-fps continuity claim. Retained JS heap is separate
from browser process RSS, GPU allocations and external memory; these results do
not resolve issue 211.

## Qualification status and reproducibility

Both one-second sustained phases pass warm p95 <500 ms, combined CPU increase
<=10 percentage points of one core over their matching qualified full-5s
baseline, and backend RSS/retained browser heap growth <=16 MiB over >=3,600
measured seconds after warm-up. Both include scheduled full loads, deterministic
source/clock/restart controls, native lifecycle controls and checked cleanup.
Short comparison phases remain incomplete for sustained-memory acceptance;
failed native or earlier diagnostic phases are never substituted as baselines.
No earlier operator waiver is inherited. Load/order did not change the budget
conclusions, so no reverse-order repeat was needed.

The post-change canonical backend gate passed 1,479 tests with 20 existing
skips; frontend passed 858 tests and its production build. Canonical static
checks pass. The expanded acceptance-tool suite passes 82 tests. Frozen
`ae8397bf` additionally passed 102 backend and 82 frontend deterministic
reference checks. Its receipt records exact tested SHA, logs and canonical
source-tree equivalence. The `a3ac7735` receipt explicitly inherits those
source-equivalent checks and records fresh static/tool checks, rather than
claiming they were rerun at a different SHA. Derived summaries cite receipt
checksums while preserving original observed browser metadata.

The [provenance appendix](2026-10-04-overview-history-efficiency-provenance.md)
records exact product trees, runtime digests, cold-reader limits, raw artifact
paths, cleanup audit checksum and reproduction commands.

## Default promotion

After both sustained runs qualified, the unset frontend setting, Dockerfile,
Compose build argument and example environment now select one second. Explicit
`5`, invalid values and API errors retain five-second polling. The query key,
background/focus policy, cancellation and scheduling implementation are
unchanged. This selects the same one-second scheduler already exercised by the
qualified explicit-`1` builds. Fresh canonical checks and a rebuilt exact-SHA
native control run verify the default path; the sustained evidence above retains
its actual earlier SHAs and is not relabeled as an exact-head soak.

The
[default-validation receipt](2026-10-04-overview-history-default-validation.json)
records production candidate `87112f0a84ec6ee6fb56f5259c120cbe8a5f1cde`, fresh
native controls with two actual viewers, 20-second warm-up and 60.011 measured
seconds, zero errors and immediate owned cleanup. The Docker build omits the
cadence argument; its complete served asset manifest is identical to the
explicit-1 build used by the native control. Production Compose is also checked
for unset, explicit rollback, empty and invalid values. This bounded run
verifies default selection and lifecycle behavior; it is incomplete for
sustained gates. Fresh canonical checks pass 1,479 backend tests (20 skips), 858
frontend tests and the production build, plus static checks. The backend/static
tested SHA is `b93c8307`; the only subsequent source change is the refresh
integration test, which is included in the `87112f0a` canonical frontend run.

## Final review validation

Review regressions tightened the acceptance tools: failed Docker inventories
refuse startup/qualification and teardown still runs after backend lookup
errors. RSS requires every measured resource sample and both endpoints; retained
heap requires both endpoints and GC spacing <=310 seconds. Every viewer must
poll across the measured interval, with <=30-second gaps accommodating
response/GC pauses. That is a qualification tolerance rather than a
polling-start guarantee. A CPU baseline also requires verified cleanup and
viewer coverage. Original raw runs retain their SHAs; their summaries and
manifests are regenerated with the corrected evaluator and identified separately
from observed metadata.

Deferred rendered-density inquiry: the two-viewer end screenshot shows traces in
roughly the right quarter. Backend snapshots remain full-sized at both
endpoints, but the probe establishes parse/redraw activity and does not measure
plotted point/time coverage. That appearance remains unexplained; this evidence
does not establish full-window rendered density or an issue 211 root cause.

The corrected evaluator at `fb43bc63a57cbc947ef18c83b49df280712f86ea`
re-evaluates both original hours: all seventeen gates still pass. Each viewer
has 3,137 requests, maximum start gaps 1.524/1.430/1.428 seconds, and measured
endpoint coverage. RSS covers all 720/715 resource rows; thirteen post-GC rows
span each hour with maximum gaps 300.889/304.079 seconds. Backend snapshots
contain 46,826 points at both endpoints. Fresh two-viewer controls at that
candidate pass after a separate preserved pre-warm native CFI/seccomp failure;
the unchanged retry measures 60.010 seconds with zero errors and checked
cleanup. Its omitted-argument default build again matches the served explicit-1
assets. The complete acceptance-tool suite passes 104 tests. Product sources are
unchanged by the review fixes; final PR CI verifies the delivered head.
