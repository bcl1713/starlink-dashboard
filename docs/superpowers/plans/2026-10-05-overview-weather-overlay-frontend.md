# Overview weather frontend and acceptance tasks

Read the [master plan](2026-10-05-overview-weather-overlay.md) and approved spec
first. B/F use its path aliases. Unit commands run from F; commits from root.

## Task 4: Configuration and shared settings

**Files:** Create F/src/services/overview-weather.ts,
F/src/hooks/api/{useOverviewWeatherSettings.ts,useUpdateOverviewWeatherSettings.ts},
F/src/pages/weather/OverviewWeatherSettingsCard.tsx, and adjacent
.test.ts/.test.tsx files. Modify F/src/pages/ConfigurationPage.tsx Overview-tab
content and its existing .test.tsx file; keep the force-mounted tab pattern.

**Interfaces:** Match Task 1 DTOs and ReadyWeatherManifest narrowing. Produce
overviewWeatherApi.getSettings(signal?: AbortSignal) ->
`Promise<WeatherSettings>`, updateSettings(update: { enabled: boolean }) ->
`Promise<WeatherSettings>`, and getFrame(signal?: AbortSignal) ->
`Promise<WeatherManifest>`. Produce WeatherSettingsObservation = { settings:
WeatherSettings; receivedAtMono: number }. useOverviewWeatherSettings() returns
the existing query result pattern with observation data;
useUpdateOverviewWeatherSettings() returns a mutation accepting { enabled:
boolean } and publishing confirmed observation data. Produce
OverviewWeatherSettingsCard(): ReactElement.

- [ ] **Step 1: Write failing API, hook, and Configuration tests.**

```tsx
it("keeps weather available when the independent clock card fails", async () => {
  renderConfigurationWithClockFailureAndWeatherOff();
  const control = await screen.findByRole("switch", {
    name: "Precipitation radar",
  });
  expect(control).not.toBeChecked();
  await user.click(control);
  expect(weatherPut).toHaveBeenCalledWith({ enabled: true });
  expect(weatherFrameGet).not.toHaveBeenCalled();
});
```

Pin strict DTO parsing including null/unknown fields, invalid ready templates
and off/unavailable variants; application-relative templates only. Test visible
5-second settings polling, hidden pause, reconnect/focus read, serialized saves,
cancelled obsolete reads, older revisions discarded without trust renewal,
idempotent confirmed responses, and failed-save feedback preserving state. Use
existing component/query harnesses; render actual switch semantics.

- [ ] **Step 2: Run RED.**

```bash
npm run test:unit -- src/services/overview-weather.test.ts src/hooks/api/useOverviewWeatherSettings.test.ts src/hooks/api/useUpdateOverviewWeatherSettings.test.ts src/pages/weather/OverviewWeatherSettingsCard.test.tsx src/pages/ConfigurationPage.test.tsx
```

Expect missing modules or unmet control/revision assertions.

- [ ] **Step 3: Implement the API adapter, observation hooks, and card.**

Use existing fetch/error/query conventions and strict parsing. Validate
templates against Task 3 routes, rejecting external URLs. Poll visible documents
only; timestamp accepted observations with performance.now(), fence older
revisions, serialize mutations, cancel obsolete reads before publication.
Weather card is independent of clock errors. Switch: **Precipitation radar**;
describe automatic precipitation on all Overview displays; show
loading/saving/confirmed/error states. Configuration never acquires images.

- [ ] **Step 4: Run GREEN.** Repeat Step 2; all cases pass.
- [ ] **Step 5: Commit.** Stage these files only. Commit:
      `feat: configure shared Overview precipitation radar`.

## Task 5: Refresh controller and complete atlases

**Files:** Create F/src/pages/weather/{weather-state.ts,weather-atlas.ts,
weather-controller.ts}, F/src/hooks/useOverviewWeatherLayer.ts and adjacent
.test.ts/.test.tsx files.

**Interfaces:** Consume Task 4 API/observation types. Produce
BrowserWeatherClock with nowMono() -> number, defaulting to performance.now().
WeatherLayerView has configuredEnabled: boolean, visible: boolean, state: "off"
| "loading" | "current" | "stale" | "unavailable", frameTimeMs: number | null,
ageMs: number | null, and atlas: WeatherAtlasPair | null. Produce
WeatherAtlasPair with radar and coverage HTMLCanvasElements, frameTimeMs,
coverageToken, coverageExpiresAtMs: number, and dispose(): void. Pairs own radar
and a reference-counted coverage lease; disposing one must not clear another
pair's shared mask.

Produce WeatherAtlasLoader(fetcher: typeof fetch, clock: BrowserWeatherClock),
with load(manifest: ReadyWeatherManifest, signal: AbortSignal) ->
`Promise<WeatherAtlasPair>` and dispose(): void. Produce WeatherController(api:
typeof overviewWeatherApi, loader: WeatherAtlasLoader, clock:
BrowserWeatherClock) with setSettings(observation: WeatherSettingsObservation |
undefined): void, setVisible(visible: boolean): void, reconnect(): void,
subscribe(listener: () => void): () => void, snapshot(): WeatherLayerView,
dispose(): void. Produce useOverviewWeatherLayer(): WeatherLayerView, owning its
controller lifetime.

- [ ] **Step 1: Write failing state, loader, controller, and hook tests.**

```ts
it("does not restart radar checks for same-revision settings polls", async () => {
  const h = enabledControllerHarness();
  for (let second = 5; second <= 300; second += 5) {
    await h.advanceSeconds(5);
    h.observeSettings({ enabled: true, revision: 1 });
  }
  expect(h.api.getFrame).toHaveBeenCalledTimes(2); // enable and 300 seconds
});
```

Other assertions: no default-off work; trust expires at 15000ms; disabled/newer
revision removes and aborts; reconnect/visible recovery checks promptly; a
change to Date.now or mission replay never alters original frame expiry. Pin
current at 1200000ms, stale immediately after, removal at 3600000ms; failed
refresh marks retained eligible imagery stale; unchanged success validates
without reloading tiles or extending expiry; malformed/stale revision responses
cannot revive it. Pin four concurrent decodes/fetches, 45000ms total deadline,
one pending load, all 16 radar plus complete coverage before publish, no mixed
frame tiles, and no immediate retry on unchanged failure. Coverage UTC-midnight
expiry removes imagery/checks manifest during a pending load. Superseded loads
release partial canvases/bitmaps; late createImageBitmap resolution closes once
and never publishes. Shared coverage survives disposal of the previous frame.
React strict mount/unmount leaves no subscriptions, timers, requests, or
retained canvas leases.

- [ ] **Step 2: Run RED.**

```bash
npm run test:unit -- src/pages/weather/weather-state.test.ts src/pages/weather/weather-atlas.test.ts src/pages/weather/weather-controller.test.ts src/hooks/useOverviewWeatherLayer.test.tsx
```

Expect missing interfaces or unmet timing/ownership assertions.

- [ ] **Step 3: Implement the declared controller and loader interfaces.**

Anchor real UTC to manifest generated_at_ms plus monotonic elapsed; preserve
frame_time_ms expiry and clamp tolerated future age to zero. Settings trust and
weather refresh use independent timers. Unknown settings hide status until a
confirmed enabled value; expired trust stops acquisition and shows unavailable
for previously enabled users. Fence every async publication by revision/load
generation; hide/pause aborts pending work, recovery requires fresh settings.

Load XYZ tiles into top-left-origin canvases at (x*512, y*512), validate decoded
512-square dimensions, preserve alpha, and close each bitmap after drawing.
Share immutable coverage through reference-counted cache leases. AbortSignal
cannot cancel native decoding: close any eventual bitmap without publication.
Only commit complete eligible pairs; failure releases partial work and retains
an eligible prior pair. Coverage expiry forbids old-mask display even if radar
is recent; schedule immediate manifest refresh. Do not tie camera/mission
changes to controller construction. Hook lifetime binds query observations,
browser visibility/network events, and snapshot subscription without core
loading gates.

- [ ] **Step 4: Run GREEN.** Repeat Step 2 and Task 4 hook suites; all cases
      pass.
- [ ] **Step 5: Commit.** Stage these files only. Commit:
      `feat: refresh complete weather atlases with bounded ownership`.

## Task 6: Globe surface and passive status

**Files:** Create
F/src/pages/weather/{weather-projection.ts,weather-textures.ts,
OverviewWeatherLayer.tsx,OverviewWeatherStatus.tsx,OverviewWeather.css} and
adjacent tests. Modify F/src/pages/OverviewPage.tsx and its layer/contract
tests.

**Interfaces:** Consume Task 5 WeatherAtlasPair/WeatherLayerView. Produce
weatherUvFromPosition(position: [number, number, number]) -> [number, number] |
null and mercatorUv(lat: number, lon: number) -> [number, number] | null.
Produce WeatherTextureOwner.replace(atlas: WeatherAtlasPair | null) ->
WeatherTextureSet | null and dispose(): void; WeatherTextureSet contains radar
and coverage THREE.CanvasTexture. Produce OverviewWeatherLayer({ atlas }: {
atlas: WeatherAtlasPair | null }): ReactElement | null and
OverviewWeatherStatus({ weather }: { weather: WeatherLayerView }): ReactElement
| null. Scene owns GPU resources, borrows CPU canvases.

- [ ] **Step 1: Write failing projection, texture, and component tests.**

```ts
it("maps the independently specified local globe coordinates", () => {
  expect(weatherUvFromPosition([1, 0, 0])).toEqual([0.5, 0.5]);
  expect(weatherUvFromPosition([0, 0, -1])).toEqual([0.75, 0.5]);
  expect(mercatorUv(90, 0)).toBeNull();
});
```

Add independent equator/mid/high-latitude, tile-edge, antimeridian orientation
cases; no precipitation beyond Mercator limit. Assert depthTest true, depthWrite
false, draw order before routes/markers, no pointer interception, unchanged
route geometry, no mipmaps, explicit texture/material disposal, and at most
three 2048-square RGBA textures (50331648 bytes). Test current/stale/
unavailable passive copy, UTC age/time, source attribution link and uncovered
legend; zero weather buttons, switches, or settings links on Overview.

- [ ] **Step 2: Run RED.**

```bash
npm run test:unit -- src/pages/weather/weather-projection.test.ts src/pages/weather/weather-textures.test.ts src/pages/weather/OverviewWeatherLayer.test.tsx src/pages/weather/OverviewWeatherStatus.test.tsx src/pages/OverviewPage.layers.test.tsx
```

Expect missing modules or unmet projection/resource assertions.

- [ ] **Step 3: Implement scene surface, ownership, and passive status.**

Longitude is atan2(-z,x), latitude from normalized y. Map u=fract(lon/360+0.5),
v=0.5-log(tan(pi/4+lat/2))/(2\*pi); Mercator limit is atan(sinh(pi)). Apply the
canvas-to-texture vertical orientation once. Use a separate transparent material
visible on the night side, alpha-preserving radar plus subtle uncovered hatching
including poles. Keep globe geometry/Suspense and route positions intact.
Texture replacement disposes superseded textures; no mipmaps. Serialize coverage
GPU replacement after pending radar commit/cancel so peak stays 48MiB. Add the
layer outside core texture loading and small passive responsive status with
linked RainViewer attribution; use existing theme tokens and fullscreen layout.

- [ ] **Step 4: Run GREEN.** Repeat Step 2 and existing Overview contract
      suites; all cases pass. Geographic pixels and real draw order are verified
      in Task 7.
- [ ] **Step 5: Commit.** Stage these files only. Commit:
      `feat: render Overview precipitation with passive weather status`.

## Task 7: Production acceptance and operator documentation

**Files:** Create tools/acceptance/overview-weather/{run.sh,compose.yml,
backend_fixture.py,provider_fixture.py,README.md} and
tools/tests/test_overview_weather_acceptance.py. Create
F/playwright.weather-acceptance.config.ts, its
F/src/test/overview-weather-acceptance-config.test.ts, and
F/tests/e2e/overview-weather-production.spec.ts with scene probe helpers.
Exclude production suite in F/playwright.config.ts. Add
docs/features/overview-weather.md, docs/api/endpoints/overview-weather.md;
crosslink docs/features/overview.md and docs/api-reference-index.md (<=300
lines).

**Interfaces:** Consume Tasks 1–6 unmodified production paths. Runner
tools/acceptance/overview-weather/run.sh accepts --check or an exact committed
SHA; exports WEATHER_ACCEPTANCE_BASE_URL and WEATHER_ACCEPTANCE_CONTROL_PATH for
Playwright. Isolated compose uses loopback ports 15278/18278 and task-owned
project/volume labels. Controls are a fixture JSON file, never a production API.

- [ ] **Step 1: Write failing runner/config tests and browser assertions.**

```ts
test("Configuration enables an already-open Overview", async ({ browser }) => {
  const overview = await openProductionOverview(browser);
  const canvas = await captureCanvasIdentity(overview);
  const config = await openProductionConfiguration(browser);
  await config.getByRole("switch", { name: "Precipitation radar" }).check();
  await expect(overview.getByText(/Weather data by RainViewer/)).toBeVisible();
  expect(await captureCanvasIdentity(overview)).toBe(canvas);
  await expect(overview.getByRole("switch")).toHaveCount(0);
});
```

Test clean-SHA archive, loopback validation, task-only cleanup, no preview
server, suite exclusion, image/source evidence, and resolver/TLS-only fixture
injection. Browser cases cover default off, two-window disable, real 300-second
refresh without reload, failure/expiry, atomic frames, coverage gaps, late
responses, toggle/unmount cleanup and core continuity. Independent geographic
landmarks check pixels at equator, high latitudes, tile edges and antimeridian;
exercise rotation, zoom, follow, reset, fullscreen/mobile and night visibility.
Actual ASGI/Nginx disconnects preserve siblings and exact-once writer cleanup.

- [ ] **Step 2: Run RED.** Run
      `python3 -m pytest -q tools/tests/test_overview_weather_acceptance.py`
      from root and
      `npm run test:unit -- src/test/overview-weather-acceptance-config.test.ts`
      from F; expect missing runner/config or unmet isolation assertions.
- [ ] **Step 3: Implement the runner, fixtures, browser suite, and operator
      docs.**

Follow overview-window-sync/ADSB acceptance runners: archive a clean tracked
candidate, fresh production images, real Nginx routes and main.app lifespan,
preserve actor Docker socket/context/proxy/CA trust, label all owned resources.
Provider fixtures inject validated public-IP resolution and synthetic TLS
streams only; production URL/framing/limits remain active. Generate PNGs using
stdlib struct/zlib from independent landmark coordinates; expose delay/failure/
frame controls through the isolated file. Fake-clock cases are explicitly
labeled; the real 300-second refresh case uses unmodified browser/backend
clocks. Reuse existing test scene probes, adding no product instrumentation or
credentials. Write feature/operator and endpoint docs including limitations,
shared control, freshness, source terms, cache limits and failure behavior.

- [ ] **Step 4: Commit the candidate, then verify GREEN and obtain fresh
      review.**

Commit named files:
`test: verify production Overview weather and document operation`. Run Step 2,
runner --check, focused suites, and `./tools/verify static`, backend, frontend
from root (set ACCEPTANCE_POLICY_BASE_SHA to an exact reachable ancestor for
static). Obtain fresh specification and quality/security review of the whole
branch before final acceptance. Fix findings, repeat affected checks, commit.
Run acceptance against that exact final SHA; retain screenshots, request counts,
resource evidence, logs, image IDs, source SHA and core continuity artifacts in
an ignored task-owned directory. Verify applicable CI on the same PR head. Any
later tracked change invalidates SHA evidence and requires a new candidate run.

- [ ] **Step 5: Publish evidence and finish delivery.** Push; update dev PR 278
      with behavior and exact-SHA validation, then mark ready after acceptance.
      Keep issue 144 open until implementation accepted. Use the
      branch-finishing skill; after merge clean only task-owned resources,
      worktree and branches. Preserve open-PR worktree and shared runtime
      configuration.
