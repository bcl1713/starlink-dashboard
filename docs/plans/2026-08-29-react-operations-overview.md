# React Operations Overview Implementation Plan

<!-- markdownlint-disable MAX_LINES -->

> **For Hermes:** Use the `subagent-driven-development` skill to implement this
> plan task-by-task. Preserve test-first ordering and stop at every review gate.

**Goal:** Add a TypeScript/React `/overview` landing page that matches the
operational meaning and full layer/functionality of Grafana's Fullscreen
Overview while both products remain available for a measured dual-run.

**Architecture:** Mission Planner owns the React page, client-side bounded
30-minute buffers, controls, and visualization state. FastAPI owns bounded,
typed monitoring contracts and all Prometheus/RainViewer access; the browser
must not receive an arbitrary PromQL or caller-selected upstream proxy. Existing
same-origin operational APIs remain in use where their semantics already match.
Grafana and its dashboard remain untouched in this PR and supply the parity
oracle during acceptance.

**Tech Stack:** Python 3.13, FastAPI/Pydantic, `httpx`, Prometheus HTTP API,
TypeScript 5.9 strict mode, React 19, React Router, TanStack Query, React
Leaflet, Leaflet, uPlot, Vitest/Testing Library, Playwright, Docker Compose.

---

## 1. Scope, invariants, and source of truth

### In scope

- Add `/overview` and make `/` redirect to it with `replace`.
- Preserve all existing management URLs and browser history.
- Match only
  `monitoring/grafana/provisioning/dashboards/fullscreen-overview.json` at the
  restored-dev base `07593c69040ad447000bf526d6453ec5c6faacfa`.
- Add typed and bounded FastAPI monitoring/history contracts.
- Add a same-origin RainViewer tile byte proxy and the minimum CSP expansion
  needed for the ArcGIS World Imagery basemap.
- Provide configurable dashboard refresh (default one second), manual refresh,
  freshness/staleness state, configurable clocks with mandatory UTC, and radar
  enabled by default with a persistent user toggle.
- Deliver full functional parity at all accepted widths through responsive
  stacking and disclosure; disclosure may reduce visual density, never remove
  data, controls, layer state, or accessible alternatives.
- Run React and Grafana side by side and collect parity evidence.

### Explicitly out of scope

- Removing, disabling, redirecting, or changing the Grafana service, image,
  volume, plugins, dashboard provisioning, credentials, tests, or port.
- Matching `overview.json`, `network-metrics.json`, `position-movement.json`, or
  any Grafana dashboard other than Fullscreen Overview.
- Adding an arbitrary PromQL endpoint, caller-provided upstream URL, WebSocket,
  or new container.
- Reintroducing the retired HCX/CommKa overlay.
- Changing the existing mission-planning business workflows.

### Binding baseline and exact-head rule

Before implementation and again immediately before final evidence, record:

```bash
cd /home/brian/starlink-dashboard-react-overview
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor 07593c69040ad447000bf526d6453ec5c6faacfa HEAD
python -m pytest tools/tests/test_fullscreen_overview_dashboard.py -q
```

Expected baseline evidence: clean feature branch, ancestor command exits `0`,
and the existing Fullscreen Overview contract passes. Each evidence bundle must
name the exact tested PR-head SHA. After the final implementation commit, run
all acceptance commands on that exact SHA with a clean tree; do not append a
commit without rerunning the affected gates. The Grafana JSON and its tests are
read-only parity inputs in this PR.

## 2. Parity contract

### Dashboard composition and panel semantics

The React page must retain all eleven Grafana panel concepts:

1. Four 24-hour clocks with seconds and explicit offset/zone labels. Defaults:
   `UTC` (label `UTC (Zulu)`), `America/New_York` (`Washington DC`),
   `Asia/Tokyo` (`Tokyo`), and `America/Chicago` (`Omaha`).
2. Dominant Current Position map.
3. POI Quick Reference, top five applicable future POIs.
4. Network Latency: current and rolling five-minute min/average/max; blue,
   green, orange, red; warning at 100 ms and critical at 200 ms.
5. Throughput: download positive/blue and upload negative/green in Mbps.
6. Ground Entry Point safe display label and map marker.
7. Obstruction gauge, 0–20%, warning at 5%, critical at 10%.
8. Packet loss history, 0–100%, warning at 2%, critical at 5%, with current,
   average, and maximum summaries.

Desktop hierarchy is clocks, approximately 75%-width map and right rail, then
GEP/obstruction/packet-loss bottom strip. Responsive layouts follow Section 8.

### Complete map layer parity and draw order

The map must expose a keyboard/touch-operable layer disclosure and render these
layers in this order (bottom to top):

1. Weather Radar (RainViewer), on by default, opacity `0.7`, zoom 0–7.
2. Planned Route — western segment, dark orange, width 2, opacity `0.9`.
3. Planned Route — eastern segment, dark orange, width 2.
4. Active X-band Link — normal, green, width 4.
5. Active X-band Link — warning, yellow, width 4.
6. Position History — western segments, blue, width 3, opacity `0.7`.
7. Position History — eastern segments, blue, width 3, opacity `0.7`.
8. Flight route/POI markers, dark-orange X plus name.
9. Satellites, purple marker plus name.
10. Mission events, yellow circle plus name.
11. Ground entry point, blue circle and `GEP` label.
12. Current position, green aircraft rotated by heading.

ArcGIS World Imagery is the basemap with `Tiles © Esri` attribution. Zoom,
mouse-wheel zoom, scale, measurement, attribution, fit-to-layers, feature
details, and a textual feature/layer summary are required. A basemap or radar
failure must not remove operational vector layers.

### Existing API ownership

Use origin-relative requests through
`frontend/mission-planner/src/services/api-client.ts`:

- `GET /api/status` — current telemetry.
- `GET /api/pois/etas?category=<comma-separated>` — filtered flight-route
  markers and POI table.
- `GET /api/pois/etas?category=satellite` — satellite markers.
- `GET /api/pois/etas?category=mission-event` — mission-event markers.
- `GET /api/route/coordinates/west` and `/east` — planned route.
- `GET /api/active-x-link?state=normal` and `?state=warning` — link geometry.
- `GET /api/weather/radar/rainviewer/{z}/{x}/{y}.png` — same-origin tile bytes
  after this plan's backend change.

Do not send the Grafana query-model fallback latitude, longitude, or speed to
`/api/pois/etas`; coordinator telemetry remains authoritative.

## 3. New API and DTO contracts

Create `backend/starlink-location/app/models/monitoring.py` with strict Pydantic
models (`extra="forbid"`) and UTC-aware datetimes:

```python
MonitoringMetric = Literal[
    "latitude_degrees",
    "longitude_degrees",
    "latency_ms",
    "throughput_down_mbps",
    "throughput_up_mbps",
    "packet_loss_percent",
]

class MonitoringSample(BaseModel):
    timestamp: datetime
    value: float | None

class MonitoringSeries(BaseModel):
    metric: MonitoringMetric
    samples: list[MonitoringSample]

class MonitoringHistoryResponse(BaseModel):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    range_seconds: int
    step_seconds: int
    series: list[MonitoringSeries]

class GroundEntryPointResponse(BaseModel):
    available: bool
    observed_at: datetime
    display: str | None
    city: str | None
    region: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
```

Do **not** expose the GEP public IP in the browser DTO. `display` comes from
`GroundEntryPoint.label`, not caller content or raw Prometheus labels.

Create `GET /api/monitoring/history` with:

- `range_seconds: int = 1800`, `ge=60`, `le=3600`.
- `step_seconds: int = 1`, `ge=1`, `le=60`.
- Server-selected `window_end=now(UTC)`; no browser-provided absolute time.
- One fixed internal Prometheus base URL from `PROMETHEUS_URL` defaulting to
  `http://prometheus:9090`.
- Exactly six allow-listed raw metric expressions:
  `starlink_dish_latitude_degrees`, `starlink_dish_longitude_degrees`,
  `starlink_network_latency_ms_current`,
  `starlink_network_throughput_down_mbps_current`,
  `starlink_network_throughput_up_mbps_current`, and
  `starlink_network_packet_loss_percent`.
- A server timeout, response-size/point ceiling of
  `6 * (range_seconds / step_seconds + 1)`, cancellation propagation, and no
  query text, hostname, URL, headers, or credentials accepted from a request.
- `NaN`, `+Inf`, and `-Inf` normalized to `null`; timestamps normalized to UTC;
  series always returned in the literal order above, including empty samples.
- `502` with a stable safe detail code for malformed/upstream error and `504`
  for timeout; never include internal URL or response bodies.

Create `GET /api/monitoring/ground-entry-point` returning
`GroundEntryPointResponse`. It reads `get_cached_ground_entry_point()` only and
returns HTTP 200 with `available=false` and null details when no cached value
exists; it must not trigger internet discovery on request.

Define matching TypeScript DTOs in
`frontend/mission-planner/src/types/monitoring.ts`. Also define dedicated DTOs
for the existing status, coordinates, active-link, and POI ETA payloads there;
do not reuse `src/types/poi.ts`, because the operational API returns `poi_id`
where the management type requires `id`. Validate external responses with zod at
the service boundary and reject malformed finite ranges/coordinates.

## 4. Refresh, continuity, freshness, and persisted preferences

- Dashboard refresh choices: `1s`, `2s`, `5s`, `10s`, `30s`, and paused. Default
  is `1s`; persist under versioned key
  `starlink.operations-overview.preferences.v1`.
- A manual Refresh button invalidates all current/overlay queries and performs
  history reconciliation once, even while paused. Disable duplicate clicks while
  that manual cycle is pending, retain the last valid render, and report
  completion/failure without moving focus.
- Fetch 30-minute history once on entry and on manual refresh. Poll current
  telemetry at the selected interval, append/de-duplicate by server timestamp,
  prune points older than 30 minutes, and reconcile history every 10 seconds. Do
  not download a full 30-minute range every second.
- Poll POIs and active link at selected cadence, route geometry every 5 seconds,
  GEP every 30 seconds, and radar according to the provider frame/cache policy.
  A selected slower cadence is the lower bound for dashboard-owned polls.
- On `document.hidden`, stop scheduled polling and timers that cause network
  traffic; preserve buffers and UI state. On visibility restoration, perform one
  coordinated refresh and resume without burst replay.
- Keep last valid panel/layer data during background fetch and partial failures.
  Never reset map viewport, selected POI categories, layer toggles, expanded
  disclosures, chart visibility, focus, or fullscreen styling on refresh.
- Every response's source/server timestamp updates per-source freshness. Show
  global last-success and localized source state. Define stale as
  `age > max(5 seconds, 3 * active refresh seconds)`; paused data is labeled
  `Paused — last updated …`, not stale merely because the operator paused.
- Distinguish initial loading, empty, stale, partial error, total error, and
  recovered. Recovery is announced once in a polite live region; never announce
  each one-second value tick.
- Clocks use a single injectable `now(): Date` source and one shared one-second
  timer. Preferences contain an ordered list of `{label, timeZone}`. UTC is
  immutable, always first, cannot be hidden or deleted, and is restored during
  migration if absent. Other IANA zones may be added, relabeled, reordered, or
  removed after `Intl.DateTimeFormat` validation. Default the four zones above;
  persist locally and test DST boundaries with a fake clock.
- Radar defaults to `true`, can be toggled from the layer disclosure, and is
  persisted. A failed radar layer shows a localized status and toggle/retry;
  vector layers continue.

## 5. International Date Line handling

Implement pure utilities in
`frontend/mission-planner/src/pages/OverviewPage/geometry.ts` and unit-test them
before map work:

- Normalize longitude into `[-180, 180)`.
- Detect an IDL crossing when adjacent normalized longitudes differ by more than
  180 degrees.
- Interpolate the latitude at `+180/-180`, end the current segment at one edge,
  and begin a new segment at the opposite edge. Preserve timestamps and stable
  order for history.
- Split every route-like geometry: planned route, position history, and each
  active-link state. Never connect the last point of one segment to the first
  point of another.
- Handle exact `180`, duplicate points, null/invalid samples, one-point input,
  repeated crossings, east-to-west and west-to-east movement.
- The backend history endpoint returns one canonical lat/lon history; React
  aligns latitude and longitude by exact timestamp and performs the split once.
  The duplicate eastern/western PromQL targets in Grafana are implementation
  plumbing, not an API contract.

## 6. File map

### Backend

- Create: `backend/starlink-location/app/models/monitoring.py`
- Create: `backend/starlink-location/app/services/prometheus_client.py`
- Create: `backend/starlink-location/app/api/monitoring.py`
- Modify: `backend/starlink-location/app/api/weather.py`
- Modify: `backend/starlink-location/app/services/weather_radar.py`
- Modify: `backend/starlink-location/main.py`
- Create: `backend/starlink-location/tests/unit/test_monitoring_models.py`
- Create: `backend/starlink-location/tests/unit/test_prometheus_client.py`
- Create: `backend/starlink-location/tests/unit/test_monitoring_api.py`
- Modify: `backend/starlink-location/tests/unit/test_weather_api.py`

### Frontend

- Modify: `frontend/mission-planner/package.json`
- Modify: `frontend/mission-planner/package-lock.json`
- Create: `frontend/mission-planner/vitest.config.ts`
- Modify: `frontend/mission-planner/src/App.tsx`
- Modify: `frontend/mission-planner/src/index.css`
- Modify: `frontend/mission-planner/nginx.conf`
- Create: `frontend/mission-planner/src/types/monitoring.ts`
- Create: `frontend/mission-planner/src/services/monitoring.ts`
- Create: `frontend/mission-planner/src/services/monitoring.test.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OverviewGrid.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OverviewControls.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/WorldClocks.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/ClockSettings.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/OperationalMap.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/LayerDisclosure.tsx`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/POIQuickReference.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/MetricChart.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/MetricSummary.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/ObstructionGauge.tsx`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/GroundEntryPointCard.tsx`
- Create: `frontend/mission-planner/src/pages/OverviewPage/useOverviewData.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/preferences.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/history.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/geometry.ts`
- Create: `frontend/mission-planner/src/pages/OverviewPage/formatters.ts`
- Create tests beside pure/component modules as `*.test.ts(x)`.
- Create: `frontend/mission-planner/tests/e2e/overview.spec.ts`
- Create: `frontend/mission-planner/tests/e2e/overview-continuity.spec.ts`
- Create: `frontend/mission-planner/tests/e2e/fixtures/overview.ts`
- Modify: `frontend/mission-planner/tests/e2e/api-origin.spec.ts`

Keep production TypeScript files near or below the repository's 300-line target;
split components rather than creating a monolithic dashboard page.

## 7. Test-first implementation tasks and commit boundaries

Every task below starts with a failing focused test, demonstrates the expected
failure, implements the smallest behavior, reruns the focus test, then runs the
listed local regression set. Do not combine commit boundaries merely because Git
permits it.

### Task 1: Separate the unit and browser test harnesses

**Files:**

- Create: `frontend/mission-planner/vitest.config.ts`
- Modify: `frontend/mission-planner/package.json`

**Baseline evidence:**
`npm ci --legacy-peer-deps && npm run build && npm run lint` passes at the
restored-dev feature head. Bare `npx vitest run` incorrectly collects the five
existing `tests/e2e/*.spec.ts` Playwright files; Playwright then rejects
`test.describe` inside Vitest. Two component files/three tests pass, while the
five browser files fail. Treat this only as harness debt, not an Overview
feature failure.

**Steps:**

1. Add a failing harness assertion (or demonstrate the baseline command) that
   proves unit discovery includes `src/**/*.{test,spec}.{ts,tsx}` but excludes
   `tests/e2e/**` and Playwright output directories.
2. Create a dedicated Vitest config with the React/Vite environment and an
   explicit unit-test include/exclude. Add
   `"test:unit": "vitest run --config vitest.config.ts"` to package scripts. Do
   not rename, import, or otherwise adapt Playwright specs for Vitest.
3. Run:

   ```bash
   cd frontend/mission-planner
   npm run test:unit
   npx playwright test --list
   ```

   Expected: unit tests run without collecting `tests/e2e`; Playwright lists
   browser tests independently. Neither command reports the cross-runner
   `test.describe` error.

4. Use `npm run test:unit -- <focused-path>` for all later Vitest steps and
   `npx playwright test ...` only for browser acceptance.
5. Commit: `test: separate frontend unit and browser suites`.

### Task 2: Freeze the parity oracle and fixtures

**Files:**

- Create: `frontend/mission-planner/tests/e2e/fixtures/overview.ts`
- Create:
  `frontend/mission-planner/src/pages/OverviewPage/parity-contract.test.ts`

**Steps:**

1. Encode deterministic nominal, no-route, sparse, stale, backend failure, radar
   failure, IDL, threshold-crossing, and recovery fixtures. Include all eleven
   panels and twelve map layers.
2. Add a test asserting the fixture's defaults against the inventory in Sections
   2–4 (30-minute range, 1-second refresh, four clocks, thresholds, category
   defaults `departure,arrival`, radar on).
3. Run:

   ```bash
   cd frontend/mission-planner
   npm run test:unit -- src/pages/OverviewPage/parity-contract.test.ts
   ```

   Expected RED: module/contract absent. After the fixture implementation,
   expected GREEN: all parity-contract tests pass.

4. Re-run
   `python -m pytest tools/tests/test_fullscreen_overview_dashboard.py -q` from
   repository root; expected unchanged PASS.
5. Commit: `test: define operations overview parity fixtures`.

### Task 3: Add strict monitoring models and allow-listed Prometheus client

**Files:** backend monitoring models/client and their unit tests from Section 6.

**Steps:**

1. Test exact model schema, UTC serialization, forbidden extra keys, stable
   series ordering, parameter bounds, fixed query map, exact
   `/api/v1/query_range` parameters, timeout, cancellation, malformed JSON,
   upstream error, empty results, point ceiling, and non-finite normalization.
2. Explicitly test that caller PromQL, URL, hostname, and headers cannot enter
   the client API.
3. Run focused tests and observe import failures:

   ```bash
   cd backend/starlink-location
   python -m pytest tests/unit/test_monitoring_models.py \
     tests/unit/test_prometheus_client.py -q
   ```

4. Implement strict Pydantic DTOs and a small async `httpx` client with the six
   constant expressions. Run again; expected PASS.
5. Run:

   ```bash
   python -m ruff check app/models/monitoring.py \
     app/services/prometheus_client.py \
     tests/unit/test_monitoring_models.py \
     tests/unit/test_prometheus_client.py
   ```

   Also run the repository's configured mypy command if present; expected no new
   diagnostics.

6. Commit: `feat(api): add bounded monitoring history client`.

### Task 4: Expose typed monitoring routes

**Files:** `app/api/monitoring.py`, `main.py`, API tests.

**Steps:**

1. Write TestClient tests for exact successful response heads/body fields,
   default and boundary parameters, 422 outside bounds, empty series,
   `available=false` GEP, safe available GEP, 502/504 mapping, no IP leakage,
   and router registration/OpenAPI response models.
2. Run focused tests; expected RED: 404/import failure.
3. Implement the router and include it in `main.py`.
4. Run focused tests; expected PASS. Then run:

   ```bash
   cd backend/starlink-location
   python -m pytest tests/unit/test_monitoring_api.py \
     tests/integration/test_health.py tests/integration/test_metrics_endpoint.py -q
   ```

5. Commit: `feat(api): expose typed monitoring endpoints`.

### Task 5: Proxy RainViewer bytes and lock CSP boundaries

**Files:** weather service/API/tests and Mission Planner Nginx config.

**Steps:**

1. Add tests for valid XYZ bounds, provider metadata failure, tile timeout,
   non-image/wrong content type, maximum body size, byte passthrough,
   `image/png`, bounded cache headers, and no redirect/`Location` header.
2. Add a config test asserting CSP `img-src` permits only `'self'`, `data:`,
   existing OSM, and `https://server.arcgisonline.com`; RainViewer must not be
   in CSP because FastAPI proxies it. Keep `connect-src` same-origin plus the
   existing WebSocket allowances; do not add Prometheus or Grafana.
3. Run focused tests; expected RED because endpoint returns 307.
4. Implement backend streaming/byte proxy with a fixed provider host obtained by
   the existing metadata service, strict tile validation, timeout and body cap.
   Add only ArcGIS to `img-src`.
5. Run weather/config tests; expected PASS. Manually verify with `curl -I` after
   Task 13 that the tile response is same-origin, not a redirect, has
   `X-Content-Type-Options: nosniff`, and that `/overview` includes the intended
   CSP.
6. Commit: `fix(weather): proxy radar tiles for browser CSP`.

### Task 6: Add frontend DTO validation and monitoring services

**Files:** frontend monitoring types/service/tests.

**Steps:**

1. Test exact API paths and query encoding, zod parsing, finite coordinate
   validation, null history samples, `poi_id` mapping, cancellation, and safe
   malformed-response failures. Assert requests are origin-relative.
2. Run focused Vitest; expected RED.
3. Implement DTO schemas and service functions only; do not add UI.
4. Run focused tests, `npm run lint`, and `npm run build`; expected PASS.
5. Commit: `feat(frontend): add typed overview data services`.

### Task 7: Implement pure time-series, metric, POI, and IDL utilities

**Files:** `history.ts`, `geometry.ts`, `formatters.ts` and colocated tests.

**Steps:**

1. Write tests for timestamp alignment, de-duplication, chronological ordering,
   30-minute pruning, maximum sample count, five-minute latency min/mean/max,
   upload sign inversion, packet-loss summaries, ETA formatting/sorting,
   exclusion of `already_passed` and `behind`, top-five limit, ETA urgency at
   900/1800/3600 seconds, and all IDL edge cases in Section 5.
2. Include a fake `now` parameter in every time-dependent utility; no tests may
   wait on wall-clock time.
3. Run focused tests; expected RED.
4. Implement pure functions, rerun; expected PASS.
5. Commit: `feat(frontend): add overview metric and geometry utilities`.

### Task 8: Implement persisted clocks, refresh, and radar preferences

**Files:** preferences, clocks/settings/controls and tests.

**Steps:**

1. With fake timers, test default clocks, 24-hour seconds, DST transitions,
   invalid IANA zone rejection, labels/offsets, immutable first UTC clock,
   preference migration, malformed localStorage fallback, refresh choices,
   default 1 second, paused state, radar default-on/toggle persistence, one
   shared timer, and timer cleanup on unmount.
2. Add keyboard and accessible-name tests for every control; enforce 44×44 CSS
   px touch targets in the responsive classes.
3. Run focused tests; expected RED, then implement and expect PASS.
4. Commit: `feat(frontend): add configurable overview controls and clocks`.

### Task 9: Implement continuity-aware data orchestration

**Files:** `useOverviewData.ts` and tests.

**Steps:**

1. Test per-source schedules, bootstrap/reconcile/append behavior, selected
   refresh cadence, manual refresh while paused, duplicate click suppression,
   hidden-tab suspension, visibility catch-up, abort on unmount, localized
   errors, retained last-good data, stale threshold, paused label, recovery
   announcement, and preservation of user state.
2. Use fake timers and deterministic query mocks. Assert five scheduled
   refreshes plus one manual refresh do not produce an undefined last-good
   snapshot between valid responses.
3. Run focused tests; expected RED, then implement and expect PASS.
4. Commit: `feat(frontend): orchestrate resilient overview refresh`.

### Task 10: Build charts, summaries, gauge, GEP, and POI presentation

**Files:** metric/POI/GEP components and tests; add `uplot` lockfile changes.

**Steps:**

1. Add `uplot` with `npm install uplot` so both package files change together.
2. Test labels, units, thresholds plus text (not color alone), legends,
   current/min/max/mean, upload-negative rendering, null gaps, accessible chart
   summaries/data tables, mobile disclosure, top-five POI card/table parity,
   empty/loading/error/stale states, and retained last-good values.
3. Run focused tests; expected RED, implement components, then expect PASS.
4. Run `npm run lint && npm run build`; expected PASS.
5. Commit: `feat(frontend): render overview metrics and POIs`.

### Task 11: Build the operational map with all layers

**Files:** map/layer components, assets if required, and tests.

**Steps:**

1. Test exact twelve-layer names/order/default visibility/styles, ArcGIS URL and
   attribution, radar toggle/opacity/zoom, western/eastern IDL segments,
   aircraft heading transform, feature details, fit-to-layers only on first
   valid load or explicit action, scale/measure/zoom controls, textual
   equivalent, and independent layer failure.
2. Test that five data rerenders plus manual refresh preserve the Leaflet map
   instance, viewport, selected feature, expanded disclosure, and layer
   instances; no `fitBounds` occurs in background refresh.
3. Run focused tests; expected RED, implement, then expect PASS.
4. Commit: `feat(frontend): add full-parity operational map`.

### Task 12: Compose the responsive page, routing, and accessibility

**Files:** overview page/grid, `App.tsx`, `index.css`, component tests.

**Steps:**

1. Test `/` redirects with replacement to `/overview`, Overview appears first in
   navigation, brand links to `/overview`, `aria-current` is present, all old
   routes still resolve, and browser Back behavior is preserved.
2. Test one `main`, skip link, logical headings, visible focus, keyboard
   fullscreen entry/exit, fullscreen failure fallback to kiosk styling, reduced
   motion, polite status live region, and no one-second live spam.
3. Implement desktop grid and responsive stacking/disclosure from Section 8.
   Fullscreen API invocation must occur only from a user gesture; exiting must
   retain dashboard state.
4. Run component suite, lint, and build; expected PASS.
5. Commit: `feat(frontend): add operations overview landing page`.

### Task 13: Add browser acceptance and temporal evidence

**Files:** Playwright overview specs, fixtures, API-origin spec, optional
checked in screenshot baselines only if repository convention approves them.

**Steps:**

1. Route all API/tile responses in Playwright to deterministic fixtures. Assert
   all eleven panel concepts and twelve map layers, controls, filters, states,
   accessibility names, same-origin requests, no console/page errors, and no
   failed first-party requests.
2. Parameterize exact viewports: `1920x1080`, `1280x800`, `1024x768`,
   `768x1024`, `390x844`, and `320x568`.
3. For every viewport assert
   `document.documentElement.scrollWidth <= document.documentElement.clientWidth`.
   Capture named full-page and initial viewport screenshots.
4. At 1920×1080 additionally prove primary content hierarchy and no below-fold
   loss except secondary detail. At 768/1024 prove map precedes full-width POI
   and charts and is at least 320 px high. At 390/320 prove status-first order,
   UTC immediate visibility, cards/disclosures retain every function, and map
   interaction can be entered/exited without scroll trapping.
5. Run the continuity scenario at 1-second cadence for five scheduled refreshes
   plus manual refresh. At each frame record DOM/screenshot, request timestamps,
   chart point counts, Leaflet instance/viewport, selected filters/layers,
   focus, and console output. Expected: no blanking, count regression, state
   reset, focus loss, layout jump, or request burst.
6. Run nominal, empty, partial/total error, stale, recovery, IDL,
   threshold-crossing, radar failure, basemap failure, and device rotation.
7. Add automated accessibility checks available in the project plus manual
   keyboard-only, screen-reader smoke, WCAG 2.2 AA contrast, reduced-motion, and
   44×44 touch-target evidence.
8. Run:

   ```bash
   cd frontend/mission-planner
   npm run build
   npx playwright test tests/e2e/overview.spec.ts \
     tests/e2e/overview-continuity.spec.ts tests/e2e/api-origin.spec.ts
   ```

   Expected: all projects/scenarios PASS and artifacts identify exact HEAD.

9. Commit: `test: add operations overview browser acceptance`.

### Task 14: Rebuild and verify the real dual-run stack

**Files:** no feature files unless a proven defect requires returning to its own
test-first task/commit.

**Steps:**

1. Because backend Python changed, use the binding clean rebuild sequence:

   ```bash
   cd /home/brian/starlink-dashboard-react-overview
   docker compose down
   docker compose build --no-cache
   docker compose up -d
   docker compose ps
   curl --fail http://localhost:8000/health
   curl --fail http://localhost:5173/overview
   curl --fail 'http://localhost:8000/api/monitoring/history?range_seconds=60&step_seconds=1'
   curl --fail http://localhost:3000/api/health
   ```

   Expected: `starlink-location`, Prometheus, Grafana, and Mission Planner are
   healthy/running; both UIs respond; history contains every named series.

2. Run Grafana and React side by side over the same 30-minute simulation window.
   Capture current metric deltas, chart extrema/rolling values, route/history,
   position/heading, GEP, X-link geometry, POI ordering, and layer visibility.
   Differences require a disposition: defect fixed and retested, or explicit
   owner-approved semantic equivalence. Silence is not a disposition.
3. Exercise an IDL route, backend interruption/recovery, internet/radar outage,
   and manual refresh. Record network transfer rate and browser memory over a
   representative soak; verify bounded history does not grow after 30 minutes.
4. Run full exact-head gates:

   ```bash
   git status --short
   git rev-parse HEAD
   python -m pytest tools/tests/test_fullscreen_overview_dashboard.py -q
   cd backend/starlink-location && python -m pytest -q
   cd ../../frontend/mission-planner && npm run lint && npm run build
   npm run test:unit
   npx playwright test
   cd ../.. && pre-commit run --all-files
   git diff --check
   ```

5. Store command logs, screenshots, traces, accessibility notes, and parity
   table in the PR evidence, not as unexplained generated repository files.
6. Cleanup even after failure:

   ```bash
   cd /home/brian/starlink-dashboard-react-overview
   docker compose logs --no-color > /tmp/react-overview-compose.log
   docker compose down --remove-orphans
   docker compose ps
   ```

   Expected final runtime evidence: no project containers or orphaned preview
   servers remain; Playwright's configured web server has exited; ports used by
   this work are no longer held by test processes. Do not use `-v`, because
   deleting operational volumes is not test cleanup.

7. No commit unless verification reveals a necessary change; route fixes back to
   their owning task and rerun exact-head gates.

## 8. Responsive acceptance details

### 1920×1080

- Four clocks visible together; map is largest region; POI/latency/throughput
  rail remains legible; GEP/obstruction/packet-loss strip visible.
- Primary operations fit one viewport; only clearly secondary details may
  require scrolling.
- Planning navigation is present but subordinate; fullscreen is keyboard
  operable and state-preserving.

### 1280×800 and 1024×768

- No page overflow. Clocks wrap deliberately. Map precedes detail and remains at
  least 320 px high. Summary values remain adjacent to or directly after it.
- Cards/charts become full width as needed; a wide table may scroll only inside
  an explicitly labeled region.

### 768×1024

- Compact navigation and clocks remain reachable. Controls are at least 44×44.
- Map, summaries, POIs, and charts stack in that priority; disclosures are
  obvious and dismissible.

### 390×844 and 320×568

- Initial viewport communicates connection/freshness, current route/position
  state, UTC, and highest-priority network state.
- Clock list keeps UTC directly visible; other clocks are fully available via a
  labeled disclosure.
- Map supports normal page scrolling until explicit map interaction is enabled.
- POI cards retain ETA, name, category/type, and urgency.
- Charts may initially show textual current/min/average/max summaries, but a
  keyboard/touch disclosure exposes the full chart and accessible data table.
- The complete layer list, radar control, filters, feature details, retry,
  refresh, and settings remain available. Rotation preserves all state.

## 9. Security, privacy, and CSP acceptance

- Browser traffic remains same-origin `/api/...`; no direct Prometheus, Grafana
  datasource proxy, RainViewer host, or internal Docker hostname.
- Monitoring query templates are constants. Validate range/step before the
  upstream call, cap returned points/body, apply timeouts, cancel disconnected
  requests, redact upstream details, and retain the existing rate limiter where
  appropriate.
- No public IP in the frontend GEP contract, logs, screenshots, tooltips, or
  accessibility text. Display fields render as React text, never HTML.
- Validate coordinates, values, labels, URLs, and IANA zones at trust
  boundaries. Reject non-finite values and do not use `dangerouslySetInnerHTML`.
- CSP adds only the exact ArcGIS HTTPS origin to `img-src`. Radar is proxied.
  Preserve `object-src 'none'`, `frame-ancestors 'none'`, `form-action 'self'`,
  `base-uri 'self'`, and fullscreen permissions. Do not broaden `connect-src`.
- Verify security headers on successful SPA, API, and tile responses and verify
  browser console has no CSP violations in every acceptance viewport.

## 10. Documentation impact routed independently

Documentation must be reviewed/routed as an independent docs workstream rather
than buried inside a feature commit. It may be a separate docs-only PR targeting
`dev`, linked to the implementation PR, but must merge before operator rollout.
Do not edit these during core code tasks:

- `docs/setup/quick-start.md` and installation verification/access URLs.
- `docs/setup/configuration/environment-variables.md` for `PROMETHEUS_URL` if it
  becomes operator-configurable.
- `docs/grafana-configuration.md` and `docs/grafana-dashboards.md` to describe
  dual-run status, **not** retirement.
- `docs/troubleshooting/services/grafana.md` to retain Grafana support.
- `docs/troubleshooting/services/backend.md`, monitoring/data diagnostics, and
  CSP/radar troubleshooting.
- `monitoring/README.md`, `monitoring/docs/README.md`, and
  `monitoring/docs/services-overview.md` for React Overview and Grafana URLs.
- Mission/operator monitoring and incident-response SOPs discovered by a fresh
  link/reference search.
- API documentation/OpenAPI examples for `/api/monitoring/history` and
  `/api/monitoring/ground-entry-point`.

Docs acceptance runs Markdown lint, filename conventions, and link checks:

```bash
pre-commit run --all-files
python -m pytest tools/tests/test_docs.py tools/tests/test_link_checker_config.py -q
python tools/check_filename_convention.py
```

Docs must say `/overview` is the default, list refresh/freshness and clock/radar
controls, explain paused/stale/error states, and state plainly that Grafana is
still deployed during dual-run.

## 11. PR, rollout, and rollback

### PR rules

- Rebase/update from current `dev`; preserve
  `07593c69040ad447000bf526d6453ec5c6faacfa` as an ancestor and resolve drift
  before evidence. If `dev` moved, rerun the baseline contract and all
  exact-head gates after update.
- Open `feature/react-operations-overview` **to `dev`, never `main`**. Verify
  the GitHub PR base explicitly (`gh pr view --json baseRefName,headRefName`)
  and require `baseRefName == "dev"` before review/merge.
- Keep commits at the boundaries above. No generated evidence, unrelated
  formatting, Grafana JSON/service changes, or retirement work.
- Require backend/API, frontend, browser/accessibility, security/CSP, and
  operator parity reviewers. Link the independently routed docs PR.
- Never merge on stale evidence: CI and manual acceptance SHA must equal the PR
  head. Merge to `dev` only after dual-run parity is approved.

### Rollout

1. Deploy to a representative simulation environment with Grafana unchanged.
2. Verify `/` and `/overview`, direct links to all old routes, backend health,
   Prometheus history, CSP, tile behavior, and Grafana availability.
3. Run side-by-side parity and a bounded soak; keep Grafana as the documented
   fallback.
4. Promote the React route as default on `dev` only after evidence passes.
5. Observe API latency/error rate, Prometheus query load, browser
   memory/network, stale frequency, tile failures, and operator feedback before
   any broader promotion.

### Rollback

- Preferred code rollback: revert the overview PR on `dev` and rebuild
  `starlink-location` and `mission-planner` with the required no-cache sequence.
- Immediate operational fallback: navigate operators to Grafana at port 3000; it
  remains deployed and unchanged.
- Verify rollback with health checks, old management routes, Grafana dashboard,
  and absence of `/api/monitoring/*` consumers. Do not delete Prometheus or
  Grafana volumes and do not remove new endpoints independently while the
  deployed frontend still calls them.
- If only radar/ArcGIS is failing, disable radar in the user control and retain
  vector operations; do not roll back telemetry merely for a third-party tile
  outage.

## 12. Separate future Grafana-retirement gate

Grafana retirement is a **new, separately scoped follow-up PR** to `dev`. This
implementation PR must not perform even preparatory deletions. Open retirement
work only after all of the following are documented and approved:

1. Every clock, panel, map layer, filter, threshold, time window, control, and
   accessible alternative has a React equivalent or explicit owner-approved
   retirement.
2. All deterministic states and all six exact viewport sizes pass.
3. Five refreshes plus manual refresh preserve map/chart/filter/focus state.
4. Existing mission, route, POI, satellite, import/export, and configuration
   workflows are regression-clean.
5. React has no Grafana endpoint, plugin, session, datasource-proxy, dashboard,
   or asset dependency.
6. A production-representative soak establishes acceptable update latency,
   browser memory/network, Prometheus load, and interruption recovery.
7. Operator sign-off, rollback drill, docs/SOP migration, bookmark/link audit,
   and observability replacement are complete.
8. The team explicitly decides whether retirement covers only Fullscreen
   Overview or every remaining Grafana dashboard; service removal requires the
   latter.

Only then may the follow-up inventory and remove, with test-first deployment
changes:

- `grafana` service and `grafana_data` from `docker-compose.yml`.
- Grafana from `deployment/portainer-ghcr-compose.yml` and publish workflows.
- Any deployment Grafana image/Dockerfile, plugin installation, provisioning,
  dashboards, datasources, custom icons, ports, passwords, and firewall rules.
- Grafana-specific health checks, tooling, tests (including
  `tools/tests/test_fullscreen_overview_dashboard.py`,
  `test_grafana_backend_proxy_runtime.py`, and `test_grafana_compose.py`) only
  after equivalent React/API contracts replace their coverage.
- Setup, verification, troubleshooting, architecture, monitoring, incident, and
  operator documentation.

Prometheus remains. The retirement PR must include its own rollout/rollback,
prove no production references remain, and target `dev`, never `main`. Until
that gate is passed and that separate PR merges, Grafana is the live fallback;
removing it early would convert confidence into theatre, which is rarely an
operational improvement.
