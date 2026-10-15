# Customer Briefing Renderer Feasibility Gate

Status: historical map-renderer qualification plan. Reuse its map work subject
to audit, but prior timing/render results do not qualify combined HTML/PDF
rendering. The
[restart spec](../specs/2026-10-08-customer-briefing-html-pdf-design.md) defines
the new proposed render contract; do not execute the old trial plan.

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
