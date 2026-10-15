# ADS-B Layer Acceptance Task

Read the [main plan](2026-10-03-overview-adsb-aircraft-layer.md), approved spec,
and both task files first. This task verifies the implemented feature; generating
this plan does not run these future product checks or authorize rollout.

## Task 7: Cross-window, rendered-browser and production-path acceptance

**Files:** Create
`frontend/mission-planner/tests/e2e/support/adsb-fixture.ts`,
`frontend/mission-planner/tests/e2e/overview-adsb.spec.ts`,
`overview-adsb-cross-window.spec.ts`, `overview-adsb-performance.spec.ts`,
`backend/starlink-location/tests/integration/test_overview_adsb_acceptance.py`,
`tools/acceptance/adsb/backend_fixture.py`,
`docs/api/endpoints/overview-adsb.md`, and
`docs/reports/2026-10-03-overview-adsb-aircraft-layer.md`.
Modify the existing browser support fixtures
`frontend/mission-planner/tests/e2e/support/overview-window-fixture.ts` and
`frontend/mission-planner/tests/e2e/support/traffic-path-fixture.ts` for
default-off ADS-B settings/traffic responses; retain all existing settings
fields, including `orbital_traffic_enabled`.
Modify `docs/features/overview.md`, `docs/features/system.md`,
`docs/api/endpoints/README.md`, and `docs/reports/README.md`.

**Interfaces:** Export
`installAdsbFixture(context: BrowserContext): Promise<AdsbFixtureController>`
from `adsb-fixture.ts`; the controller exposes
`setContacts(contacts: AdsbContact[]): void`,
`setSettings(settings: AdsbSettings): void`,
`failSettingsSave(fail: boolean): void`,
`failTraffic(fail: boolean): void`, and
`holdNextTraffic(): { release: () => void }`.
One context-level fake backend handles both pages with shared revisioned state;
do not synchronize independent page-local mocks or rely on shared React Query.
Held responses capture revision/content when requested, before later saves.
Use existing globe readiness and camera helpers and the tracked Playwright
configuration. Backend acceptance uses httpx controlled provider fixtures.

- [x] **Step 1: Add failing browser acceptance cases.** With separate
  Configuration and Overview pages, assert enable, include, exclude, mode,
  disable and saved-list edits converge without reload within 5s plus measured
  API response time. Explicit inclusion admits a civilian outside the own
  aircraft region; exclusion suppresses overlapping entries and own hex;
  included-only-empty renders none. Deliberately hold a traffic response across
  exclusion/disable and verify it cannot restore map/table rows. Save rejection
  retains confirmed state and exposes Configuration feedback. Refresh both pages
  and change mission: settings/lists persist independently.
  Freshness cases use a controlled clock with real observation timestamps at
  29.999/30/119.999/120s, requests failed or payload repeated, foreground resume,
  and fresh returning aircraft. Include entries remain saved throughout expiry.
  At 1920×1080 and native fullscreen, verify distinguishable glyphs, persistent
  included labels/fallbacks, noncolor stale indicator, tracked orientation and
  read-only details. Test marker click, camera drag, globe rear-side occlusion,
  Escape, keyboard access, dialog focus restoration, and selected expiry.
  Long/coincident included labels never become an aggregate. Also check current
  responsive layouts at 390×844 and 844×390 for control/dialog containment.
  Compare camera pose before/after settings and contact selection. Retain route,
  telemetry, history, metrics, links and warnings while toggling ADS-B.
  From Overview, use its keyboard identity to verify convergence with a fixture
  API response budget of 500ms:

  ```ts
  await expect(overview.getByRole('button', { name: 'Details for 00AB12' }))
    .toBeVisible({ timeout: 5500 });
  ```

- [x] **Step 2: Add backend restart and workload acceptance cases.** Test the
  real settings/traffic routers with the owned service and mocked upstream:
  settings survive stop/start, cache starts empty, source failures remain
  independent, and simultaneous clients do not multiply acquisitions. Use a
  controlled dataset of 2,000 military records distributed across hemispheres,
  with duplicates, 50 included identities and stale records; assert all eligible
  hexes remain available in the traffic response and Configuration table.
- [x] **Step 3: Verify tests can detect the contract violations.** Run new
  suites before final fixes. If earlier tasks already satisfy a case, temporarily
  mutate its revision check/expiry/occlusion in the isolated test workspace and
  confirm that case fails, then restore the source. Do not leave mutations or
  weaken assertions. Backend acceptance must not contact adsb.lol.
- [x] **Step 4: Complete browser fixture and performance checks.** Render the
  2,000-record workload alongside existing route/history/links for 30s of camera
  motion; capture frame-time percentiles, draw calls, contact/instance counts,
  DOM label counts and post-disable resource counts. Use a deterministic 50-label
  subset near the visible region to inspect included-label behavior. Verify no
  background DOM label nodes, no omitted eligible instances, and resources return
  to the same non-ADS-B baseline after repeated enable/disable. Record the exact
  browser/renderer, hardware and a same-scene ADS-B-off comparison. The approved
  spec sets no frame-time threshold: report measurements and visibly delayed
  interaction honestly; improve measured bottlenecks before calling it usable.
- [x] **Step 5: Document final behavior and run required checks.** Document
  defaults, mode/filter precedence, conflicts, table scope, shared polling,
  original-position freshness, unavailable fields, units, attribution, source
  failures and rollout usage review. API docs show partial PUT, complete revisioned
  settings, and traffic bundle examples matching the implemented parsers.
  From root run `./tools/verify backend` and `./tools/verify frontend`; expect
  PASS. Commit the candidate, then run
  `ACCEPTANCE_POLICY_BASE_SHA=<selected-full-base-sha> ./tools/verify static`;
  expect all required checks to pass against the reachable implementation base.
  From the frontend run `npx playwright test overview-adsb.spec.ts
  overview-adsb-cross-window.spec.ts overview-adsb-performance.spec.ts
  --project=chromium --workers=1`, then existing globe, map interaction,
  fullscreen route, arrival, POI-responsive and metric-history suites. Expect
  PASS; manually inspect screenshots instead of blindly updating snapshots.
  Include `overview-window-refresh.spec.ts`, `overview-window-paths.spec.ts`,
  `overview-window-controls.spec.ts` and `overview-traffic-paths.spec.ts` in
  existing-browser regressions against the reconciled `dev` base.
- [x] **Step 6: Verify an isolated exact-SHA production path.** Follow
  `docs/development/workflow.md` and `docs/development/cloud-docker.md`; read
  the runtime skill's Docker proxy/CA reference before builds. Preserve
  `DOCKER_HOST` and active context, discover the actor socket if needed, and
  verify `docker info` there. Use a task-owned Compose project and loopback
  ports with the repository production images, Nginx/backend/Prometheus path,
  isolated named data volume and a controlled provider transport. Capture actual
  API GET/PUT/traffic responses through Nginx, two-window synchronization and a
  backend restart preserving settings but not live contacts. Keep provider
  substitution explicit in the report and outside normal deployment settings.
  Implement `tools/acceptance/adsb/backend_fixture.py` as a test-only launcher
  exporting `app`: import `main`, replace its ADS-B client construction with
  `httpx.MockTransport` for adsb.lol URLs only, then expose unchanged `main.app`
  and its normal lifespan. Preserve real Prometheus/other HTTP clients. Mount the
  launcher and fixed JSON fixtures read-only into the exact backend image and
  override only its command to `uvicorn backend_fixture:app --host 0.0.0.0
  --port 8000`; retain the production Nginx and data mounts. This verifies the
  application startup/adapter/cache/API path without upstream network traffic.
  No production admin/test endpoint is needed. Clean up task-owned resources.
- [x] **Step 7: Record evidence and commit acceptance files.** Report candidate
  full SHA, base, image inputs, viewport, renderer, source mode, timestamps,
  cross-window timing, resource/performance measurements, checks, screenshots
  and recording. Distinguish intercepted browser fixtures from actual Nginx/API
  evidence. Obtain independent review before ready-for-PR claims. If checks or
  infrastructure are unavailable, record the precise gap and leave acceptance
  pending. Commit the docs/tests with
  `test(adsb): verify shared aircraft layer and document acceptance`.
  Recheck the final candidate if that commit changes runtime inputs. Merge,
  deployment and contacting the provider remain outside this task.
