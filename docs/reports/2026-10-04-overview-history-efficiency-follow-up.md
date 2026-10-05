# Overview history efficiency follow up

Issue 224's incremental reader and chart memoization were already delivered in
PR 228. This work amends their existing spec and measures the remaining HTTP,
browser and sustained resource costs. The default remains five seconds while
qualification is pending.

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

## Qualification status

Comparable release phases and the one/two-viewer 60-minute soaks remain pending.
The budgets require warm p95 below 500 ms, combined CPU increase at most 10
percentage points of one core over a healthy comparable full-range 5s baseline,
and backend RSS/retained browser heap growth at most 16 MiB after warm-up over
at least 3,600 measured seconds. Missing duration, provenance, behavior,
resource samples or cleanup remains incomplete.

The canonical backend gate passed 1,478 tests with 20 existing skips. The
canonical frontend gate passed 858 tests and the production build. Canonical
static checks passed after correcting two line lengths in the amended plan. The
expanded acceptance-tool suite passed 80 tests. These precede any proposed
production change and do not qualify a one-second default by themselves.

Raw evidence remains in the task-owned acceptance directory:
`/tmp/starlink-224-followup/.superpowers/sdd/2026-10-04-overview-history-efficiency-follow-up/evidence/`.
Each completed phase records candidate SHA, image IDs, runtime, raw timings,
resource samples, native artifacts, process logs and cleanup; checksums
accompany finalized evidence. Failed/interrupted runs remain available. No
production stack was deployed and issues 211/213 remain open.
