# Phase 3: React Operations Overview Runtime and Browser Acceptance

> **For Hermes:** Start after Phase 2. Evidence is valid only for the exact
> clean PR-head SHA under test; rerun affected gates after any commit.

This phase proves temporal continuity, every accepted viewport, real dual-run
parity, runtime cleanup, and the security/CSP boundary. Use the
[responsive acceptance matrix](02-dashboard-ui.md#responsive-acceptance-details)
and the
[master exact-head rule](../2026-08-29-react-operations-overview.md#binding-baseline-and-exact-head-rule).

## Browser and runtime tasks

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

## Security, privacy, and CSP acceptance

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
