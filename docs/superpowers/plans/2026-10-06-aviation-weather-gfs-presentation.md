# Aviation weather GFS presentation implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development or superpowers:executing-plans to
> implement this plan task-by-task. Steps use checkboxes for tracking.

**Goal:** Complete Phase 2 with correctly derived flight levels, native wind
barbs/temperature shading and synchronized Configuration selections.

**Architecture:** Consume the merged foundation's immutable normalized grids,
keeping scientific decoding and flight-level derivation server-side. Production
scalar/vector renderers share admission and cancellation with Phase 1 weather;
Configuration owns all selection controls and Overview shows passive context.

**Tech Stack:** Python/NumPy, TypeScript/Zod, React Query, Three, Vitest, pytest
and provisioned Playwright/native WebGL acceptance.

**Spec:** [Approved Phase 2](../specs/2026-10-06-aviation-weather-phase-two.md).
**Dependency:** [Foundation plan](2026-10-06-aviation-weather-gfs-foundation.md)
must be merged into `dev` before creating this implementation worktree.

## Global constraints

- Preserve all foundation acquisition, store, IPC, time identity and expiry
  limits. Production does not import acceptance tools or decode scientific input
  in browser/API handlers.
- Pressure selections remain 850/500/300/250/200 hPa. Add
  FL050/100/180/240/300/340/390/450, reference 1013.25 hPa, derivation
  `isa-log-pressure-v1`, with actual ordered source pressures.
- Surface remains unsupported; no relabeling native pressure as FL, no GPS/AGL
  substitution, no extrapolation or temporal interpolation.
- Default-off wind/temperature; horizons Current/+3/+6/+9/+12/+18/+24/+36/+48
  hours. Show actual run and selected valid UTC rather than requested time
  alone.
- Shared Phase 1/GFS encoded/decoded/GPU limits 16/32/16 MiB, old plus
  candidate; four weather fetch/decode operations and 45-second generation
  deadline. Weather total 128/64 MiB preserves radar's reserved 96/48 MiB.
- One temperature raster, at most 2,000 wind barbs, no particles/animation.
  Hidden/offline/disabled/unmounted/superseded work aborts and disposes.
- Preserve radar coverage hatching, bulletin selection, route/operational marker
  visibility and globe interaction. Configuration owns controls.
- Every test/acceptance run has explicit wall limit, recorded owners and scoped
  cleanup. Clean exact-SHA no-cache production/browser acceptance is required.

## Review focus

1. Flight levels above the ISA troposphere boundary need the next ISA segment.
2. Shared wind/temperature buffers must not be double-counted or released while
   a sibling display still uses them.
3. Disabled/expired raster replacements cannot resurrect through late downloads.
4. Calm wind and seam/pole direction cannot become missing or reversed barbs.
5. Model legends and additional status must not obstruct mobile report
   inspection.

## Task 1: Genuine flight-level selections

**Files:** Create backend `app/services/aviation_weather/gfs/vertical.py`;
modify `app/models/aviation_grid.py`, GFS inventory/grid/settings and frontend
`src/services/aviation-weather.ts`; tests backend
`tests/unit/test_gfs_vertical.py`, `tests/unit/test_gfs_grid.py` and frontend
`src/services/aviation-weather.test.ts`.

**Interfaces:** Replace pressure-only `GfsSelection` vertical field with tagged
`PressureSelection(kind='pressure', pressure_pa: int)` or
`FlightLevelSelection(kind='flight-level', flight_level: int)`; migrate the
foundation's saved pressure selection without changing its meaning.
`flight_level_pressure(flight_level: int) -> float`,

```text
source_pressures(selection: GfsSelection, available_pa: tuple[int, ...]) -> tuple[int, ...]
```

```text
interpolate_vertical(fields: DecodedFields, target_pa: float) -> DecodedFields
```

Foundation's acquire/normalize/publish/bridge signatures remain stable.

- [ ] Write tests against independently tabulated ISA pressures for all enabled
      FLs, including FL390/450 above 11000 m; native pressure remains pressure.
      Assert log-pressure interpolation of known U/V/T, ordered bracket lineage,
      identical run/grid/lead, unavailable brackets, no extrapolation,
      conservative contributor/surface-pressure masks and quantization only
      after interpolation.
- [ ] Run

  ```sh
  timeout --kill-after=10s 5m uv run --with-requirements requirements-dev.txt --with-requirements requirements-gfs.txt pytest tests/unit/test_gfs_vertical.py tests/unit/test_gfs_grid.py -q
  ```

  from backend; expect missing FL derivation tests to fail.

- [ ] Implement two ISA segments: geopotential height h=FL×100×0.3048 m,
      p=101325×(1−0.0065h/288.15)^(9.80665/(287.05287×0.0065)) through 11000 m;
      above, p=p11×exp(−9.80665(h−11000)/(287.05287×216.65)), where p11 is
      computed by the first segment. Interpolate in ln(p), using nearest
      distinct bracketing levels admitted by inventory; include only necessary
      U/V/T and matching surface pressure in source admission. Publish actual
      source brackets; unavailable inputs remain unavailable.
- [ ] Run backend/strict frontend selection tests to PASS and ten independent
      numeric FL samples with physical error <=0.01 after quantization.
- [ ] Commit `feat: derive GFS flight levels with explicit source pressures`.

## Task 2: Shared browser admission and normalized-grid lifecycle

**Files:** Create frontend `src/services/aviation-grid.ts`,
`src/pages/aviation-weather/weather-budget.ts`, `gfs-controller.ts` and tests
`src/services/aviation-grid.test.ts`, `weather-budget.test.ts`,
`gfs-controller.test.ts`. Modify `aviation-controller.ts` and
`AviationLayer.tsx` to use the same budget, including inspection highlights.

**Interfaces:** `parseGridDescriptor(data: unknown): GridDescriptor`,

```text
fetchGrid(product: AviationProduct, signal: AbortSignal, budget: WeatherBudget): Promise<GridLease>
```

`GridLease` exposes descriptor, Int16 u/v/t, Uint8 mask and idempotent
`release()`.

```text
WeatherBudget.reserve(key: string, bytes: {encoded: number; decoded: number; gpu: number}): Reservation
```

`acquire(signal: AbortSignal): Promise<() => void>` caps all four fetch/decode
slots. `Reservation.release(): void` returns accounted ownership. GfsController
publishes GfsView with now, state (off/loading/current/stale/ unavailable),
enabled product envelopes and optional owned drawing. Its methods:

```text
start(): void; stop(): void
setSettings(settings: AviationSettings): void
setVisible(visible: boolean): void; setOnline(online: boolean): void
subscribe(listener: () => void): () => void
getSnapshot(): GfsView
```

- [ ] Write rejection tests for path/identity/hash/type/length/dtype/mask/unit
      mismatch before GPU allocation. Test wind/temperature component dedupe by
      hash plus geometry/quantization, sibling leases, combined Phase 1/GFS and
      highlight reservation, old-plus-new limits, fifth operation waiting,
      generation timeout at 45 seconds, abort at hide/offline/disable and late
      response after revision change. Assert all counters/slots return to zero.
- [ ] Run named new tests and existing `aviation-controller.test.ts` with
      `timeout --kill-after=10s 5m npm run test:unit -- <test paths>` from
      frontend; expect missing shared admission/grid lifecycle to fail.
- [ ] Implement strict bounded streaming/hash verification before parsing or GPU
      work. Fetch descriptor then buffers under one deadline. Account stream
      chunks, concatenation/conversion, owned arrays and old/candidate drawings;
      reference-count equal buffers instead of allocating duplicates. Share
      global optional-weather slots/reservations with bulletins/highlights,
      preserving radar's independent allowance. Drive expiry from catalog UTC
      plus monotonic anchor even when network fails; incompatible selections
      remove old drawing immediately. Poll catalog once per minute while
      visible.
- [ ] Run new and affected bulletin controller/layer tests to PASS.
- [ ] Commit `feat: share aviation grid resources and cancellation budgets`.

## Task 3: Native scalar/vector renderers and Configuration integration

**Files:** Create frontend `src/pages/aviation-weather/grid-sampling.ts`,
`grid-shader.ts`, `grid-renderer.ts`, `wind-barbs.ts`, `GfsLayer.tsx`,
`GfsStatus.tsx`; modify `AviationSettingsCard.tsx`, `AviationWeather.css`,
`src/hooks/api/useAviationSettings.ts`, `src/pages/OverviewPage.tsx`. Tests:
`grid-renderer.test.ts`, `wind-barbs.test.ts`, `GfsStatus.test.tsx`, existing
`AviationSettingsCard.test.tsx` and `OverviewPage.layers.test.tsx`.

**Interfaces:**

```text
sampleGrid(lease: GridLease, latitude: number, longitude: number): {u: number | null; v: number | null; t: number | null; mask: number}
```

```text
createGridDrawing(lease: GridLease, layers: {winds: boolean; temperature: boolean}, budget: WeatherBudget): GfsDrawing
```

`GfsDrawing` exposes Three object, exact owned bytes and idempotent dispose().
Configuration mutation accepts partial booleans or validated shared selection;
existing hooks keep confirmation and five-second visible settings polling.

- [ ] Write tests for geographic mapping x=cos(lat)cos(lon), y=sin(lat),
      z=−cos(lat)sin(lon), seam wrap/pole clamp, all-contributors-valid
      sampling, signed packed decoding and temperature offset. Assert <=2,000
      barbs, meteorological wind-from direction in both hemispheres, a calm-wind
      symbol, magnitude quantization and masked cells omitted. Test saved/failed
      settings, supported pressure/FL and unsupported Surface, model
      run/valid/level/units, stale/expiry labels and no added Overview selection
      controls.
- [ ] Run named tests with bounded frontend command; expect FAIL.
- [ ] Promote tested packed-scalar shader/projection algorithms into production
      without importing test support. Use nearest-filtered RGBA8 packing/manual
      conservative interpolation, no mipmaps; temperature shows a fixed labeled
      −80 to +40 °C palette with explicitly clamped ends (wire remains K). Barbs
      use a deterministic equal-area sampling subset and standard knots glyph
      increments from SI U/V; disclose thinning. Reserve geometry/material/
      texture/conversion before allocation. Put weather below operational
      markers and preserve radar hatching/bulletin click handling. Add
      Configuration's Flight-level atmosphere controls and passive Overview
      source/time legends.
- [ ] Run focused tests, `timeout --kill-after=10s 10m npm run test:unit`,
      `timeout --kill-after=10s 10m npm run build`; require PASS.
- [ ] Commit `feat: render GFS winds and temperature on the native globe`.

## Task 4: Integrated Phase 2 acceptance and handoff

**Files:** Extend `tools/acceptance/gfs-weather/run.sh`, `compose.yml`,
`source_fixture.py`, `check_foundation.py` and runner tests; create frontend
`tests/e2e/gfs-weather-production.spec.ts`; update
`docs/api/aviation-weather.md`, `docs/features/overview-weather.md` and a dated
report under `docs/reports/`.

- [ ] Extend runner with
      `run.sh <clean-40-hex-SHA> <provisioned-browser> presentation`, project
      `starlink-290-gfs-presentation`, loopback ports 15293/18293 and private
      volumes. Keep production images/Nginx/worker/grid renderers; fixture only
      source transport and clearly label deterministic time controls.
- [ ] Add browser assertions for two-browser Configuration propagation,
      pressure-to-FL/horizon changes, actual selected UTC, stale/expiry despite
      failed polling, disabled/hidden/offline recovery, late response
      cancellation, and model/source failures while core globe/telemetry remain
      usable. Validate U/V/T source/CPU/GPU samples independently, seam/poles
      and below-terrain masks; inspect native output and wind glyph direction
      rather than DOM legends alone. Capture desktop/fullscreen/mobile with
      radar and Phase 1 overlays enabled; verify report chooser/popups and map
      controls.
- [ ] Run

  ```sh
  timeout --kill-after=10s 40m tools/acceptance/gfs-weather/run.sh <SHA> <browser> presentation
  ```

  retain hashes, shader/readback/source comparisons, viewport/screenshots,
  actual encoded/decoded/GPU peaks including replacements, acquisition/decode
  CPU/RSS and disk usage. A missing metric, failed control or missing cleanup
  prevents PASS. Label software rendering and remaining hardware/minimum-host
  deployment evidence separately.

- [ ] Run required backend/frontend/static checks and exact-head CI; complete
      independent whole-branch review, fix findings and repeat affected controls
      on the final committed head. Preserve evidence and verify absence of task
      processes/listeners/containers/networks/disposable volumes before handoff.
      Push presentation PR against `dev`, leaving issue 290 open for Phases 3–6.
      Keep open-PR worktree; after verified merge perform AGENTS.md cleanup.

## Plan self-review

Foundation tasks 1–6 cover production contracts/settings, source acquisition,
scientific normalization/store, process isolation/IPC, API projection and first
PR acceptance. Presentation tasks 1–4 cover vertical derivation, shared browser
lifecycle, Configuration/rendering and integrated acceptance. Every review-focus
condition has explicit assertions in its owning task. Implementation remains
pending plan review; no completed Phase 2 behavior is claimed.
