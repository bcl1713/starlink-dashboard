# GFS Wind Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Replace GFS wind barbs with a wind-speed gradient, animated flow
trails, and a knots legend; enforce exclusive wind/temperature selection across
displays.

**Architecture:** Retain the existing GFS worker, grid admission, and controller
ownership. Enforce mode selection in the settings store and frontend parser;
extract the existing atmospheric mesh into a reusable raster owner, then attach
a bounded particle owner only to wind drawings. Drive motion through React Three
Fiber, using the existing controller lifecycle and weather budget.

**Tech Stack:** Python/FastAPI/Pydantic/filelock, TypeScript/React/Zod,
Three.js, React Three Fiber, Vitest, pytest, Playwright, and the existing Docker
acceptance runner. No new dependency or data provider.

**Spec:**
[Approved wind visualization design](../specs/2026-10-14-gfs-wind-visualization-design.md).

**Status:** Approved for native implementation by the user on 2026-10-14.
Hardware performance remains unverified until its target is identified; software
browser acceptance and hardware performance approval are separate.

## Global Constraints

- Implement in a feature worktree based on the latest `origin/dev`, with a PR
  against `dev`. Keep the primary checkout on `dev`. The inspected code base is
  `aef333d46a30c131f61a5de3bfe318c6a7618f43`; this documentation branch adds the
  approved spec. Carry the approved documents into the feature branch if their
  documentation PR has not merged. Record and review any intervening code diff.
  At feature setup, record `GFS_WIND_BASE_SHA` as the full pre-change dev SHA;
  use that same SHA for static-policy and paired baseline controls.
- Exactly three modes: both false is off; wind true implies temperature false;
  temperature true implies wind false. No particles over temperature.
- Preserve existing shared level/horizon, confirmation and five-second settings
  polling. Default-off additions, corrupt-file behavior, schema, masks, NOAA
  attribution, original freshness/expiry, and radar/bulletin behavior remain.
- Unrounded speed is `hypot(U, V) * 1.9438444924406` knots after conservative
  bilinear U/V interpolation. Do not round to barb increments or interpolate
  precomputed magnitudes. Invalid data is unknown, not zero.
- Palette: 0 `#1d4ed8`, 25 `#06b6d4`, 50 `#22c55e`, 75 `#eab308`, 100 `#f97316`,
  125 `#ef4444`, 150+ `#a855f7`; linear sRGB interpolation, opacity 0.45. Only
  displayed color saturates at 150 kt.
- At most 2,000 particles, 12 retained trail samples each at 30 Hz, staggered
  lifetimes at most six seconds, visual multiplier 12,000, integration steps at
  most 50 ms. Discard suspended time; no invented minimum wind speed.
- Shared optional-weather limits remain 16 MiB encoded, 32 MiB decoded/geometry,
  16 MiB GPU, four fetch/decode operations, and old-plus-candidate accounting.
  Keep each drawing within the existing envelope's 12 MiB decoded / 4 MiB GPU
  allocation declarations; do not silently increase them.
- Preallocate animation buffers. No particle/frame React state changes, new
  timers, forecast playback, user particle controls, or retained barb mode.
- Stop/dispose on disable, mode/selection change, hide, offline, expiry, and
  unmount. Reduced motion disables particles without a grid fetch.
- Every test/resource-owning run has an explicit wall limit and termination
  grace. Record ownership and verify scoped cleanup on success and failure.

## Review Focus

1. A legacy repair can bypass GFS demand invalidation or invert control/settings
   lock order; Task 1 tests repaired revisions with existing live demand.
2. A failed save may already have persisted a revision while worker
   acknowledgement fails; Task 2 tests confirmed UI state and subsequent
   revision reconciliation.
3. A preference change can arrive while a replacement grid is pending; Task 4
   tests that the newly admitted drawing observes the latest motion preference.
4. An entirely masked grid or extreme encoded winds can cause endless respawn or
   invalid geometry; Task 4 tests fixed work bounds and finite output.
5. The existing production proof enables both layers and rewrites the
   temperature texture to measure U/V; Task 5 measures each new native shader
   separately and fails if evidence is missing or only checks diagnostic output.

## File Map and Task Boundaries

Paths below are relative to the repository root. `F` abbreviates
`frontend/mission-planner`; `B` abbreviates `backend/starlink-location`; `A`
abbreviates `F/src/pages/aviation-weather`. Expand these in shell commands.

| Task                       | Production files                                                                                                                                                                                                                              | Tests / evidence                                                                                                                                                                                          |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1: Settings ownership      | `B/app/services/aviation_weather/settings.py`, `B/app/services/aviation_weather/gfs/bridge.py`, `B/app/api/aviation_weather.py`, `B/main.py`                                                                                                  | `B/tests/unit/test_gfs_settings.py`, `test_gfs_api.py`, `test_gfs_store.py`, `test_gfs_worker.py`, `test_gfs_ipc.py`, `test_main_aviation_weather.py`; `tools/acceptance/gfs-weather/check_foundation.py` |
| 2: Exclusive UI mode       | Create `F/src/services/gfs-mode.ts`; modify `F/src/services/aviation-weather.ts`, `A/AviationSettingsCard.tsx`, `A/gfs-controller.ts`                                                                                                         | Create `F/src/services/gfs-mode.test.ts`; extend `F/src/services/aviation-weather.test.ts`, `A/AviationSettingsCard.test.tsx`, `A/gfs-controller.test.ts`                                                 |
| 3: Raster and key          | Create `A/wind-scale.ts`, `A/grid-raster.ts`; modify `A/grid-shader.ts`, `A/grid-renderer.ts`, `A/GfsStatus.tsx`, `A/AviationWeather.css`; remove production `A/wind-barbs.ts`                                                                | Create `A/wind-scale.test.ts`; extend `A/grid-renderer.test.ts`, `A/GfsStatus.test.tsx`, `F/src/pages/OverviewMapLegend.test.tsx`; remove production `A/wind-barbs.test.ts`                               |
| 4: Particles and lifecycle | Create `A/wind-particles.ts`, `A/wind-particle-drawing.ts`; modify `A/grid-sampling.ts`, `A/grid-renderer.ts`, `A/gfs-controller.ts`, `A/GfsLayer.tsx`, `F/src/hooks/useGfsWeather.ts`                                                        | Create `A/wind-particles.test.ts`, `A/wind-particle-drawing.test.ts`, `A/GfsLayer.test.tsx`; extend `A/grid-renderer.test.ts`, `A/gfs-controller.test.ts`; create `F/src/hooks/useGfsWeather.test.tsx`    |
| 5: Production acceptance   | Extend `tools/acceptance/gfs-weather/runner.py`, `README.md`, `F/tests/e2e/gfs-weather-production.spec.ts`; create `F/tests/e2e/support/gfs-wind-probe.ts`, `F/tests/e2e/gfs-wind-performance.spec.ts`, `F/playwright.gfs-hardware.config.ts` | Extend `tools/tests/test_gfs_acceptance_runner.py`; update `docs/api/aviation-weather.md`, `docs/features/overview-weather.md`; create `docs/reports/2026-10-14-gfs-wind-visualization.md`                |

Keep the historical diagnostic renderer under
`F/tests/e2e/support/aviation-weather-proof/` and its tests intact: it documents
a previous proof, not the current production mode. Remove production barb
imports and production-specific assertions; retain signed sampling and
geographic tests.

Execute Tasks 1–5 in order. Each task has its own red/green checks and commit.

## Task 1: Exclusive Settings, Legacy Repair, and Demand Ownership

**Interfaces:** Preserve `AviationSettingsStore.get()` and
`update(changes: dict)`. `get()` returns an effective wind-precedence snapshot
without writing. Add `repair_legacy() -> tuple[AviationSettings, bool]`, where
the flag reports an atomic persisted repair. Add
`GfsBridge.read_settings() -> AviationSettings` (async) and its synchronous
`_read_settings()` helper.

- [x] Add named failing tests in `test_gfs_settings.py`:
      `test_partial_enable_disables_other_layer_in_one_revision`,
      `test_explicit_both_true_is_rejected_without_write`,
      `test_legacy_repair_is_atomic_and_idempotent`,
      `test_readonly_legacy_snapshot_never_writes`, and
      `test_concurrent_mode_saves_commit_exclusive_revisions`. Required
      assertions:

  ```python
  before = store.update({"temperature": True})
  after = store.update({"winds": True})
  assert (after.winds, after.temperature) == (True, False)
  assert after.revision == before.revision + 1
  assert store.update({"winds": True}).revision == after.revision
  ```

  Write a raw legacy JSON fixture with both true and revision 7; repair must
  persist wind-only revision 8 exactly once, preserving non-GFS fields and
  selection. A read-only store returns wind-only revision 7 with unchanged file
  bytes. Repeated concurrent saves must yield unique ordered committed revisions
  with no both-true snapshots. Empty/null/unsupported changes remain invalid.

- [x] Add route/bridge tests in `test_gfs_api.py` and startup coverage in
      `test_main_aviation_weather.py`: both-true PUT returns 422, file/demand
      stay unchanged, and GET/startup legacy repair clears old demand before
      returning the repaired revision. Test missing worker acknowledgement and
      lock contention with bounded deadlines. Use real stores/mailboxes and the
      existing child-worker fixtures; do not mock away revision invalidation.
- [x] Run from `B`, expecting the new exclusivity/repair assertions to FAIL:

  ```sh
  timeout --kill-after=10s 5m uv run --with-requirements requirements-dev.txt --with-requirements requirements-gfs.txt pytest tests/unit/test_gfs_settings.py tests/unit/test_gfs_api.py tests/unit/test_main_aviation_weather.py -q
  ```

- [x] Implement effective normalization without changing raw `_read()` data.
      `AviationSettingsUpdate.changes()` rejects explicitly both true before
      guarded runtime operations; preserve route validation status 422.
      `update()` validates first, takes the file lock, combines legacy
      normalization with the requested change, clears the counterpart on enable,
      and persists at most one revision using the existing
      tempfile/fsync/replace sequence. Repeated saves are no-ops.
- [x] Implement `repair_legacy()` under the settings lock, refusing writes for
      read-only stores. Bridge `_read_settings()` takes the mailbox control lock
      **before** the settings lock, repairs, then invalidates demand for the
      repaired revision before releasing control. `read_settings()` delegates
      through `asyncio.to_thread`; it does not wait for ingest. `_save()`
      continues to invalidate the single final update revision. Never acquire
      mailbox control from inside the settings lock.
- [x] Route settings GET and catalog settings reads through the bridge helper
      when present; fallback to the writable store's repair when there is no
      bridge. Initialize repair after bridge construction and before startup
      completes, preserving optional-weather startup failure isolation. Product
      admission and read-only worker `get()` calls only normalize; they do not
      repair or nest control locks. Preserve PUT's existing
      worker-acknowledgement behavior.
- [x] Update both-true fixtures in `test_gfs_api.py`, `test_gfs_store.py`, and
      `test_gfs_worker.py` to one admitted mode, parametrizing independent wind
      and temperature controls where necessary. In `check_foundation.py`,
      replace the combined enable with sequential modes: capture/verify wind
      descriptor and components, switch to temperature and verify its
      identity/components, confirm old wind URLs are denied, then restore wind
      for cancellation controls. Retain all original hash, mask, expiry, worker
      and core-response evidence.
- [x] Run the focused command and `pytest tests/unit/test_gfs_*.py -q` through
      the same uv environment with a 10-minute limit; require PASS, no hangs,
      and no owned workers left. Commit
      `feat: enforce exclusive GFS settings and legacy repair`.

## Task 2: Confirmed Exclusive Configuration and Frontend Admission

**Interfaces:** `gfs-mode.ts` exports
`GfsFlags = { winds: boolean; temperature: boolean }` and
`resolveGfsFlags(flags: GfsFlags): GfsFlags`, returning wind precedence if both
true. Re-export `GfsFlags` from `gfs-controller.ts` for existing imports.
`parseAviationSettings(data: unknown): ResolvedAviationSettings` retains its
signature, normalizing the flags after strict parsing.

- [ ] Write `gfs-mode.test.ts` with all four boolean combinations and tests that
      normalization never mutates the input. Extend parser tests with both-true
      revision 7: expect wind-only revision 7, unchanged level/horizon and
      non-GFS fields; malformed values still fail parsing.
- [ ] Extend Configuration tests using the real shared QueryClient and existing
      API boundary fixtures. `enabling wind atomically replaces temperature`
      starts in temperature mode and asserts the exact request and confirmed
      switches:

  ```typescript
  expect(aviationWeatherApi.updateSettings).toHaveBeenCalledWith({
    winds: true,
    temperature: false,
  });
  expect(screen.getByRole("switch", { name: "GFS winds" })).toBeChecked();
  expect(
    screen.getByRole("switch", { name: "GFS air temperature" }),
  ).not.toBeChecked();
  ```

  Add the inverse, both-off, failed save, and save rejection after persisted
  revision followed by polling reconciliation. Last confirmed cache data stays
  visible on rejection; a subsequent higher revision updates both switches.

- [ ] Add `legacy mode admits only wind` in `gfs-controller.test.ts`: supply a
      both-true input and a catalog containing both entries; only wind is
      loaded, drawn, and published. Selection/horizon and incompatible-drawing
      removal are unchanged. Run these tests plus `aviation-weather.test.ts` and
      `AviationSettingsCard.test.tsx` from `F` with the command below; expect
      FAIL before implementation.

  ```sh
  timeout --kill-after=10s 5m npm run test:unit -- src/services/gfs-mode.test.ts src/services/aviation-weather.test.ts src/pages/aviation-weather/AviationSettingsCard.test.tsx src/pages/aviation-weather/gfs-controller.test.ts
  ```

- [ ] Implement the helper/parser and atomic toggle mutations. Turning either
      switch off never enables its counterpart. Add helper copy: **Only one GFS
      layer can be displayed at a time.** Keep the shared selection, Surface
      disabled, pending-control disable, error handling, and confirmed-cache
      behavior. The controller consumes normalized settings; Overview never
      writes preferences to repair old snapshots.
- [ ] Rerun the named tests to PASS and commit
      `feat: make GFS Configuration toggles mutually exclusive`.

## Task 3: Wind-Speed Raster and Matching Legend

**Interfaces:** `wind-scale.ts` exports immutable `WIND_COLOR_STOPS`,
`windSpeedKnots(u: number, v: number): number`,
`windColor(knots: number): readonly [number, number, number]` (sRGB 0–1), and
`windLegendGradient(): string`. `grid-raster.ts` exports
`earthPoint(lat: number, lon: number, radius?: number): THREE.Vector3` and
`createGridRaster(lease: GridLease, mode: 'winds' | 'temperature', budget: WeatherBudget): GfsDrawing`.
Keep/re-export `earthPoint` and preserve the three-argument `createGridDrawing`
entry point. Extend it in Task 4 rather than making callers own animation.
Replace the obsolete `NativeGridDrawing` barb fields with
`mode: 'winds' | 'temperature' | 'off'`; preserve object/bytes/disposal. All-off
direct calls return an empty owned drawing; the controller normally avoids
drawing in off mode.

- [ ] Write `wind-scale.test.ts`: exact stops and constant, 3/4 m/s magnitude
      `9.719222462203` kt, halfway colors within floating tolerance, 150 and 250
      kt equal color, and 250 kt physical speed remains 250 kt. No wind
      rounding.
- [ ] Replace barb-specific renderer assertions with wind/temperature cases. A
      legacy both-true call must produce wind only. Signed U/V RGBA8 packing
      decodes -32768 and 32767 correctly; conservative masks use only
      positive-weight contributors. Retain geographic axes, seam/poles, triangle
      winding, day/night-independent materials, outward face, reservation
      rejection, and double-disposal checks. For opposite U samples at a
      midpoint, CPU/reference speed is zero, not the mean of magnitudes.
- [ ] Extend `GfsStatus.test.tsx` and `OverviewMapLegend.test.tsx`:
      current/stale wind shows **Wind speed · kt** and 0/25/50/75/100/125/150+
      labels, temperature shows only its °C key, legacy both-entries selects
      wind, and off/loading/ unavailable without an admitted drawing has no
      misleading key. Keep the existing level/horizon and passive-context tests;
      use admitted-drawing fixtures where required. From `F`, run the command
      below; expect FAIL before implementing the raster/key:

  ```sh
  timeout --kill-after=10s 5m npm run test:unit -- src/pages/aviation-weather/wind-scale.test.ts src/pages/aviation-weather/grid-renderer.test.ts src/pages/aviation-weather/GfsStatus.test.tsx src/pages/OverviewMapLegend.test.tsx
  ```

- [ ] Extract atmospheric mesh construction, winding, camera uniforms, and
      resource disposal from `grid-renderer.ts` into `grid-raster.ts`.
      Temperature continues to use its existing packed T shader. Wind packs U
      and V into two nearest-filtered RGBA8 textures, carrying mask bytes, with
      no mipmaps. Reuse geographic fragment reconstruction and interpolate
      physical U/V before magnitude. Build palette uniforms from
      `WIND_COLOR_STOPS`, including correct sRGB output handling, rather than
      duplicating hex values in GLSL.
- [ ] Keep raster radius 2.012, no raycast, transparent alpha 0.45, depth writes
      disabled, and existing below-marker render order. Reserve exact
      conversion, textures, geometry, and materials before allocation; dispose
      partial failures. Name meshes `GFS wind speed` and `GFS temperature`.
      Retain `userData.gfs.grid`, `bytes`, and `budget` ownership information
      for the existing evidence probe. Diagnostic U/V/T readback may expose
      numeric uniforms in this production shader, but no synthetic grid or
      acceptance-only renderer enters production. Define `diagnostic` as 0 for
      ordinary color, 1/2/3 for U/V/T signed packed readback, 4 for unsigned
      24-bit hundredths of a knot, and 5 for unblended palette output. U/V and
      speed diagnostics belong to wind; T belongs to temperature. Component
      readback keeps the existing signed Int16 encoding and mask; speed readback
      uses RGB with mask in alpha. Read numeric diagnostics with blending
      disabled in the probe, restoring material state afterwards. Diagnostic 5
      uses the same color calculation as normal rendering, with alpha 1 for
      valid cells. Ordinary rendering must independently obey the conservative
      mask and 0.45 opacity; diagnostic success alone is insufficient.
- [ ] Build the wind key from the same palette definition, with visible labels
      and accessible range/units text. Use responsive layout that permits a
      stacked key on narrow displays. Preserve temperature CSS, admission
      context, and the collapsed map legend. Remove production barb resources
      and their unit tests; keep historical proof support unchanged.
- [ ] Rerun focused tests, production `npm run build`, and relevant lint with
      explicit limits; require PASS. Commit
      `feat: render a knots-scaled GFS wind gradient`.

## Task 4: Bounded Flow Trails and Drawing Lifecycle

**Interfaces:** Add
`sampleWindInto(lease: GridLease, latitude: number, longitude: number, out: Float64Array): void`
to `grid-sampling.ts`; `out` has three elements `[u, v, mask]`, with `NaN`
components for invalid samples. It uses the same conservative stencil as
`sampleGrid`, without allocating arrays/objects per sample.

`wind-particles.ts` exports `WindParticleState`,
`createWindParticles(lease: GridLease): WindParticleState`, and
`advanceWindParticles(state: WindParticleState, deltaSeconds: number): void`.
State owns immutable grid identity, count, unit-sphere position/history arrays,
ages, sample accumulator, and preallocated `positions: Float32Array` and
`alpha: Float32Array` for trail line vertices. Use a deterministic seeded
generator derived from grid instance identity; no test-only constructor.

`wind-particle-drawing.ts` exports
`createWindParticleDrawing(lease: GridLease, budget: WeatherBudget): GfsDrawing & { update(deltaSeconds: number): void }`.
Extend shared `GfsDrawing` with optional `update(deltaSeconds: number): void`
and `setReducedMotion(reduced: boolean): void`. Native drawings expose both;
temperature methods are no-ops. Extend `createGridDrawing` with optional fourth
argument `{reducedMotion?: boolean}`, keeping three-argument callers valid. Add
`GfsController.setReducedMotion(reduced: boolean): void` and pass
`{reducedMotion: boolean}` as the fourth draw-callback argument.

- [ ] Write `wind-particles.test.ts` and sampler tests for physical direction:
      at the equator, positive U changes longitude eastward and positive V
      latitude northward; doubled U doubles angular distance within 0.1% for a
      1/60 s step. Integration uses Earth radius 6,371,000 m, not scene radius.
      Compare one second at 30/60/120 Hz within 0.05° angular error using
      identical initial seeds. One 60-second callback advances at most 50 ms;
      negative/nonfinite delta is a no-op. At exact/near poles and the seam all
      points remain finite and normalized.
- [ ] Test zero wind, signed extremes, masks 1/2/3, all-masked fields, cleared
      respawn history, staggered age/fade, 12-sample/2,000-particle caps, and 30
      Hz sample cadence independent of render frequency. Limit reseeding to four
      attempts per particle per update; entirely masked fields emit no visible
      segments with bounded work. Test buffers retain identity across updates.
- [ ] Write particle-drawing integration and controller/layer tests: bounded
      allocations; no far-side trails/raycast; disposal twice returns
      reservations; reduced-motion true creates no particle owner; toggling the
      preference releases and recreates particles without reloading the grid;
      temperature never creates a particle owner. Add pending-replacement
      preference changes, late download after mode switch,
      hidden/offline/unmount/expiry, and new-generation cleared history. Use the
      React Three test renderer for frame-loop contracts and real WeatherBudget;
      existing injected catalog/load boundaries remain fixtures.
- [ ] From `F`, run all new/affected tests; expect FAIL before implementing
      motion/lifecycle:

  ```sh
  timeout --kill-after=10s 5m npm run test:unit -- src/pages/aviation-weather/wind-particles.test.ts src/pages/aviation-weather/wind-particle-drawing.test.ts src/pages/aviation-weather/GfsLayer.test.tsx src/pages/aviation-weather/grid-renderer.test.ts src/pages/aviation-weather/gfs-controller.test.ts src/hooks/useGfsWeather.test.tsx
  ```

- [ ] Implement local-tangent integration using reused vectors/scalars, multiply
      physical motion by 12,000, and renormalize to the globe. Integrate capped
      time in substeps of at most 1/120 s, sampling every substep; preserve
      cadence at exact 1/30 s boundaries. Check mask validity along short
      emitted segments at no coarser than half-grid spacing and cap checks at
      eight per segment; if more are needed, clear/retire that trail instead of
      bridging unknown cells. Use equal-area deterministic seeds, lifetimes in
      [3,6] seconds, staggered initial ages, and fade the oldest samples and
      end-of-life trails. Valid calm wind remains static; no streak connects a
      respawn to its previous position.
- [ ] Implement one depth-tested `THREE.LineSegments` owner named
      `GFS wind particles`, radius 2.014, render order below operational
      markers, light sRGB color `#f8fafc`, per-vertex alpha, no depth writes, no
      picking. Allocate at most `2000 * 11 * 2` vertices. Reuse geometry buffers
      on updates. Account for CPU history, conversion scratch, positions/alpha,
      GPU geometry, materials, and candidate peaks; reserve before creating any
      owner.
- [ ] Make the native grid drawing own the raster and optional particle drawing.
      Its bytes report sums of active owned allocations, including preference
      transitions; disposal detaches both owners, clears references, and
      prevents later updates/recreation. Initialize particles only for wind with
      reduced motion false. Failed particle construction rolls back the complete
      candidate. If recreation after a preference change cannot be admitted,
      remove that drawing through the controller's existing failure path; do not
      throw out of the render loop or pretend particles are active.
- [ ] In `useGfsWeather`, reuse `usePrefersReducedMotion`; propagate its value
      into the binding before controller start and on changes. The controller
      preserves it across pending downloads and calls the admitted drawing
      setter without revising settings or fetching. `GfsLayer` calls only the
      current drawing's `update` inside `useFrame`; ownership and cleanup stay
      with the controller. Do not add timers or a duplicate preference
      subscription in `GfsLayer`.
- [ ] Run focused tests and the complete frontend suite with ten-minute limits;
      require PASS and zero retained budgets/listeners/workers on lifecycle
      cases. Commit
      `feat: animate bounded GFS wind trails with motion-aware cleanup`.

## Task 5: Native Browser Proof, Performance Evidence, and Delivery

**Interfaces:** Retain the existing `run.sh <exact-SHA> <browser> presentation`
entry point, source fixtures, project `starlink-290-gfs-presentation`, ports
15293/18293, and private volumes. Add evidence keys `wind_raster`,
`wind_particles`, `exclusive_modes`, and `reduced_motion` to presentation
requirements without removing existing keys. `gfs-wind-probe.ts` provides
`windSnapshot(page: Page)` and
`windReadbacks(page: Page, coordinates: GeoSample[])` using the actual admitted
scene/material/framebuffer. Define
`GeoSample = {latitude: number; longitude: number}`; `windSnapshot` returns a
promise containing presence, mode, grid instance, particle count, a bounded
position sample, draw calls, owned bytes and budget peaks. `windReadbacks`
returns a promise of samples with geographic location, physical U/V, knots,
validity mask, and four-channel RGBA readback. Probe types live in that
test-support module and are never imported by production.

- [ ] Extend `test_gfs_acceptance_runner.py`: removing any new proof rejects
      presentation PASS; NaN, infinity, zero samples, absent cleanup, or
      over-budget metrics reject PASS. Add route roundtrip and paired UI/browser
      assertions to `gfs-weather-production.spec.ts`, replacing combined-layer
      enable and ready predicates with explicit wind then temperature modes.
- [ ] Add native shader readbacks for signed U/V, physical speed and rendered
      color on independently captured NOAA oracle coordinates, plus labeled
      synthetic controls for opposite vectors/zero/masks. Check both diagnostic
      components and ordinary production color/alpha output. Tolerances:
      source/CPU quantization at most 0.01 m/s; packed GPU components at most
      0.02 m/s; knots error at most 0.06 kt; unblended color within 2/255 per
      channel. Select probe pixels away from particles, compare transparent
      masks against a raster-hidden control, and restore
      camera/material/visibility in `finally`.
- [ ] Add visible trail/direction checks on the real drawing, far-side
      occlusion, repeated wind/temperature/off cycles, live reduced-motion
      changes, mode change during refresh, complete generation swap, stale and
      original-expiry removal, and hidden/offline recovery. Confirm wind legend
      and temperature exclusion in both browser contexts; check radar hatching,
      reports/picking, route markers, and gesture behavior. Keep all existing
      foundation/source/hash/FL/terrain and core-response controls.
- [ ] Capture desktop 1920×1080, fullscreen at that viewport, and mobile 390×844
      screenshots for both modes and reduced-motion wind. Measure legend label
      rectangles for overlap, finite native geometry, draw calls, GPU/decoded
      peaks, and empty particle resources in temperature/off states. Browser
      exceptions or source-provider requests from the page fail acceptance.
- [ ] Run runner contract tests from the root:

  ```sh
  timeout --kill-after=10s 5m python3 -m pytest tools/tests/test_gfs_acceptance_runner.py tools/tests/test_gfs_compose.py -q
  ```

  Expect new evidence requirements to FAIL before extending runner/probes;
  implement them and rerun to PASS. Update the runner README and operator/API
  docs with exclusive toggles, knots scale, illustrative motion, and migration.
  Record measured results only after their runs, distinguishing pending gates.

- [ ] Add a dedicated hardware Playwright config with existing provisioned
      Chrome, one worker, no retries or SwiftShader flags, external same-origin
      Nginx URL, headed mode, and no managed/shared service startup. Inputs are
      `GFS_HARDWARE_BROWSER`, `GFS_HARDWARE_BASELINE_URL`,
      `GFS_HARDWARE_CANDIDATE_URL`, `GFS_HARDWARE_BASELINE_SHA`,
      `GFS_HARDWARE_CANDIDATE_SHA`, and `GFS_HARDWARE_OUTPUT_DIR`; validate
      exact SHAs, installed executable, and permitted HTTP(S) origins before
      opening contexts. Baseline and candidate each serve their own isolated
      production Nginx/backend/worker and identical pinned replay source. An
      absent target or fixture is an unmet preflight, never a substitute
      live-data benchmark. `gfs-wind-performance.spec.ts` selects the real
      controls and measures full-cap update duration via a scoped wrapper around
      the existing drawing update; restore the wrapper in `finally`. Keep
      instrumentation in acceptance support, not new production test APIs.
- [ ] Measure the two targets below. The approved spec requires naming the
      hardware environment before execution; until the user supplies its
      details, H1 is an outstanding preflight input, not a claimed passing
      benchmark.

  | Target         | Environment and fixture                                                                                                                                                          | Result required                                                                                  |
  | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
  | C1 correctness | This managed cloud environment's provisioned Chrome with SwiftShader, real-source historical replay, production Nginx, the viewports above                                       | All presentation evidence, resource bounds, cleanup; explicitly label software rendering         |
  | H1 hardware    | User-designated Overview workstation and installed Chrome, hardware acceleration enabled; record machine/OS/CPU/GPU/browser/DPR/refresh rate and WebGL renderer before execution | At 2,000 particles, p95 update ≤4 ms and p95 total frame duration ≤1.2× the paired barb baseline |

  For H1 use 1920×1080, fixed DPR 1, camera `(6,0,0)` looking at origin,
  controls idle, 500 hPa F006 pinned source. Measure once with GFS only and once
  with the same radar/bulletin overlay fixtures enabled. Warm up 15 s; capture
  60 s for each of three paired baseline/candidate runs, alternating order.
  Every run must satisfy the gates; use nearest-rank p95, report frame count,
  draw calls, allocation peaks, and core health/status latency. Use real time
  for animation; historical source replay does not alter frame timing. If
  hardware identity/fixtures are absent, renderer is software, or data is
  incomplete, record hardware gate **unverified** and do not claim deployment
  performance acceptance. Baseline is the implementation feature branch's exact
  pre-change dev SHA; archive it and build separately, never copy the old barb
  implementation into production as a selectable mode.

- [ ] Commit the acceptance changes as
      `test: verify exclusive GFS wind rendering and particle lifecycle`. Use a
      clean committed candidate for final controls from the repository root:

  ```sh
  ACCEPTANCE_POLICY_BASE_SHA="$GFS_WIND_BASE_SHA" timeout --kill-after=10s 20m python3 tools/verify static
  timeout --kill-after=10s 20m python3 tools/verify backend
  timeout --kill-after=10s 15m python3 tools/verify frontend
  GFS_ACCEPTANCE_SOURCE_DIR=/path/to/pinned/source-root timeout --kill-after=10s 40m tools/acceptance/gfs-weather/run.sh "$(git rev-parse HEAD)" /path/to/provisioned/chrome presentation
  ```

  These are commands to run during implementation, not verification performed
  while writing this plan. Discover actual installed/source paths through the
  established environment workflow; do not fabricate or install a browser. Use
  the actor's Docker daemon and fresh no-cache candidate images. Preserve
  exact-SHA artifacts and clean all task-owned processes, listeners, containers,
  networks, and disposable volumes after each attempt.

- [ ] Run H1 only after recording its target, pinned fixture delivery and paired
      baseline/candidate URLs. From `F`, with the six hardware inputs above set,
      run
      `timeout --kill-after=10s 15m npx playwright test --config playwright.gfs-hardware.config.ts gfs-wind-performance.spec.ts`.
      Record those inputs and target identity in the report; if H1 remains
      unavailable, report the outstanding gate plainly. Any source/tooling or
      report commit after acceptance changes candidate SHA: rerun applicable
      exact-head controls rather than attach stale evidence.
- [ ] Request a whole-branch review, fix verified findings, push the feature
      branch, and open a PR against `dev` linking the approved spec/plan and
      evidence. Leave merge and deployment out of this task. Do not call
      software-only proof hardware approval. Keep the worktree for the open PR,
      with runtime resources stopped and cleanup evidence attached.

## Coverage and Execution Handoff

Tasks 1–2 implement configuration, legacy compatibility, and synchronized
exclusive admission. Task 3 implements the fixed-scale raster, mask semantics,
and legend. Task 4 implements physical flow direction, bounded animation,
reduced motion, and ownership. Task 5 verifies real source/CPU/GPU agreement,
production views, lifecycle, budgets, and separate hardware performance gates.

The user approved this plan for native execution on 2026-10-14. Execute the five
tasks sequentially with an independent whole-branch review. H1 remains a
required input for hardware performance approval, rather than a software
correctness claim.
