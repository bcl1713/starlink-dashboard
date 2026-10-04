# Orbital traffic experiment results

Local execution on `forge`, 2026-10-04. No cloud job or sync automation was
started. The original checkout and its work remain intact; implementation uses
`/tmp/starlink-261` on `experiment/261-orbital-traffic`.

This record is being populated from local evidence. Deployment-laptop identity
and access remain unanswered; that validation gate is blocked, not passed.

## Verified so far

- Task-by-task RED/GREEN tests; frontend 687 passed.
- Canonical backend: 1,470 passed, 20 skipped, two existing warnings.
- Canonical frontend: tests and production build passed. Existing bundle-size
  warning and optional satellite.js Node/WASM externalization warnings remain.
- Canonical static: passed after formatting corrections and running inside the
  cached Python development environment; no checks skipped.
- Fresh local Docker images for candidate `a919ce6a` after the visibility
  confirmation fix; actor endpoint
  `unix:///run/user/1002/docker.sock` retained.
- Backend HTTP health 200; semantic status degraded because the isolated
  two-service simulation topology has no Prometheus scrape.
- One real provider attempt at `2026-10-04T15:29:34.682511+00:00` succeeded.
  Accepted 11,122, eligible 11,120, rejected/truncated zero. Both viewer leases
  received identical generation and attempt timestamp. Releasing both left
  zero active viewers. No retry or operator resume was performed.
- Backend restart preserved all settings, catalog generation and provider
  attempt timestamp; orbital was restored off afterward.
- Controlled browser cases passed through the maximum catalog and disconnected
  fixture. The negative control detected the absent satellite layer.

## Pending evidence

The 50-toggle resource run and paired 30-second warm-up/120-second measurement
runs are active. Their numeric results will replace this paragraph.

The provisioned browser is Chrome for Testing 153.0.8010.12, checksum
`8c599d43aec53f2460a31ae2f4af6bd863f8258b34ff519564bc5d4726bfaa1e`.
It reports ANGLE Vulkan SwiftShader software WebGL2. These are local forge
measurements and do not satisfy the deployment-laptop hardware gate.

## Evidence locations and remaining gates

Local artifacts: `/tmp/starlink-261-evidence`. This includes build ledger/image
IDs, browser session identity, provider smoke, restart persistence, off/on
1920×1080 screenshots and controlled journey JSON. Canonical gate logs are
`/tmp/starlink-261-{static4,backend,frontend}.log`.

The independent whole-branch review is being requested with the unfinished
performance and laptop gates explicitly identified. Actual deployment-laptop
images/performance, actual background-tab
validation there, complete GPU/driver memory measurement and definitive
long-task attribution are unrun or unavailable. No CI absence is counted as
passing evidence. Promotion, auto-merge and issue closure remain unauthorized.
