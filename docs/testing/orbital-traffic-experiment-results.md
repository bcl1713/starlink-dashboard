# Orbital traffic experiment results

Local execution on `forge`, 2026-10-04. No cloud job or sync automation was
started. The original checkout and its work remain intact; implementation uses
`/tmp/starlink-261` on `experiment/261-orbital-traffic`.

Implementation and local checks are recorded below. Deployment-laptop identity
and access remain unanswered; that validation gate is blocked, not passed.

## Verified local checks

- Task-by-task RED/GREEN tests; frontend 691 passed.
- Canonical backend: 1,471 passed, 20 skipped, two existing warnings. Eighteen
  skips require absent legacy `dev/completed/kml-route-import` fixtures; two
  existing skips cover complex KML upload and unavailable integration
  `tmp_path`. None are counted as passes. Exact skip reasons are in
  `/tmp/starlink-261-skipped-checks.log`.
- Canonical frontend: tests and production build passed. Existing bundle-size
  warning and optional satellite.js Node/WASM externalization warnings remain.
- Canonical static: passed after formatting corrections and running inside the
  cached Python development environment; no checks skipped.
- Fresh local Docker images for candidate `17f2fb92` after the independent
  review fixes; actor endpoint `unix:///run/user/1002/docker.sock` retained.
- Backend HTTP health 200; semantic status degraded because the isolated
  two-service simulation topology has no Prometheus scrape.
- One real provider attempt at `2026-10-04T15:29:34.682511+00:00` succeeded.
  Accepted 11,122, eligible 11,120, rejected/truncated zero. Both viewer leases
  received identical generation and attempt timestamp. Releasing both left zero
  active viewers. No retry or operator resume was performed.
- Backend restart preserved all settings, catalog generation and provider
  attempt timestamp; orbital was restored off afterward.
- Final-source controlled browser journey passed 17 functional cases plus the
  negative control and 50-cycle resource assertion. Every off cycle released
  workers, viewer leases and all 458,752 bytes of orbital buffer storage. One
  current canvas retained production buffers; observed bounds were 83/92 buffers
  and 540,448/666,448 bytes. Native layer timers are separately covered by unit
  tests, not counted by this browser probe.
- Maximum catalog: 16,384 valid objects, one active worker and one constellation
  draw per frame. Sample total buffer allocation was 990,128 bytes, including
  458,752 orbital bytes. Full-catalog snapshot update sample: 118.3 ms.
- Final-image cached-provider check delivered all 11,122 accepted objects to
  both leased viewers with the original generation/clock, without a new provider
  attempt. Release returned demand to zero. Final-image restart persistence
  passed for all three settings, cached generation and provider timestamp.
- Inspected 1920×1080 screenshots show unlabeled dots and preserved metrics,
  route/history and link legend. The 2,048-object fixture stays visually
  restrained; the 16,384-object stress fixture forms a conspicuous dense shell.
  Its visual density remains a laptop/user acceptance consideration.

## Paired forge performance

Each mode used a separate 30-second warm-up and 120-second window, at 1920×1080
and pixel ratio 1, with the same 16,384-object synthetic catalog, route/history,
both links and metrics. Hardware: Intel Core i9-10900K at 3.70 GHz, 20 logical
CPUs, approximately 61 GiB RAM. Paired screenshots were inspected: the warmed
camera composition is consistent; dots have no labels and remain subordinate to
the highlighted links in the close view.

| Metric                    |      Off |               On | Evaluation                               |
| ------------------------- | -------: | ---------------: | ---------------------------------------- |
| Sustained FPS             |     8.90 |             6.93 | Both fail ≥30 target                     |
| p95 frame interval        | 199.9 ms |         250.0 ms | Both fail ≤33 ms target                  |
| Worker update p95 / max   |     None | 118.0 / 134.8 ms | Below 250 ms                             |
| Worker updates            |        0 |              120 | Once per second                          |
| Active workers            |        0 |                1 | Within cap                               |
| Constellation draws/frame |        0 |                1 | Within cap                               |
| Total draws/frame maximum |       30 |               31 | One extra constellation draw             |
| Orbital buffer bytes      |        0 |          458,752 | Three fixed attributes                   |
| Whole-page long tasks     |        0 |                9 | On maximum 60 ms; attribution unresolved |
| Snapshot handler maximum  |     None |          24.3 ms | Partial layer instrumentation            |
| Browser errors            |        0 |                0 | None observed                            |

The software-rendering baseline already misses frame targets, and enabling the
maximum catalog further reduces cadence. Nine whole-page tasks above 50 ms were
observed on; the observer does not identify the responsible layer. The complete
layer-attributable long-task gate is not passed. Instrumented snapshot handlers
stayed below 50 ms, while asynchronous rendering and mount work remain outside
that timing. No orbital-sized bufferData upload occurred in the warmed window;
this is not a measurement of complete upload or GPU cost.

These performance findings leave the experiment default-off and isolated. Actual
laptop measurements and the user's visual acceptance are still required.

The provisioned browser is Chrome for Testing 153.0.8010.12, checksum
`8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e`. It reports
ANGLE Vulkan SwiftShader software WebGL2. These are local forge measurements and
do not satisfy the deployment-laptop hardware gate.

## Evidence locations and remaining gates

Original provider artifacts: `/tmp/starlink-261-evidence`. Final-source
artifacts: `/tmp/starlink-261-evidence-reviewed`, containing build ledger/image
IDs, browser session identity, cached-provider and restart checks, health,
1920×1080 images, controlled journey JSON and paired performance evidence. Final
gate logs: `/tmp/starlink-261-reviewed-{static3,backend,frontend,tools}.log`.
The final documentation static rerun is `/tmp/starlink-261-final-static.log`.

Tested product source is `17f2fb92c831ceae05b337ebbfba9257fa4dd3c4`. Later
commits update only plan checkboxes and this evidence record. Final Docker image
IDs:

```text
backend  sha256:e498c8292c83b68e7eb02e80768d189b3a310b2d1fd2c47cee3192efa52f6f51
frontend sha256:6f7c4d0977b7f2300f6264fe08ec942f64fd635ceef289a70afd232dd6899e05
```

The independent whole-branch review and its regression fixes are complete.
Actual deployment-laptop images/performance, actual background-tab validation
there, complete GPU/driver memory measurement and definitive long-task
attribution are unrun or unavailable. No CI absence is counted as passing
evidence. Promotion, auto-merge and issue closure remain unauthorized.

## Independent whole-branch review

A fresh read-only reviewer examined `b2ea3341..4e8a0ef9`. No Critical findings;
three Important findings and one Minor. The diagnostics finding was regraded
Important because truthful fallback information is part of acceptance. All four
were reproduced with failing regression tests and fixed in `17f2fb92`:

- Ordinary HTTP LAN origins now use the existing browser-compatible client ID
  helper instead of requiring secure-context `crypto.randomUUID`.
- A catalog generation delivers its complete accepted membership. Future objects
  enter the worker eligibility window without reinstalling records.
- A failed replacement search retains an endpoint-consistent, physically valid
  prior route. Invalid routes and confirmed endpoint changes still fall back.
- Diagnostics distinguish successful last Overview routing from no observation
  and actual fallback, without inventing a failure reason.

Targeted review regressions: frontend 32 passed; backend 32 passed. Final
canonical backend, frontend and static gates passed; storage/Compose 48 passed.
Reviewer declined-to-judge list: empty. Deferred minors: none. The reviewer did
not rerun canonical suites; the implementer ran the final gates after fixes.

## Decisions made during execution

- Use `/tmp/starlink-261` for isolation because existing worktrees use `/tmp`
  and a project-local worktree directory was not ignored. Cost if wrong:
  relocation.
- Extract task briefs manually because the parser does not follow companion task
  documents. Cost if wrong: bookkeeping.
- Suspend all non-200 provider responses to match reviewed CelesTrak policy.
  Cost if wrong: additional intervention after a transient HTTP failure.
- Allocate the provider HTTP client lazily to preserve default-off startup
  behavior. Cost if wrong: first-request setup latency.
- Build the worker as ES modules because the verified satellite.js release
  cannot use Vite's default IIFE worker format. Cost if wrong: module-worker
  browser support required, already part of the baseline.
- Add the durable orbital Compose mount and entrypoint ownership omitted from
  the plan's container wiring. Cost if wrong: an extra storage directory.
- Require exact orbital buffer teardown and one current canvas owning buffers;
  record bounds for asynchronous production allocations. Driver-private GPU
  memory is unavailable. Cost if wrong: broader GPU attribution stays unproven.
- Regrade misleading successful-route diagnostics from Minor to Important and
  add a regression. Truthful fallback information is required for acceptance.
  Cost if wrong: a small extra diagnostic fix and test.

## Retained unsuccessful evidence

Initial formatting, Markdown and Python-environment gate failures were corrected
and rerun without waivers. An early 50-cycle run released all orbital resources
but failed an overly broad total-production-buffer equality assertion;
production allocation had two bounded levels, 83/92 buffers and 540,448/666,448
bytes. The probe now checks exact orbital release and current-context ownership.

The `a919ce6a` repeat completed 16 cycles before a satellite-legend timeout and
failed cleanup after the owned browser was closed. A subsequent endpoint probe
was denied socket access in the sandbox, so it does not establish a Chrome
failure. The unsuccessful artifact is retained at
`/tmp/starlink-261-evidence-final/browser/orbital-browser-results.json`. The
final source rerun passed in a fresh local session with authorized loopback
access and a correctly applied 15-second sprite visibility timeout.

## Branch and local resource state

Origin was fetched again at 16:39 UTC on 2026-10-04. Current `origin/dev`
remained `b2ea3341`, already contained in the experiment; no merge was needed.
Only `experiment/261-orbital-traffic` is pushed. No rebase, force push,
promotion PR, auto-merge or issue closure was performed. The original checkout
remains clean on `dev`; the isolated worktree is retained for laptop follow-up.

The journey restored orbital off. Owned acceptance browsers, Compose services
and task builder are stopped through platform cleanup. Evidence and owned cache
volumes remain local; no background cloud synchronization was enabled.
