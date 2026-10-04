# Orbital Traffic Experiment: Tasks 4–7

Read the [main plan](2026-10-04-orbital-traffic-experiment.md) and
[Tasks 1–3](2026-10-04-orbital-traffic-experiment-tasks-1-3.md) first. Frontend
paths below begin at `frontend/mission-planner/`; other paths are repository
relative. Global constraints and existing production eligibility apply.

## Task 4: Bounded inferred route and handover state

**Files:** Create frontend `src/pages/orbital/geometry.ts`, `spatial-index.ts`,
`routing.ts`, `hysteresis.ts` and corresponding tests. Modify `types.ts`,
`orbital.worker.ts`, and add `routing-limits.test.ts` in that directory.

**Interfaces:** `OrbitalRoute` contains ordered string `ids`, `lengthKm` and
`identity` (catalog generation, satellite sequence and PoP location).
`segmentClearanceKm(start: FlowPoint, end: FlowPoint): number` returns closest
straight-line radius minus reference Earth radius.

```typescript
selectRoute(snapshot: PropagationResult, endpoints: OrbitalEndpoints,
previous: RoutingState): RoutingSelection
```

returns `route`, new hysteresis `state`, fallback reason and search-expansion
count. `routeIsValid(route, snapshot, endpoints): boolean` rechecks current
clearance and endpoint validity. RoutingState retains endpoint challengers and
route challengers separately. Use the same physical kilometer convention and
sphere as propagation; scene embellishment cannot make a physically invalid edge
admissible.

- [x] Write `greatest_elevation_and_single_satellite`: choose greatest endpoint
      elevation strictly above 10 degrees; numeric catalog-ID ordering resolves
      ties; a shared access/egress ID is one node. Invalid/missing endpoints
      return no route. Test exact threshold, aircraft altitude and polar
      endpoints.
- [x] Write `neighbors_and_shortest_bounded_path`: spatially indexed neighbors
      are the nearest eight admissible candidates, ties by numeric ID; require
      distance ≤5,000 km and clearance ≥80 km. A known graph chooses its
      shortest admissible path, never repeats nodes, and never exceeds eight
      satellite nodes or 2,048 expansions. Exhaustion returns no
      partial/fabricated path. Test disconnected graphs, identical positions,
      antimeridian crossings and analytic chord clearance where both vertices
      lie above Earth but the chord does not.
- [x] Write `hysteresis_and_immediate_invalidity`: a 5-degree elevation gain
      requires two consecutive selections; a 10-percent route-length improvement
      also requires two. Changed challengers reset counts. Broken current
      clearance or invalid endpoint bypasses immediately, including between
      five-second selections. No valid replacement means arc fallback in that
      snapshot.
- [x] Write `maximum_catalog_routing_is_bounded`: deterministic 16,384-object
      fixtures enforce neighbor/search caps and never materialize an all-pairs
      matrix. Index queries yield nearest admissible candidates without sorting
      all pairs; disconnected dense fixtures terminate under the search budget.
- [x] Run

  ```bash
  npm run test:unit -- src/pages/orbital/geometry.test.ts \
  src/pages/orbital/spatial-index.test.ts \
  src/pages/orbital/routing.test.ts \
  src/pages/orbital/hysteresis.test.ts \
  src/pages/orbital/routing-limits.test.ts
  ```

  require new failures before code.

- [x] Implement a spatial index and depth-constrained Dijkstra search on its
      directed candidate graph, keyed by `(satellite ID, hop count)` with stable
      ties and explicit cycle exclusion. Charge every expanded search state to
      the 2,048 budget. Select routes at most every five seconds; current-path
      validity is checked every snapshot and may clear the route sooner. Compare
      current and replacement lengths at the same UTC, not against old lengths.
- [x] Rerun to green, including route changes on catalog expiry and PoP change.
      Commit `feat: select bounded inferred orbital traffic routes`.

## Task 5: Mount lifecycle, cancellation and Configuration diagnostics

**Files:** Create frontend `src/hooks/useOrbitalTraffic.ts` and its test,
`src/pages/orbital/lifecycle.ts` and its test,
`src/pages/OrbitalTrafficDiagnostics.tsx` and its test. Modify
`src/pages/ConfigurationPage.tsx` and its test. Use Task 3's catalog API client.

**Interfaces:**

```typescript
useOrbitalTraffic({ settings: OverviewLinkSettings | undefined,
endpoints: OrbitalEndpoints }): OrbitalTrafficState
```

exposes previous/current snapshots, route, `spritesReady`, and `status`. Status
is a typed union of off, loading, ready, disconnected, expired,
provider-suspended and worker-failed, with diagnostic counts/times. Settings
remain owned by the existing query. `OrbitalLifecycle` owns mount generation,
abort controller, lease renewal, catalog poll, worker and disposal. Catalog
reads poll every 60 seconds while active; unchanged generation does not
reinstall worker elements. Diagnostics read `/api/orbital/status` with no lease
and no upstream side effects.

- [x] Write `inactive_means_no_orbital_resources`: orbital false/unconfirmed,
      Starshield false or initially hidden means zero worker creations, fetches,
      timers, snapshot buffers and leases. X-band false alone does not stop
      orbital demand. Failed settings reads retain confirmation without
      inventing true.
- [x] Write `hidden_disable_unmount_invalidate_every_generation`: pending lease
      PUT/catalog GET and worker messages after teardown cannot recreate
      anything. Abort requests, release lease, terminate worker and recycle/drop
      snapshots; lease TTL covers aborted PUT races and failed DELETE. Visible
      return rechecks settings before acquisition, then fetches current catalog
      and current UTC. StrictMode setup/cleanup/setup and 50 off/on cycles leave
      no owned resources.
- [x] Write `worker_failure_latches_until_explicit_retry`: error/invalid
      protocol or watchdog timeout (no response for five visible seconds)
      releases orbital resources and uses the arc; timer/catalog refresh does
      not recreate worker. Visibility return in the same mount retains the
      failure latch. Explicit orbital off/on or remount permits retry; test
      worker construction failure.
- [x] Write `configuration_only_diagnostics`: provenance explains public
      elements, inferred routing and abstract PoP leg; displays freshness,
      truncation, backoff/suspension and fallback reasons. Resume button calls
      only Task 2's explicit resume endpoint. No satellite IDs or badges reach
      the globe.
- [x] Run

  ```bash
  npm run test:unit -- src/hooks/useOrbitalTraffic.test.ts \
  src/pages/orbital/lifecycle.test.ts \
  src/pages/OrbitalTrafficDiagnostics.test.tsx \
  src/pages/ConfigurationPage.test.tsx
  ```

  verify red tests.

- [x] Implement ownership centrally, guarding every async continuation by mount
      generation. On lease failure use cached eligible snapshots only until
      lease validity ends, then release worker/dots and use the arc. Do not add
      optimistic settings or a second settings owner. Handle hidden/unmount and
      failure as separate states so visibility events cannot clear the failure
      latch.
- [x] Rerun to green. Commit
      `feat: own orbital viewer lifecycle and configuration diagnostics`.

## Task 6: Batched sprites and one measured path

**Files:** Create frontend `src/pages/orbital/OrbitalSprites.tsx`,
`sprite-resources.ts`, `traffic-path.ts` and corresponding tests. Modify
`src/pages/OverviewPage.tsx`, `OverviewPage.traffic.test.tsx`,
`OverviewMapLegend.tsx`, `OverviewMapLegend.test.tsx`, `OverviewPage.css`;
extend `AnimatedFlowLine.test.tsx` for orbital progress/handover regression.

**Interfaces:** `OrbitalSprites` takes Task 5's two snapshots, mount generation
and reduced-motion flag. `createSpriteResources(capacity: number)` /
`disposeSpriteResources(resources)` own batched Three.js geometry/material.

```typescript
projectOrbitalTrafficPath(route: OrbitalRoute | null, snapshot:
OrbitalSnapshot | null, aircraft: AircraftScenePosition | null, pop:
GlobeCoordinate | null): FlowPoint[]
```

builds one polyline. `chooseTrafficPath` returns either usable orbital points or
production `projectTrafficArc` points, plus a stable `particleKey`. Legend gains
`satellites: boolean` default false.

- [x] Write `sprites_have_two_draw_call_and_three_buffer_caps`: 16,384 objects
      use at most two sprite draw calls, never one mesh/React component per ID;
      buffers have two retained snapshots plus one in-flight update. Shader
      interpolation only joins matching IDs in the same catalog generation,
      avoids expired/invalid dots, stops under reduced motion, and never
      propagates per frame. Test mid-interpolation disable and reused buffers
      after StrictMode.
- [x] Write `orbital_polyline_preserves_clearance_and_altitude`: ground legs
      start/end at current aircraft/PoP and rise safely to selected satellites;
      space legs use actual propagated altitudes, verified analytic chord
      clearance. Reject any unsafe/nonfinite geometry rather than repairing a
      missing hop. Preserve unrelated globe starfield and camera composition.
- [x] Write `exactly_one_measured_flow_owner`: mount one Starshield
      `AnimatedFlowLine` with selected points and unchanged
      `TRAFFIC_PATH_STYLE`, `deriveOverviewLinkState` and emitters. Freshness
      failure/unavailable/zero throughput remains production behavior.
      Upload/download directions and 100-per-direction capacity do not change
      with hop count; X-band's synthetic activity/labels/warning are
      independent. Missing/expired catalogs and worker failure use the arc;
      disconnected route keeps eligible dots plus arc; invalid aircraft/PoP
      removes traffic while eligible dots may stay.
- [x] Write `motion_and_handover`: same satellite sequence/PoP preserves
      normalized particle progress on changed geometry; satellite sequence,
      catalog generation or PoP handover changes key and clears particles
      without bursts. Ordinary aircraft motion must not reset key. Reduced
      motion stops particles and interpolation while static geometry continues
      updating once per second. Legend has `Satellites` only when nonempty
      eligible sprites actually draw.
- [x] Run

  ```bash
  npm run test:unit -- src/pages/orbital/sprite-resources.test.ts \
  src/pages/orbital/OrbitalSprites.test.tsx \
  src/pages/orbital/traffic-path.test.ts \
  src/pages/OverviewPage.traffic.test.tsx \
  src/pages/OverviewMapLegend.test.tsx \
  src/pages/AnimatedFlowLine.test.tsx
  ```

  confirm failures before integration.

- [x] Implement batched depth-tested subordinate sprites with GPU interpolation,
      reusable typed buffers and explicit disposal. Integrate the single chosen
      traffic polyline before deriving existing link state/legend guards. Reuse
      `particleKey`, `canAnimateStarshield` and existing render budgets. Avoid
      rebuilding geometry because unrelated metric objects changed.
- [x] Rerun to green, run `npm run build`, and verify the production camera,
      route/history and metric panel suites. Commit
      `feat: render experimental constellation and single orbital traffic path`.

## Task 7: Controlled acceptance and laptop decision

**Files:** Create `tools/acceptance/journeys/orbital-traffic.mjs`,
`docs/testing/orbital-traffic-experiment.md`,
`docs/testing/orbital-traffic-experiment-results.md`. Add recorded catalog
fixtures to the journey's fixture directory. Reuse the existing browser bundle
and isolated Docker acceptance mechanism; do not modify production workflows.

**Interfaces:** Journey takes service URL, provisioned browser and artifact
directory from the established runner. Use fake provider/catalog fixtures for
deterministic scenarios, never a live GP download during CI. Record browser,
hardware, viewport, catalog size, off/on results, missing checks and artifact
paths. Results distinguish automated evidence from deployment-laptop evidence.

- [x] Write controlled assertions for all spec fallback-table rows; setting
      persistence across restart; two viewers sharing provider cooldown; hidden
      demand release; stale responses after disable; failure latch/retry;
      reduced motion; independent X-band warning; repeated-toggle
      GPU/worker/timer disposal. Run against a deliberately failed condition
      first to prove detection.
- [x] Run all three canonical quality gates from the main plan after targeted
      tests pass. Build the backend freshly in an isolated acceptance project
      and verify health. Missing browser/Docker/provider access must be recorded
      as environment-blocked; no success claim may stand in for an unrun check.
- [x] Execute browser journey at 1920×1080 with route/history and both links
      visible. Capture off/on images and numeric renderer draw/buffer/resource
      counters. Test 16,384-object and disconnected dense fixtures as well as a
      realistic constellation. Assert no extra labels/badges and no camera
      reset.
- [ ] Measure paired off/on 120-second runs after a 30-second warm-up; capture
      sustained FPS, p95 frame time, worker update latency, layer-attributable
      long tasks and GPU memory across 50 toggles. Targets are 30 FPS, ≤33 ms
      p95, <250 ms worker updates and no >50 ms layer main-thread task. Record
      failures as findings; keep default off and isolated if targets are unmet.
- [ ] Perform a policy-compliant real-provider smoke check through the backend,
      respecting persisted cooldown, and repeat paired performance/visual checks
      on the deployment laptop. Record machine/browser identity and results. A
      cloud browser result alone cannot satisfy this laptop gate.
- [x] Commit evidence/runbook as
      `test: document orbital experiment acceptance and performance`. Present
      the result for the user's decision. Keep experiment on its branch until
      the user explicitly approves promotion; pause future synchronization only
      when the experiment ends or is deleted.

Execution evidence is in
[the local results record](../../testing/orbital-traffic-experiment-results.md).
Task 7 remains partial while deployment-laptop validation, complete GPU memory
and definitive layer long-task attribution are unavailable. Local timed runs
are recorded separately and miss frame targets under SwiftShader; absence of
experimental-branch CI proves nothing.
