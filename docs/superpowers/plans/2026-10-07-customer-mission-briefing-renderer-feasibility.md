# Customer Briefing Renderer Feasibility Gate

Required Task 3A details for the
[phase-one plan](2026-10-07-customer-mission-briefing-phase-one.md) and its
[technical companion](2026-10-07-customer-mission-briefing-phase-one-acceptance.md).
This is a planning document; the gate remains future implementation work. The
[approved spec](../specs/2026-10-07-customer-mission-briefing-trial-design.md)
sets the whole mission stage timeout to 60 seconds. The 50-second threshold
below is a feasibility screening margin, not a production timeout change.

## Task 3A contract

Task 3A depends only on Task 1 route snapshots. Use empty/synthetic markers, not
final Task 2 IDs. Prove readiness/framing in a disposable production-compatible
image before changing deployed backend packaging:

1. Build a dedicated local export entry with `CityLitGlobe`, `GlobeRouteRibbon`,
   `globe-route-projection.ts`, `overview-camera-frame.ts`,
   `overview-route-hemisphere.ts`, and `solar-position.ts::sunLightPosition`.
   Reuse `/earth-day-hi.jpg` and `/city-lights-mask.png`. Extract pure camera
   framing as needed; do not mount OverviewPage or its interactive controller,
   subscriptions, Date.now clock, aircraft, traffic, weather or dashboard UI.
2. Run from a production-compatible, non-root image with a packaged browser.
   Produce 1920 x 1080 PNG at fixed pixel ratio 1; planned reference time is
   effective leg takeoff. Wait for decoded textures, compiled shaders, settled
   camera, projected labels and completed deterministic render, not a sleep.
   Report readiness errors explicitly. Two identical inputs in the same runtime
   produce identical geometry/framing and decoded pixels; record PNG hashes.
3. Prove short, polar and dateline routes, then a route without a containing
   hemisphere. Split its ordered geometry into consecutive fitting views with
   shared endpoints; depth-test against globe. No through-planet visibility
   hack. All route pieces/markers fit with crop padding and neutral styling.
   Label lighting “Planned-time illustration” with reference timestamp.
4. Create F08-map now: three route-only snapshot legs with short, polar/dateline
   and hemisphere-spanning geometry; the last needs at least two views (>=4
   total). Later F08/F09 reuse these routes; no Task 2 fixture is an input to
   this gate. One request-owned stage, browser and shared 60-second monotonic
   deadline cover cold startup, assets/readiness, all primary maps/views, PNG
   collection and browser/listener cleanup. Use fresh processes and no
   request-cache hits for three runs on representative deployment hardware.
   Record hardware/image identity, cold startup, warm per-view cost, whole-stage
   elapsed and `60 - elapsed` margin. All required maps must succeed within 50
   seconds each run (>=10-second screening margin); this gate leaves the
   production timeout at 60 seconds. Missing views, routine fallbacks or timing
   failure are no-go: stop Task 2/3B/4, revise strategy and rerun. Do not
   silently raise the timeout or treat routine fallback as success.
5. Preserve runtime/asset versions, timing, readiness log and PNGs. Failed
   startup/texture/context loss and slow rendering must also prove fallback and
   cleanup. If packaging or framing fails, repair it before trial integration;
   repeated fallback is not evidence of successful overview rendering.

**Task 3A files:** Create root
`tools/acceptance/customer-briefing/map_feasibility.mjs` and
`tools/acceptance/customer-briefing/Dockerfile.renderer-feasibility`,
`backend/starlink-location/tests/fixtures/customer_briefing/f08_map_inputs.json`,
and the frontend scene/protocol/framing/child files below. The image packages
Node, locked Chromium/OS libraries and local assets for the proposed backend OS
ABI and non-root user. No production Docker/Compose/workflow changes in 3A.
`RendererFeasibilityReport` records fixture/input digests, runtime/hardware,
expected/actual leg-view IDs and PNG hashes, all run timings/margins,
failure/cleanup results and pass/no-go. Retain report before releasing Task 2.

**Create frontend files:** `mission-export.html`,
`vite.mission-export.config.ts`, `src/mission-export/main.tsx`, `scene.tsx`,
`protocol.ts`, `framing.ts`, and `render.mjs`. Build script
`build:mission-export` uses that separate Vite entry; output is
`dist-mission-export/`. Add that directory to root `.gitignore`. Add
`src/mission-export/framing.test.ts` and `tests/e2e/mission-export-map.spec.ts`
with a dedicated Playwright config.

## Handoff and bounded verification

From repository root run:

```bash
timeout --kill-after=10s 10m node \
  tools/acceptance/customer-briefing/map_feasibility.mjs
```

Wrap its disposable image build separately with a 45-minute wall-clock limit and
10-second kill grace. The runner also enforces one 60-second renderer stage per
request. Forced-timeout outcomes fail the gate and require verified cleanup
before retry, following the companion resource lifecycle.

Only a passing RendererFeasibilityReport releases Task 2. Task 3B then consumes
its final IDs and adopts the proven scene/runner in production packaging. Retest
F08-map with the final image/markers after integration. No phase-two worker
system or legacy replacement is authorized by this proof.

## Implemented gate reproduction

Task 3A provides a standalone scene and disposable image; deployed backend,
Compose and workflows remain unchanged. The fixture has five ordered primary
views: one short, one polar/dateline, and three consecutive views for a complete
circumnavigation. Empty route-only markers drive timing; synthetic numbers are
used only in separate framing/pixel checks. The scene uses radius-two Earth,
depth-tested neutral ribbons, fixed planned takeoff lighting, and a 75-degree
interior cap before applying the shared overview camera fitter. Labels are
projected inside padding and checked for collisions. Readiness requires decoded
textures, linked shaders, the final camera, projected labels and completed
demand frames; no readiness sleep or live dashboard is involved.

Build separately from repository root, retaining normal proxy/CA configuration:

```bash
timeout --kill-after=10s 45m docker build \
  --build-arg RENDERER_CANDIDATE_SHA="$(git rev-parse HEAD)" \
  -f tools/acceptance/customer-briefing/Dockerfile.renderer-feasibility \
  -t starlink-customer-briefing-task3a:local .
timeout --kill-after=10s 10m node \
  tools/acceptance/customer-briefing/map_feasibility.mjs
```

If the executor requires its public session CA for networked build steps, add
`--secret id=proxy_ca,src="$CODEX_PROXY_CERT"` to the build. The
Dockerfile-specific ignore file admits only renderer inputs; it excludes
credentials, data, worktrees, dependency caches and evidence. No root
`.dockerignore` is added.

The runner requires an image labeled with the checked-out full SHA, runs its
packaged browser contract checks offline, then creates three fresh non-root
containers with one browser per whole mission, four CPUs and 4 GiB. Each request
has one monotonic 60-second outer deadline, including container/Node/browser
startup, local assets, every primary view, collection and cleanup. The child
reserves time for cleanup inside that deadline. Browser failures return a
labeled fallback decision with no partial primary images. Actual legacy/static
fallback assembly remains Task 3B. A fallback in any timing run is a no-go.

Set `MISSION_MAP_IMAGE` to select the disposable image and
`MISSION_MAP_EVIDENCE` to select a private evidence directory. The default is
the phase-one plan workspace's `evidence/task-3a/`. The retained report contains
image, hardware, locked browser/library and OS package identity, source/asset
digests, per-view and whole-stage timings, expected/actual view IDs,
PNG/decoded-pixel hashes, and browser failure/cleanup results. Matching source
digests prevent a stale built scene from passing against current files.
Identical inputs in one runtime must produce identical framing and decoded
pixels; cross-platform pixel identity is not asserted.

Useful focused checks, each bounded by `timeout --kill-after=10s 10m`, are
`npm run test:unit -- src/mission-export/framing.test.ts` and
`npx playwright test --config playwright.mission-export.config.ts` from the
frontend, plus `node --test tools/tests/test_map_feasibility.mjs` from root. The
Playwright checks require `npm run build:mission-export` and the locked
packaged/provisioned browser. The gate runs these real browser checks inside its
image, retaining identical-input PNGs and startup, texture, context-loss and
shared-deadline failure evidence. Containers use `--init`, private loopback
listeners, no published ports, no network and no volumes. Ownership is recorded
before launch; every exit removes the owned containers. Host process/container
verification is still required before checkpoint handoff.

This proof releases Task 2 only. Task 3B must repeat the whole-mission gate in
the final production image with final interval markers. Exact-head CI, actual
ZIP/PPTX rendering, customer layout/semantics acceptance and the later review
remain separate gates.
