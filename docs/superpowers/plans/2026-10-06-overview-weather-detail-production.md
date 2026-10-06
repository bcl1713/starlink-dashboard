# Overview weather detail production implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> with the user's preserved Native execution choice. Implement task-by-task with
> one fresh whole-branch review at the end.

**Goal:** Improve observed radar detail during native Overview zoom and reduce
radar opacity while preserving international coverage and current resource caps.

**Architecture:** Retain RainViewer behind the backend's normalized contract and
keep complete zoom-2 fallback atlases. Select at most eight visible
higher-detail pairs from the existing camera, load them under shared budgets,
and publish matched slots into fixed detail textures owned by the displayed
frame.

**Tech stack:** FastAPI/Pydantic, asyncio, React/TypeScript, Three/React Three
Fiber, Vitest, pytest, Playwright, production Docker and Nginx.

**Spec:**
[Approved design](../specs/2026-10-06-overview-weather-detail-design.md).

## Global Constraints

- Preserve international observed coverage; avoid ongoing API fees. No ingest,
  forecast, satellite filling or additional aviation products in this issue.
- Keep default-off Configuration ownership and native rotate/zoom/follow/reset.
  Add no slider, manual refresh, resolution preference or weather interaction.
- Backend: 90 actual attempts/rolling minute, four active exchanges, 32 pending,
  48 cached PNGs/64 MiB. Detail subset: 30 attempts/minute, two exchanges;
  reserve two exchanges for coarse/metadata and prioritize their admission.
- Browser: four fetch/decode operations total, two detail; 45-second load
  deadline, 2 MiB PNG payload, strict 512-square decode, 96 MiB owned decoded
  ceiling.
- GPU: 32 MiB coarse plus 16 MiB detail, total 48 MiB. Two 2048-by-1024 detail
  atlases, eight 512-square slots, one-pixel gutters/510-square interiors; no
  mipmaps, double-buffered detail set or additional GPU metadata texture.
- Decoded: four coarse canvases 64 MiB, detail canvases 16 MiB, up to eight
  bitmap pairs 16 MiB; staging shares that pair budget, reserve before decoding.
- Selection: actual projection/view offset/globe transform/drawing buffer; at
  most 4 Hz, 400 ms stable demand, 20 percent resolution hysteresis, maximum
  zoom 7 and eight pairs. Retain eligible overlaps and coarse fallback.
- Preserve frame/settings/coverage identity, settings trust, existing 20-minute
  stale threshold, 60-minute expiry, midnight coverage expiry and attribution.
- Radar opacity candidate 0.40, compare 0.35/0.45/0.72 with operational
  overlays; hatch factor remains independently 0.17. Final choice needs rendered
  evidence.
- Work in this isolated feature worktree; primary checkout stays on dev. Record
  resource ownership before startup, bounded timeout/kill grace, and verify all
  owned processes, listeners, containers, networks and volumes gone.
- Preserve actor Docker configuration. Final acceptance uses exact committed
  SHA, production Dockerfiles/backend lifespan/Nginx, fresh evidence and CI.
  Push branch and PR against dev; do not merge or publish to main.

## Review Focus

1. Canonical path bypasses (`02`, `+2`, out-of-range XYZ) cannot reach DNS or
   dialing, even if FastAPI converts them to integers (Task 1).
2. Camera view offsets, antimeridian, poles and foreshortened horizon cannot
   request invisible regions or starve useful visible detail (Task 2).
3. Old decode completions after frame/settings/coverage changes close resources
   and cannot paint newer slots or extend freshness (Task 3).
4. Missing coverage on a slot boundary remains hatched during interpolation,
   fading, adjacency and coarse fallback (Task 4).
5. Coarse refresh under saturated multi-viewer detail demand retains priority,
   bounded memory and core-dashboard continuity (Tasks 1, 3 and 5).

## File map and shared types

Backend paths below are relative to `backend/starlink-location/`; frontend paths
are relative to `frontend/mission-planner/`.

- Modify backend models/API/service/transport/admission/acquisitions under
  `app/models/overview_weather.py`, `app/api/overview_weather.py` and
  `app/services/overview_weather/` and their existing unit tests.
- Modify frontend `src/services/overview-weather.ts` and its strict contract
  tests.
- Create `src/pages/weather/weather-detail-selection.ts` and tests: pure demand.
- Create `src/pages/weather/OverviewWeatherCameraObserver.tsx`: canvas observer.
- Create `src/pages/weather/weather-work.ts` and tests: shared operations/bytes.
- Create `src/pages/weather/weather-detail.ts` and tests: pairs/cache/lifecycle.
- Create `src/pages/weather/weather-detail-textures.ts` and tests: atlas slots.
- Modify existing atlas/controller/state/textures/layer, their tests, weather
  hook, `OverviewPage.tsx` and related mocked views to pass context/demand.
- Extend production e2e fixtures/spec/runner and feature/API documentation.

Shared types in `weather-detail-selection.ts` (first three) and
`weather-detail.ts` (last two):

```ts
type DetailKey = { z: number; x: number; y: number };
type CameraSnapshot = {
  projection: readonly number[];
  cameraWorld: readonly number[];
  globeWorld: readonly number[];
  drawingBuffer: readonly [number, number];
};
type DetailDemand = {
  keys: readonly DetailKey[];
  level: number;
  texelPixels: number;
};
type DetailContext = {
  generation: number;
  settingsRevision: number;
  manifest: ReadyWeatherManifest;
};
type DetailPair = {
  context: DetailContext;
  key: DetailKey;
  radar: ImageBitmap;
  coverage: ImageBitmap;
  dispose(): void;
};
```

Use bounded test helpers from the worktree root:

```bash
backend_weather_tests() {
  (cd backend/starlink-location && timeout --kill-after=10s 10m \
    uv run --with-requirements requirements.txt pytest "$@" -q)
}
frontend_weather_tests() {
  (cd frontend/mission-planner && timeout --kill-after=10s 10m \
    npm run test:unit -- "$@")
}
```

## Task 1: Normalized higher-zoom delivery and coarse priority

**Files:** Backend model/API/service/transport/admission/acquisitions and their
unit tests; frontend service contract/fixtures/tests; API endpoint
documentation.

**Interfaces:** Produce manifest `max_zoom: 7`, `source: 'rainviewer'`,
`product: 'observed-radar'`, `coverage_encoding: 'absence-rgba-v1'` in all
states; retain `zoom: 2`, tile size 512 and same-origin admitted templates.
Extend `WeatherAdmission.take_attempt(*, detail: bool = False)` and
`admit(deadline: float, *, detail: bool = False)`; zoom >2 determines detail.
Existing default consumers remain coarse. Cache keys retain kind/token/z/x/y.

- [ ] Write regressions for accepted z2/z7 edges and rejection of z1/z8,
      negative, fractional/boolean values, x/y equal to 2\*\*z, leading zeros
      and signs. Transport rejection must occur before a DNS spy is called. Pin
      strict frontend/backend provenance/max-zoom/encoding and reject unknown
      fields.
- [ ] Add fake-clock saturation tests: 30 detail attempts block the 31st; coarse
      still uses remaining overall budget, the 91st total attempt fails; every
      numeric retry counts. Two active detail tasks leave two coarse slots;
      queued coarse demand precedes detail; pending never exceeds 32.
      Cancellation/disable/shutdown release leases without invalidating others.
- [ ] Run affected backend tests and
      `frontend_weather_tests     src/services/overview-weather.test.ts`; expect
      RED on z7/new contracts.
- [ ] Implement canonical raw-coordinate validation before conversion, expand
      transport grammar with independent 2\*\*z bounds, add advertised literals,
      and bounded priority admission. Preserve public-IP pinning, TLS, frame
      admission, five-second provider deadlines, coalescing and cooldowns.
- [ ] Repeat tests to PASS, including existing transport/acquisition/lifecycle
      tests; commit `feat: deliver bounded higher-zoom weather tiles`.

## Task 2: Camera-driven bounded demand

**Files:** Selector/observer/tests, Overview page and map-controller tests.

**Interfaces:** Produce
`selectDetail(snapshot: CameraSnapshot, previous: DetailDemand | null): DetailDemand`;
`DetailDemandStabilizer.update(demand, nowMono)` takes `DetailDemand` and
monotonic milliseconds, returning `DetailDemand | null` only after stability.
Observer prop `onDemand(demand: DetailDemand): void` forwards actual canvas
camera snapshots; it owns its sampling clock.

- [ ] Write independent geometry tests with known globe landmarks, perspective
      projection/view offset and drawing-buffer changes. Assert <=8 canonical
      visible keys, zoom<=7, antimeridian wrap, Mercator limit, no back
      hemisphere or near-horizon-only refinement; regional zoom yields level >2.
- [ ] Add fake-clock tests: 399 ms gives no changed demand, 400 ms does;
      oscillation inside 20 percent keeps level, identical keys cause no event,
      stable overlap is retained, rapid movement replaces pending selection.
      Native follow/reset/rotate/zoom matrices and controls remain unchanged.
- [ ] Run
      `frontend_weather_tests src/pages/weather/weather-detail-selection.test.ts`
      and the existing map-controller test; expect RED on missing selector.
- [ ] Implement sphere intersections and projected tile footprint ranking using
      the actual matrices; choose finest fitting level or bounded coarser
      demand. Observer samples at most 4 Hz with no alternate camera/controls or
      polling outside the canvas. Suspend/clear pending demand with inactive
      context.
- [ ] Repeat tests to PASS; commit
      `feat: select weather detail from native camera`.

## Task 3: Shared browser budgets and frame-owned paired detail

**Files:** Work/detail owners/tests, atlas/controller/state/hook and
integration.

**Interfaces:** Produce
`WeatherWork.run<T>(kind, signal, operation): Promise<T>` takes
`kind: 'coarse' | 'detail'`, `signal: AbortSignal` and
`operation: () => Promise<T>`. Also produce
`reserveDecoded(bytes: number): () => void` (throws when unavailable). One
instance is shared by atlas/detail owners. Produce
`WeatherDetailOwner.setContext(context: DetailContext | null): void`,
`setDemand(demand: DetailDemand): void`, `snapshot(): readonly DetailPair[]`,
`subscribe(listener: () => void): () => void`, `dispose(): void`. Controller
owns the context and its generation, tied to the displayed manifest.

- [ ] Add delayed real-promise tests: four total/two detail operations, coarse
      priority, reservation before decode, eight pairs including staging,
      eviction closes bitmaps, failures release every reservation. Reject >2 MiB
      or wrong dimensions; only publish after both same-context images decode.
- [ ] Test changed selection cancels obsolete work but identical keys do not;
      bounded Retry-After and existing 30-second failure cooldown prevent camera
      polling retries. Keep eligible overlaps and displayed-frame detail while
      replacement coarse loads; failed detail leaves frame status unchanged.
- [ ] Test successful coarse swap clears old detail in the same context update;
      late decode after swap, settings revision, midnight, hide, disable,
      disconnect, navigation or StrictMode cleanup closes its bitmap and cannot
      publish. Preserve 20/60-minute freshness and existing recovery behavior.
- [ ] Run all weather atlas/controller/work/detail unit tests; expect RED on
      shared limits and missing context owner.
- [ ] Refactor atlas operations through shared work owner, evict detail bitmaps
      when coarse staging needs decoded reservations, and implement matched
      detail pairs/cache, reserve bitmap bytes before decoding and release on
      every path. Expose controller-owned context through hook/view; publish
      null when acquisition is disallowed. Bound pending demand to one
      selection.
- [ ] Repeat full frontend weather tests to PASS; commit
      `feat: own weather detail within displayed frame and shared budgets`.

## Task 4: Fixed detail slots, conservative edges and lower opacity

**Files:** New detail texture owner/tests; existing textures/layer/shader tests.

**Interfaces:** Produce
`WeatherDetailTextureOwner.replace(context, pairs, nowMono)` takes
`DetailContext | null`, `readonly DetailPair[]` and monotonic milliseconds,
returning `DetailTextureSet | null`. Also produce `dispose(): void`.
`DetailTextureSet` contains radar/coverage CanvasTextures and eight slot
bounds/rectangles/validity/fade uniform values. Existing coarse replacement
disposes detail first.

- [ ] Write allocation tests from texture dimensions: base32+detail16 MiB;
      coarse replacement peak<=48 MiB with detail disposed before allocation; no
      second detail set. Assert two textures for detail, mipmaps disabled,
      paired in-place publish, validity cleared before slot reuse, gutters
      sampled without neighbor bleed and teardown leaves no resources.
- [ ] Add geographic shader/pixel regressions for storm features present only at
      higher zoom, adjacency, antimeridian, projected polar limits and edge
      fallback. Missing/uncertain mask always retains hatching throughout fades
      and seams; detail from another context is rejected. Keep shader uniform
      object identity stable (Three caches it when a program is reused).
- [ ] Run texture/layer tests to RED, implement packing plus geographic lookup,
      200 ms entry fade and one-provider-texel edge transition to matching base.
      Blend premultiplied radar weighted by coverage, using conservative absent
      mask combination. Use candidate radar factor 0.40 and independent hatch
      0.17; retain depth settings, ignored raycast and native geometry.
- [ ] Run all weather unit tests to PASS; commit
      `feat: render paired regional weather detail with lighter opacity`.

## Task 5: Production acceptance, evidence and issue delivery

**Files:** Production e2e spec/provider/backend fixtures/runner, acceptance
tests, feature/API docs and dated production acceptance report.

**Interfaces:** Consume committed HEAD and production owners; produce immutable
SHA/image evidence, pixel/request/resource assertions, opacity judgment and
cleanup proof. Saved actual sources must run through production scheduling and
shader, with replay timestamps clearly distinguished from live fixture status.

- [ ] Extend provider fixtures with geographically independent detail-only rain
      and matched mask boundaries; force detail errors, quota saturation,
      changed frame and late completions. Seed aircraft/track, active route,
      POIs and labels over precipitation regions; keep telemetry/GEPs/borders.
- [ ] Extend native tests for existing camera minimum/maximum, wheel/touch,
      rotate/follow/reset, 1080p/fullscreen/mobile day/night; assert z>2 actual
      acquisition and added detail via pixels, paired identity and coarse
      fallback. Inspect all four opacity variants with populated overlays.
- [ ] Assert multi-viewer priority/attempt ceilings, decoded/GPU peak
      allocation, unchanged frame age on detail failure, automatic refresh,
      stale/midnight expiry, trust/visibility/disable/offline/navigation cleanup
      and continuity. Initial extended tests expect RED before the relevant
      production fixes.
- [ ] Commit candidate; run isolated issue-288 production acceptance with
      `timeout --kill-after=15s 30m tools/acceptance/overview-weather/run.sh <sha>`
      and issue-specific project/ports. Retain exact image IDs, screenshots,
      camera/pixel/request/resource data and ownership/cleanup records. Replay
      dated actual RainViewer matched base/detail captures separately through
      production owners; recapture if stored frames cannot be replayed without
      violating timestamp fences. No bypass of production freshness.
- [ ] Run focused backend/integration and complete frontend unit suites, lint,
      types, Markdown/filename checks and diff check with explicit time bounds.
      Expect all PASS; choose final lower fixed opacity from inspected views.
- [ ] Perform one fresh whole-branch review and resolve important findings. Any
      final source change requires a new committed-SHA acceptance run. Update
      docs/report, push feature branch, create/update PR against dev, require
      applicable exact-head CI and leave issue open until implementation
      satisfies acceptance. Stop/reap/verify all runtime resources immediately;
      retain only open-PR worktree and evidence.
