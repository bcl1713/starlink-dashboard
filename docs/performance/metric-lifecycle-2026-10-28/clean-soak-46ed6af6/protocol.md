# Current-candidate clean-soak protocol

The production candidate is `46ed6af6d431cd7fac8633a9f3d829d5fc24d831`,
including development base `65a4df92b87a27eb8e2ac88985d8ce02f85e8fd8`. The
separately versioned qualification harness is identified by `harness_sha` in
each run. This branch adds evidence capture and coordinated control timing; it
changes no production application files. Production images are built from the
exact candidate archive with its unchanged Dockerfiles. Actual image IDs,
dependency versions, fixture hashes and the browser executable hash are
retained.

The sustained workload has one fullscreen 1920×1080 Overview and one Operator
page, a 30-minute history window, a real clock and one-second Prometheus scrape
and evaluation intervals. It uses the candidate's default display layers.
Resource samples occur every five seconds. Warmup is 120 seconds and the target
measured window is 3,620 seconds. Qualification requires an actual first-to-last
measured span of at least 3,600 seconds.

The three native control deadlines are measured-duration quarters: 905, 1,810
and 2,715 seconds after warmup. Sampling and read coordination can delay them;
actual execution times are recorded. The controls activate leg 2, deactivate,
then reactivate leg 1, and retain the three journal writes. A transition waits
for a fresh successful Operator read and a natural idle interval of 75 ms.
Afterward, the Operator must read the new health identity and, when a mission is
active, successfully read records bound to that identity. Each wait has a
10-second deadline. No UI polling is paused, intercepted or suppressed.

Every observed API request has a unique ID, full URL/scope, phase and terminal
outcome. Error response bodies are retained up to 64 KiB, with explicit size,
hash and capture errors. Oversized, unavailable or timed-out captures prevent
qualification. Playwright uses a whole-body API, so unknown-length responses can
allocate more before the retained-size check. Successful Operator health,
context, events, records and record-change responses retain source metadata and
body hashes rather than journal payloads. Other successes retain request and
terminal metadata.

The existing HTTP failure gate remains in force, including its existing exact
GPS-config 503 exception. Every other measured HTTP error, network error,
unexplained cancellation, unknown terminal request or capture error prevents
qualification. An observed `store_context_changed` response is recorded and
still fails. Protocol v2 permits a cancellation only with a recorded actual
`XMLHttpRequest.abort()` invocation for the same page, method and URL, matched
within 100 ms to the authoritative CDP network start. The request must be a
measured GET of this synthetic mission's Operator events, start no earlier than
two seconds before a declared transition, and finish within ten seconds after
it. At most one cancellation per page and transition can qualify. The control
must succeed, change the operating identity while preserving store, epoch and
mode, and produce successful health/context recovery on the affected page and
Operator page within that window. A fresh event read must recover the new source
when active; a fresh context read must confirm no mission when inactive.

The XHR wrapper preserves native arguments, return values and exceptions and
never initiates cancellation. The separate CDP observer enables network events
with an 8 MiB total buffer, 1 MiB resource buffer and zero POST-data buffer per
page. These observers add overhead. No cache or request interception settings
are changed. Raw cancellations and their unknown internal cause remain intact;
the classifier writes separate, hash-bound proof. Missing or ambiguous abort,
transition, source or recovery evidence fails qualification. Measurement ends
only at an idle, fully drained capture fence before the known harness teardown.
Outcome counts and raw request records must reconcile.

A separate short preflight uses the same services, capture code, 120-second
warmup and all three controls within a 120-second measured window. Its explicit
negative capture controls exercise a real stale-source 409 and a deliberate XHR
cancellation with actual abort-invocation proof in an isolated qualification
context. These intentionally failing probe outcomes are recorded separately and
are never part of the sustained measurement. The hour-long run has no injected
negative controls.

Independent Prometheus observations must show healthy scrapes, current mission
identity counts following 1 → 0 → 1, and no current mission gauges while
inactive. All three control writes and source recoveries must succeed. Cleanup
must verify that task processes, listeners, containers, networks, images,
disposable volumes and temporary runtime inputs are gone after each run.

The previous failed soak and final results remain immutable. Preflights 001 and
002 used the stricter v1 cancellation gate and remain failed; v2 does not
reclassify them. The v2 protocol and harness are committed before further runs.
This protocol qualifies a coordinated lifecycle workload with a diagnostic
headless browser. It makes no matched speedup, production capacity or
leak-freedom claim. The software renderer, observation overhead and actual
memory growth remain visible.
