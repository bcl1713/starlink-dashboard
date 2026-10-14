# GFS Wind Rendering Tasks

Continuation of the [approved implementation plan](2026-10-14-gfs-wind-visualization.md).

## Task 3: Wind-Speed Raster and Matching Legend

**Interfaces:** `wind-scale.ts` exports immutable `WIND_COLOR_STOPS`,
`windSpeedKnots(u: number, v: number): number`,
`windColor(knots: number): readonly [number, number, number]` (sRGB 0–1), and
`windLegendGradient(): string`. `grid-raster.ts` exports
`earthPoint(lat: number, lon: number, radius?: number): THREE.Vector3` and

```ts
createGridRaster(lease: GridLease, mode: 'winds' | 'temperature', budget: WeatherBudget): GfsDrawing`
```

Keep/re-export `earthPoint` and preserve the three-argument `createGridDrawing`
entry point. Extend it in Task 4 rather than making callers own animation.
Replace the obsolete `NativeGridDrawing` barb fields with
`mode: 'winds' | 'temperature' | 'off'`; preserve object/bytes/disposal. All-off
direct calls return an empty owned drawing; the controller normally avoids
drawing in off mode.

- [x] Write `wind-scale.test.ts`: exact stops and constant, 3/4 m/s magnitude
      `9.719222462203` kt, halfway colors within floating tolerance, 150 and 250
      kt equal color, and 250 kt physical speed remains 250 kt. No wind
      rounding.
- [x] Replace barb-specific renderer assertions with wind/temperature cases. A
      legacy both-true call must produce wind only. Signed U/V RGBA8 packing
      decodes -32768 and 32767 correctly; conservative masks use only
      positive-weight contributors. Retain geographic axes, seam/poles, triangle
      winding, day/night-independent materials, outward face, reservation
      rejection, and double-disposal checks. For opposite U samples at a
      midpoint, CPU/reference speed is zero, not the mean of magnitudes.
- [x] Extend `GfsStatus.test.tsx` and `OverviewMapLegend.test.tsx`:
      current/stale wind shows **Wind speed · kt** and 0/25/50/75/100/125/150+
      labels, temperature shows only its °C key, legacy both-entries selects
      wind, and off/loading/ unavailable without an admitted drawing has no
      misleading key. Keep the existing level/horizon and passive-context tests;
      use admitted-drawing fixtures where required. From `F`, run the command
      below; expect FAIL before implementing the raster/key:

  ```sh
  timeout --kill-after=10s 5m npm run test:unit -- src/pages/aviation-weather/wind-scale.test.ts src/pages/aviation-weather/grid-renderer.test.ts src/pages/aviation-weather/GfsStatus.test.tsx src/pages/OverviewMapLegend.test.tsx
  ```

- [x] Extract atmospheric mesh construction, winding, camera uniforms, and
      resource disposal from `grid-renderer.ts` into `grid-raster.ts`.
      Temperature continues to use its existing packed T shader. Wind packs U
      and V into two nearest-filtered RGBA8 textures, carrying mask bytes, with
      no mipmaps. Reuse geographic fragment reconstruction and interpolate
      physical U/V before magnitude. Build palette uniforms from
      `WIND_COLOR_STOPS`, including correct sRGB output handling, rather than
      duplicating hex values in GLSL.
- [x] Keep raster radius 2.012, no raycast, transparent alpha 0.45, depth writes
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
- [x] Build the wind key from the same palette definition, with visible labels
      and accessible range/units text. Use responsive layout that permits a
      stacked key on narrow displays. Preserve temperature CSS, admission
      context, and the collapsed map legend. Remove production barb resources
      and their unit tests; keep historical proof support unchanged.
- [x] Rerun focused tests, production `npm run build`, and relevant lint with
      explicit limits; require PASS. Commit
      `feat: render a knots-scaled GFS wind gradient`.

## Task 4: Bounded Flow Trails and Drawing Lifecycle

**Interfaces:** Add

```ts
sampleWindInto(lease: GridLease, latitude: number, longitude: number, out: Float64Array): void
```

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

```ts
createWindParticleDrawing(lease: GridLease, budget: WeatherBudget): GfsDrawing & { update(deltaSeconds: number): void }`
```

Extend shared `GfsDrawing` with optional `update(deltaSeconds: number): void`
and `setReducedMotion(reduced: boolean): void`. Native drawings expose both;
temperature methods are no-ops. Extend `createGridDrawing` with optional fourth
argument `{reducedMotion?: boolean}`, keeping three-argument callers valid. Add
`GfsController.setReducedMotion(reduced: boolean): void` and pass
`{reducedMotion: boolean}` as the fourth draw-callback argument.

- [x] Write `wind-particles.test.ts` and sampler tests for physical direction:
      at the equator, positive U changes longitude eastward and positive V
      latitude northward; doubled U doubles angular distance within 0.1% for a
      1/60 s step. Integration uses Earth radius 6,371,000 m, not scene radius.
      Compare one second at 30/60/120 Hz within 0.05° angular error using
      identical initial seeds. One 60-second callback advances at most 50 ms;
      negative/nonfinite delta is a no-op. At exact/near poles and the seam all
      points remain finite and normalized.
- [x] Test zero wind, signed extremes, masks 1/2/3, all-masked fields, cleared
      respawn history, staggered age/fade, 12-sample/2,000-particle caps, and 30
      Hz sample cadence independent of render frequency. Limit reseeding to four
      attempts per particle per update; entirely masked fields emit no visible
      segments with bounded work. Test buffers retain identity across updates.
- [x] Write particle-drawing integration and controller/layer tests: bounded
      allocations; no far-side trails/raycast; disposal twice returns
      reservations; reduced-motion true creates no particle owner; toggling the
      preference releases and recreates particles without reloading the grid;
      temperature never creates a particle owner. Add pending-replacement
      preference changes, late download after mode switch,
      hidden/offline/unmount/expiry, and new-generation cleared history. Use the
      React Three test renderer for frame-loop contracts and real WeatherBudget;
      existing injected catalog/load boundaries remain fixtures.
- [x] From `F`, run all new/affected tests; expect FAIL before implementing
      motion/lifecycle:

  ```sh
  timeout --kill-after=10s 5m npm run test:unit -- src/pages/aviation-weather/wind-particles.test.ts src/pages/aviation-weather/wind-particle-drawing.test.ts src/pages/aviation-weather/GfsLayer.test.tsx src/pages/aviation-weather/grid-renderer.test.ts src/pages/aviation-weather/gfs-controller.test.ts src/hooks/useGfsWeather.test.tsx
  ```

- [x] Implement local-tangent integration using reused vectors/scalars, multiply
      physical motion by 12,000, and renormalize to the globe. Integrate capped
      time in substeps of at most 1/120 s, sampling every substep; preserve
      cadence at exact 1/30 s boundaries. Check mask validity along short
      emitted segments at no coarser than half-grid spacing and cap checks at
      eight per segment; if more are needed, clear/retire that trail instead of
      bridging unknown cells. Use equal-area deterministic seeds, lifetimes in
      [3,6] seconds, staggered initial ages, and fade the oldest samples and
      end-of-life trails. Valid calm wind remains static; no streak connects a
      respawn to its previous position.
- [x] Implement one depth-tested `THREE.LineSegments` owner named
      `GFS wind particles`, radius 2.014, render order below operational
      markers, light sRGB color `#f8fafc`, per-vertex alpha, no depth writes, no
      picking. Allocate at most `2000 * 11 * 2` vertices. Reuse geometry buffers
      on updates. Account for CPU history, conversion scratch, positions/alpha,
      GPU geometry, materials, and candidate peaks; reserve before creating any
      owner.
- [x] Make the native grid drawing own the raster and optional particle drawing.
      Its bytes report sums of active owned allocations, including preference
      transitions; disposal detaches both owners, clears references, and
      prevents later updates/recreation. Initialize particles only for wind with
      reduced motion false. Failed particle construction rolls back the complete
      candidate. If recreation after a preference change cannot be admitted,
      remove that drawing through the controller's existing failure path; do not
      throw out of the render loop or pretend particles are active.
- [x] In `useGfsWeather`, reuse `usePrefersReducedMotion`; propagate its value
      into the binding before controller start and on changes. The controller
      preserves it across pending downloads and calls the admitted drawing
      setter without revising settings or fetching. `GfsLayer` calls only the
      current drawing's `update` inside `useFrame`; ownership and cleanup stay
      with the controller. Do not add timers or a duplicate preference
      subscription in `GfsLayer`.
- [x] Run focused tests and the complete frontend suite with ten-minute limits;
      require PASS and zero retained budgets/listeners/workers on lifecycle
      cases. Commit
      `feat: animate bounded GFS wind trails with motion-aware cleanup`.
