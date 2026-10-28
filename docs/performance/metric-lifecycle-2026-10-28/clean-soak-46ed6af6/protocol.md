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
context, records and record-change responses retain source metadata and body
hashes rather than journal payloads. Other successes retain request and terminal
metadata.

The existing HTTP failure gate remains in force, including its existing exact
GPS-config 503 exception. Every other measured HTTP error, measured
cancellation, network error, unknown terminal request or capture error prevents
qualification. An observed `store_context_changed` response is recorded and
still fails. Cancellation error text is recorded; an unobserved internal abort
cause is not invented. Measurement ends only at an idle, fully drained capture
fence before the known harness teardown. Outcome counts and raw request records
must reconcile.

A separate short preflight uses the same services, capture code, 120-second
warmup and all three controls within a 120-second measured window. Its explicit
negative capture controls exercise a real stale-source 409 and a deliberate
browser cancellation in an isolated qualification context. These intentionally
failing probe outcomes are recorded separately and are never part of the
sustained measurement. The hour-long run has no injected negative controls.

Independent Prometheus observations must show healthy scrapes, current mission
identity counts following 1 → 0 → 1, and no current mission gauges while
inactive. All three control writes and source recoveries must succeed. Cleanup
must verify that task processes, listeners, containers, networks, images,
disposable volumes and temporary runtime inputs are gone after each run.

The previous failed soak and final results remain immutable. This protocol
qualifies a coordinated lifecycle workload with a diagnostic headless browser.
It makes no matched speedup, production capacity or leak-freedom claim. The
software renderer, observation overhead and actual memory growth remain visible.
