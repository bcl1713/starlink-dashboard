# Overview weather detail production implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> with the user's preserved Native execution choice. Implement task-by-task with
> one fresh whole-branch review at the end.

**Goal:** Improve observed radar detail during native Overview zoom and reduce
radar opacity while preserving international coverage and current resource caps.

**Architecture:** Retain the normalized backend weather contract. RainViewer is
the initial observed-radar adapter unless Task 0 demonstrates a practical
replacement. Manifest capabilities drive bounded camera selection, paired
loading and fixed texture packing; provider URL grammar stays server-side.

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
  deadline, 2 MiB PNG payload, schema-validated dimensions, 96 MiB decoded cap.
- GPU: 32 MiB coarse plus 16 MiB detail, total 48 MiB. Two 2048-by-1024 detail
  atlases, eight 512-square slots, one-pixel gutters/510-square interiors; no
  mipmaps, double-buffered detail set or additional GPU metadata texture.
- Decoded: four coarse canvases 64 MiB, detail canvases 16 MiB, up to eight
  bitmap pairs 16 MiB; staging shares that pair budget, reserve before decoding.
- Selection: actual projection/view offset/globe transform/drawing buffer; at
  most 4 Hz, 400 ms stable demand, 20 percent resolution hysteresis, maximum
  zoom from manifest capabilities and eight pairs. Retain eligible overlaps and
  coarse fallback.
- Preserve source/provenance/product/schema/frame/coverage identity, settings
  trust, existing 20-minute stale threshold, 60-minute expiry, midnight coverage
  expiry and attribution.
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
   and cannot paint newer slots or extend freshness; a different normalized
   source with matching XYZ/time cannot reuse old detail (Tasks 1, 2 and 3).
4. Missing coverage on a slot boundary remains hatched during interpolation,
   fading, adjacency and coarse fallback (Task 4).
5. Coarse refresh under saturated multi-viewer detail demand retains priority,
   bounded memory and core-dashboard continuity (Tasks 1, 3 and 5).

## File map and shared types

Backend paths below are relative to `backend/starlink-location/`; frontend paths
are relative to `frontend/mission-planner/`.

- Modify backend models/API/service/transport/admission/acquisitions under
  `app/models/overview_weather.py`, `app/api/overview_weather.py` and
  `app/services/overview_weather/` and their existing unit tests. Create
  `app/services/overview_weather/rainviewer.py` for adapter-specific discovery,
  paths and capability constants; no second live adapter or ingest framework.
- Modify frontend `src/services/overview-weather.ts` and its strict contract
  tests.
- Create `src/pages/weather/weather-detail-selection.ts` and tests: pure demand.
- Create `src/pages/weather/OverviewWeatherCameraObserver.tsx`: canvas observer.
- Create `src/pages/weather/weather-work.ts` and tests: shared operations/bytes.
- Create `src/pages/weather/weather-detail.ts` and tests: pairs/cache/lifecycle.
- Create `src/pages/weather/weather-detail-textures.ts` and tests: atlas slots.
- Modify atlas/controller/state/textures/layer/status, their tests, weather
  hook, `OverviewPage.tsx` and related mocked views to pass context/demand.
- Extend production e2e fixtures/spec/runner and feature/API documentation.

Shared contracts, exact types and bounded test helpers are defined in the
[normalized contract](2026-10-06-overview-weather-detail-contract.md).

## Task 0: Provider decision and validation (completed)

**Files/Interfaces:** [Comparison results][results] select the Task 1 adapter.

- [x] Compare immutable RainViewer z2 and z5/z6/z7 imagery against bounded MRMS
      and OPERA observed composites: 80 native desktop/fullscreen/mobile,
      day/night views. Record visible detail, requests/storage, processing,
      fetch/decode/upload latency, CPU/RAM and measurement limitations.
- [x] Record decision: raw generation is feasible but does not justify changing
      #288 or replace international coverage. Proceed with the RainViewer
      adapter, advertising max zoom 7 and 512px tiles; no continuous ingest. The
      48 MiB proof applies to this selected schema, not every future source.
- [x] Evidence validated by the completed comparison workflow: replay candidate
      `553d96ded55971cda417cd79f1c14182d7d2bab6`, hashes and cleanup retained.
      Reuse these results; repeat only if evidence becomes insufficient.

## Task 1: Normalized higher-zoom delivery and coarse priority

**Files:** Backend model/API/service/transport/admission/acquisitions and their
unit tests; frontend service contract/fixtures/tests; API endpoint
documentation.

**Interfaces:** Produce the strict normalized manifest in the linked contract.
The selected adapter advertises its capabilities; the browser accepts bounded
source identifiers rather than a RainViewer source enum. Keep source-neutral
same-origin routes and admitted product identities. Extend
`WeatherAdmission.take_attempt(*, detail: bool = False)` and
`admit(deadline: float, *, detail: bool = False)`; z>fallback determines detail.
Include normalized product identity in acquisition/cache keys before kind/token/
z/x/y; retain all current coalescing, capacity and security guarantees.

- [ ] Write regressions for accepted z2/z7 edges and rejection of z1/z8,
      negative, fractional/boolean values, x/y equal to 2\*\*z, leading zeros
      and signs. Transport rejection must occur before a DNS spy is called. Pin
      strict normalized capabilities/provenance/schema and reject unknown
      fields. Test source-neutral template/product admission before DNS and
      source-change cache isolation with identical time/XYZ; frontend parsing
      accepts the normalized alternative-source/max-zoom fixture.
- [ ] Add fake-clock saturation tests: 30 detail attempts block the 31st; coarse
      still uses remaining overall budget, the 91st total attempt fails; every
      numeric retry counts. Two active detail tasks leave two coarse slots;
      queued coarse demand precedes detail; pending never exceeds 32.
      Cancellation/disable/shutdown release leases without invalidating others.
- [ ] Run affected backend tests and
      `frontend_weather_tests src/services/overview-weather.test.ts`; expect RED
      on z7/new contracts.
- [ ] Implement canonical raw-coordinate validation before conversion, expand
      provider transport grammar with independent 2\*\*z bounds, isolate adapter
      assumptions, emit normalized capabilities and enforce priority admission.
      Preserve public-IP pinning, TLS, frame admission, five-second provider
      deadlines, coalescing and cooldowns.
- [ ] Repeat tests to PASS, including existing transport/acquisition/lifecycle
      tests; commit `feat: deliver bounded higher-zoom weather tiles`.

## Task 2: Camera-driven bounded demand

**Files:** Selector/observer/tests, Overview page and map-controller tests.

**Interfaces:** Produce
`selectDetail(snapshot, capabilities, previous): DetailDemand` consumes
`CameraSnapshot`, normalized `WeatherCapabilities` and `DetailDemand | null`;
`DetailDemandStabilizer.update(demand, nowMono)` takes `DetailDemand` and
monotonic milliseconds, returning `DetailDemand | null` only after stability.
Observer consumes `capabilities: WeatherCapabilities | null`, owns the sampling
clock, captures actual canvas camera snapshots and runs selection/stabilization.
Its `onDemand(demand: DetailDemand): void` prop forwards stabilized
`DetailDemand`.

- [ ] Write independent geometry tests with known globe landmarks, perspective
      projection/view offset and drawing-buffer changes. Assert <=8 canonical
      visible keys, zoom<=manifest max, antimeridian wrap, Mercator limit, no
      back hemisphere or near-horizon-only refinement; regional zoom yields
      level >2.
- [ ] Add fake-clock tests: 399 ms gives no changed demand, 400 ms does;
      oscillation inside 20 percent keeps level, identical keys cause no event,
      stable overlap is retained, rapid movement replaces pending selection.
      Native follow/reset/rotate/zoom matrices and controls remain unchanged.
- [ ] Add `normalized source capabilities drive selection`: fixture source
      `fixture-radar`, max zoom 5, the same supported 512px schema and only
      dashboard API URLs. Expect level<=5 and no provider-domain requests or
      provider URL parsing. Reject unsupported schemas before acquisition.
- [ ] Run
      `frontend_weather_tests src/pages/weather/weather-detail-selection.test.ts`
      and the existing map-controller test; expect RED on missing selector.
- [ ] Implement sphere intersections and projected tile footprint ranking using
      the actual matrices; choose finest fitting level or bounded coarser demand
      from manifest capabilities. Observer samples at most 4 Hz with no
      alternate camera/controls or polling outside the canvas. Suspend/clear
      pending demand with inactive context.
- [ ] Repeat tests to PASS; commit
      `feat: select weather detail from native camera`.

## Task 3: Shared browser budgets and frame-owned paired detail

**Files:** Work/detail owners/tests, atlas/controller/state/hook/status.

**Interfaces:** Produce
`WeatherWork.run<T>(kind, signal, operation): Promise<T>` takes
`kind: 'coarse' | 'detail'`, `signal: AbortSignal` and
`operation: () => Promise<T>`. Also produce
`reserveDecoded(bytes: number): () => void` (throws when unavailable). One
instance is shared by atlas/detail owners. Produce
`WeatherDetailOwner.setContext(context: DetailContext | null): void`,
`setDemand(demand: DetailDemand): void`, `snapshot(): readonly DetailPair[]`,
`subscribe(listener: () => void): () => void`, `dispose(): void`. Controller
owns context/generation tied to the displayed manifest and its full normalized
identity; the contract defines the required identity fields and invalidation.

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
      publish. Change source/provenance/product/schema while XYZ/time match;
      assert cancellation, bitmap closure, cache/slot invalidation and a new
      coarse identity, without extending freshness. Preserve 20/60-minute
      policy.
- [ ] Run all weather atlas/controller/work/detail unit tests; expect RED on
      shared limits and missing context owner.
- [ ] Refactor atlas operations through shared work owner, evict detail bitmaps
      when coarse staging needs decoded reservations, and implement matched
      detail pairs/cache, reserve bitmap bytes before decoding and release on
      every path. Expose displayed provenance/attribution and context via the
      hook/view/status; publish null when acquisition is disallowed. Bound
      pending demand to one selection.
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
      200 ms entry fade and one-normalized-texel transition to matching base.
      Packing consumes validated schema/tile-size capabilities, never source
      IDs. Blend premultiplied radar weighted by coverage, using conservative
      absent mask combination. Use candidate radar factor 0.40 and independent
      hatch 0.17; retain depth settings, ignored raycast and native geometry.
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
      changed frame/source and late completions. Add the normalized alternative
      source/capability fixture to production browser acceptance; no live
      provider. Seed aircraft/track, active route, POIs and labels over
      precipitation regions; keep telemetry/GEPs/borders.
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

[results]: ../../reports/2026-10-06-weather-source-comparison-results.md
