# Orbital traffic experiment acceptance

Issue #261 supplies the existing optional orbital implementation. The user
requested restoring this option together with saved-settings compatibility on
2026-10-04; `fix/orbital-settings-schema` contains both changes for review.
Orbital mode remains off by default. Merging into `dev`/`main` and closing the
issue remain separate from implementation and require review of the final
candidate. Verify deployment-laptop GPU and actual background-tab behavior
before treating the earlier local performance measurements as laptop evidence.

## Local preparation

Use an isolated worktree. Fetch origin and merge current `origin/dev` into the
experimental branch before each session and hourly during active work. Use
regular merges and normal pushes. Do not activate cloud execution or cloud
synchronization. Preserve the actor's Docker endpoint and active context.

Run the canonical gates with Node 22.22.2 and the backend development Python
dependencies available on PATH:

```sh
ACCEPTANCE_POLICY_BASE_SHA=$(git merge-base origin/dev HEAD) ./tools/verify static
./tools/verify backend
./tools/verify frontend
```

The static gate invokes `python3 -m pytest`; a bare system Python without
pytest cannot complete it. Run the gate inside the development environment,
without skipping its final check. Inspect command exit codes, not just log tails.

Reuse `tools.acceptance.platform.compose` to render and validate an isolated,
loopback-only topology from tracked Compose and `.env.example`. Build with
`build_final`, inspect image IDs, and start with `start_no_build`. The existing
V2 contract supplies the two service names and build inputs for this experiment;
its V2 product journey is **not** an orbital acceptance result. Do not modify
production workflows or borrow production volumes. Cache storage at
`/app/data/orbital` must be independently writable and durable.

Use the provisioned browser profile with
`tools.acceptance.platform.health.start_final_browser_session`. Do not install
another browser or change the acceptance platform. Record its browser checksum
and WebGL renderer. SwiftShader measurements describe software rendering and
cannot establish deployment-laptop GPU performance.

## Controlled browser journey

The journey attaches to the platform-owned CDP session:

```sh
node tools/acceptance/journeys/orbital-traffic.mjs \
  --session http://127.0.0.1:PORT \
  --origin http://127.0.0.1:FRONTEND_PORT \
  --artifacts /tmp/orbital-evidence \
  --prove-failure true --toggles 50 --performance true
```

Run functional stress with `--performance false`. For paired timing in a fresh
browser session use `--phase performance --performance true`; this avoids
contamination by prior stress runs. Every completed toggle is saved immediately.

Run from the repository root, or pass `--repository-root`. Settings use the
actual backend and Configuration controls. Status, route/history, configured
X-band, leases, and catalog responses are explicitly browser-intercepted
fixtures. No GP endpoint is contacted by this journey. The recorded synthetic
OMM template expands into 2,048 or 16,384 objects at a common run UTC epoch; it
is not public satellite telemetry. The disconnected fixture moves the abstract
PoP to longitude 120 degrees.

The negative control deliberately expects a satellite legend entry while off
and must detect its absence. Functional cases cover production fallback,
telemetry failures, expiry, independent controls, worker failure/retry, delayed
responses, controlled visibility events, reduced motion and repeated teardown.
Real propagation and routing run inside the built module worker. Unit tests
separately exercise physical clearance, hysteresis, particle progress,
StrictMode, watchdogs and exact resource caps. The browser's visibility case
uses a controlled `visibilitychange` event; also check actual background-tab
behavior on the deployment laptop.

The probe observes native worker messages and WebGL operations. It preserves
transfers and rendering behavior. Counted GPU buffer bytes are allocated buffer
storage, excluding textures and driver-private memory. Full-catalog point draw
calls identify the constellation batch. Production buffers can shrink as other
layers settle; off cycles must release orbital-sized buffers, workers and
viewer demand. Only the current canvas may own GPU buffers after teardown;
record total allocation bounds rather than comparing asynchronously initialized
production layers at an arbitrary instant. Account for native context loss,
which releases its buffers without individual `deleteBuffer` calls.

Performance uses a 30-second warm-up followed by 120 seconds each for off and
on at 1920×1080. Record sustained frame cadence, p95 frame interval, worker
latency and page long tasks. Handler/upload timings cover only those instrumented
operations. Whole-page long tasks are not automatically attributable to the
orbital layer; preserve that limitation instead of declaring the attribution
gate passed. Inspect images for subordinate unlabeled dots, unchanged camera
composition, and preserved route/history, both links and metrics.

## Provider and persistence checks

Review CelesTrak's format and usage policy before a live check; see
[the recorded provider policy](../development/orbital-provider-policy.md).
A live check must go through the backend and its durable reservation. Before
starting, inspect status and existing cooldown. Acquire two viewer leases,
observe their shared generation and attempt timestamp, then release both.
Never resume a provider failure just to make acceptance pass. All non-200
responses suspend until operator intervention; resume preserves cooldown.

Record health's HTTP response and semantic status separately. The two-service
acceptance topology lacks Prometheus, so simulation health may report degraded
while returning HTTP 200. Restart/recreate the isolated backend and verify all
three settings, the last good catalog and provider clock persist. Restore
orbital off before teardown. Use the platform cleanup functions for the exact
owned Compose project, browser session and builder. Retain evidence and cache
volumes according to their existing ownership rules.

## Deployment laptop gate

Identify the actual deployment machine and browser. Repeat the paired visual
and timing checks there with the real renderer, both links and route/history.
Targets are at least 30 FPS, p95 at most 33 ms, worker updates below 250 ms,
and no layer-attributable main-thread task above 50 ms. These are experimental
targets, not guarantees. Record every blocked/unrun check. Keep default off
and leave promotion pending when measurements fail or the laptop is unknown.
