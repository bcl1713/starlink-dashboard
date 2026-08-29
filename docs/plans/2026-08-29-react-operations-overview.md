# React Operations Overview Implementation Plan

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

## Scope, invariants, and source of truth

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

## Parity contract

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

## Ordered implementation roadmap

The requirements and executable steps continue in these ordered supporting
plans. Implement them in order; task numbers and commit boundaries are
continuous across files.

1. [Contract and API](react-operations-overview/01-contract-and-api.md) — strict
   monitoring contracts, Prometheus and weather boundaries, DTO validation, IDL
   utilities, exact file map, and Tasks 3–6.
2. [Dashboard UI](react-operations-overview/02-dashboard-ui.md) — continuity,
   clocks, configurable refresh, radar preferences, responsive/mobile parity,
   charts, map, routing, and Tasks 7–12.
3. [Runtime and browser acceptance](react-operations-overview/03-runtime-and-browser-acceptance.md)
   — exact-head Playwright evidence, real dual-run verification, cleanup,
   security/CSP acceptance, and Tasks 13–14.
4. [Docs, rollout, and retirement](react-operations-overview/04-docs-rollout-and-retirement.md)
   — independent documentation review, the development PR policy, rollout and
   rollback, and the separate future Grafana-removal gate.

Each supporting plan inherits this master plan's goal, architecture, technology
stack, scope exclusions, baseline SHA rule, and Grafana-as-parity-oracle rule.

## Test-first foundation and commit boundaries

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
2. Add a test asserting the fixture's defaults against the inventory in the
   [parity contract](#parity-contract), the
   [API contract](react-operations-overview/01-contract-and-api.md), and the
   [refresh/preferences contract](react-operations-overview/02-dashboard-ui.md)
   (30-minute range, 1-second refresh, four clocks, thresholds, category
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
