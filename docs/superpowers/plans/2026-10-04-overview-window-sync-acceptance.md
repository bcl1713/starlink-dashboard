# Overview Window Synchronization: Integrated Acceptance Task

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for native execution, or `superpowers:subagent-driven-development` if
> delegation is selected. Track the checkbox steps below.

**Goal:** Verify real saved-state propagation and display controls through the
production path, document the supported workflow, and report evidence limits.

**Architecture:** Controlled browser fixtures verify timing/races; a separate
two-page journey uses an isolated real backend behind production Nginx. Existing
regression suites protect view/history continuity. No V2 acceptance result is
misrepresented as acceptance of this feature.

**Tech Stack:** Playwright Chromium, Docker Compose, FastAPI, Nginx, repository
quality gates, markdownlint.

**Spec:** [Approved design](../specs/2026-10-04-overview-window-sync-design.md).
Read the [main plan](2026-10-04-overview-window-sync.md) for Global Constraints,
Review Focus, baseline, and execution requirements. Tasks 1–4 are prerequisites.

## Task 5: Real-request acceptance, regressions, and operator guidance

**Files:**

- Create: `tests/e2e/support/overview-window-mission.ts`,
  `tests/e2e/support/overview-route-probe.ts`.
- Create: `tests/e2e/overview-window-production.spec.ts`,
  `playwright.window-acceptance.config.ts` in the frontend.
- Modify: `playwright.config.ts` to exclude the production-only journey.
- Create: repository-root `tools/acceptance/overview-window-sync/compose.yml`,
  `tools/acceptance/overview-window-sync/run.sh`.
- Reuse: repository-root
  `docs/missions/acceptance-assets/v2-activation-route.kml`. Derive a second
  route with names KCCC/KDDD, coordinates two degrees north/ten degrees east,
  and the same timestamps.
- Modify: `docs/features/overview.md` and relevant existing Configuration/clock
  user guidance located through the docs index.
- Create: `docs/reports/2026-10-04-overview-window-sync-acceptance.md` and
  bounded evidence files under
  `docs/reports/evidence/2026-10-04-overview-window-sync/`.

**Interfaces:**

- `playwright.window-acceptance.config.ts` requires
  `OVERVIEW_ACCEPTANCE_BASE_URL` to be a loopback HTTP URL; no frontend preview
  webServer. One Chromium worker, no retries, traces on failure.
  `tests/e2e/overview-window-production.spec.ts` belongs only to this config;
  the ordinary config excludes it explicitly so fixture suites do not
  accidentally claim real-backend acceptance.
- `run.sh` resolves repository HEAD, requires a clean tracked worktree, exports
  ACCEPTANCE_CANDIDATE_SHA, and invokes task-owned Compose file/project
  `starlink-257`. Use 127.0.0.1:18257 for backend and 127.0.0.1:15257 for Nginx;
  check availability before starting and fail clearly on collision.
- Standalone Compose uses production frontend/backend Dockerfiles and Nginx
  config, task-specific named mission/settings/satellite/route/POI volumes,
  simulation data, and Prometheus's production config/rules. No global container
  names, dish access, host data binds, unrelated cleanup, or Grafana
  requirement.
- Browser evidence records exact SHA/build inputs, successful mutation
  responses, route identity, visible time/labels, propagation latency,
  fullscreen state, camera comparison, retained sample continuity, and actual
  read counts.

- `seedOverviewWindowMission(request: APIRequestContext)` returns missionId,
  firstLegId, secondLegId, firstRouteId, and secondRouteId, all strings. Create
  mission/two legs through real V2 REST calls and upload both routes through
  leg-route endpoints, following the existing integration fixture shape.
- `installOverviewRouteProbe(page: Page): Promise<void>` installs a DevTools
  boundary before application load. `renderedRoutePoints(page: Page)` returns
  `Promise<number[][]>` from the route's rendered React props/Three resource;
  distinguish it from traffic links using its flow configuration. Follow
  existing probe patterns without adding visible product instrumentation.

- [x] **Step 1: Establish the production journey and isolation checks.** Use the
      seed helper and real mission storage/API contracts for two legs. Intercept
      no application settings/mission responses in this journey. Verify requests
      pass through Nginx with actual successful statuses. Exercise:

  ```ts
  // After real PUT /api/overview-clocks/settings through the Configuration form:
  await expect(targetClock).toContainText("Honolulu operations", {
    timeout: 8000,
  });
  // After real activate/switch/deactivate requests through Missions controls:
  await expect
    .poll(() => renderedRoutePoints(overview), { timeout: 8000 })
    .toEqual(projectRouteArc(expectedRoute.points, 2.015, 8));
  await expect(overview.getByLabel("Map POIs")).toContainText("KCCC");
  // Compare real saved state + visible projections, not just request occurrence.
  expect(overviewMainFrameNavigationCount).toBe(1);
  expect(
    await overview.evaluate(() => document.fullscreenElement !== null),
  ).toBe(expectedFullscreen);
  ```

  Read expectedRoute through the real route API response. Compare rendered route
  points and accessible POI names; after deactivation assert no route resource.
  Preserve existing projection constants. Also test actual clock time text,
  generated arrival state, and route identity.

- [x] **Step 2: Validate and run the isolated production environment.** Read the
      cloud Docker/proxy references before build. Preserve configured Docker
      endpoint; run `docker info` normally. Commit the acceptance harness first
      so its clean-worktree check binds a concrete candidate. Run the validation
      command below, review rendered volume/port isolation, build with exact
      SHA, await bounded health, then execute
      `npx playwright test --config playwright.window-acceptance.config.ts`. A
      failing journey must name its failed assertion; keep its trace and mark
      acceptance pending until resolved. Do not depend on provider connectivity.

  ```sh
  docker compose -p starlink-257 \
    -f tools/acceptance/overview-window-sync/compose.yml config --quiet
  ```

- [x] **Step 3: Verify every saved-state path and continuity.** Keep editing
      page foreground, without target bringToFront/reload during timed
      observations. Cover clock label/timezone, history-window changes, link
      toggles, GPS state, camera-follow preference, mission
      activation/switch/deactivation, active-leg edits and timeline-derived
      POIs. Use fixture failure/hold controls for failed PUT, interrupted GET,
      and recovery; separately identify controlled results. Exercise
      ordinary/native fullscreen, manual camera intent, retained history,
      multiple/closed displays, targeted recenter, remote fullscreen rejection,
      local click success, and local Escape state propagation. Save desktop and
      fullscreen screenshots and response-to-visible durations; assert each
      healthy controlled propagation is <=8000ms.
- [x] **Step 4: Run relevant existing browser regressions and quality gates.**
      From frontend run the command below. At repository root run
      `./tools/verify frontend`, `./tools/verify backend`,
      `./tools/verify static`. Preserve existing tolerances. Report
      renderer-dependent failures against unchanged-base evidence rather than
      silently increasing retries/tolerances.

  ```sh
  npx playwright test \
    tests/e2e/overview-globe.spec.ts \
    tests/e2e/overview-map-interaction.spec.ts \
    tests/e2e/overview-arrival.spec.ts \
    tests/e2e/v2-mission-overview.spec.ts \
    tests/e2e/overview-metric-history.spec.ts \
    tests/e2e/overview-metric-history-fullscreen.spec.ts \
    tests/e2e/overview-fullscreen-route.spec.ts \
    tests/e2e/configuration-clocks.spec.ts --workers=1
  ```

- [x] **Step 5: Update operator guidance and the acceptance report.** Document
      five-second propagation plus response/render time, suspension catch-up,
      browser-local camera preferences, display selection/loss, same-browser
      command scope, real fullscreen state, and the required local click when
      policy rejects remote entry. Replace investigation's
      implementation-pending status only when backed by the corresponding
      evidence. Record gaps, exact runtime versions, SHA, fixtures vs real
      requests, screenshots, timings, checks, Docker endpoint/context, and
      task-specific cleanup.
- [x] **Step 6: Verify cleanup and commit.** Stop only the `starlink-257`
      project and remove only its named volumes; check no task
      containers/listeners remain. Format and lint changed docs; commit
      `test(overview): verify cross-window production workflow`. If this commit
      changes frontend/backend acceptance inputs, rebuild and rerun the
      production journey at the final candidate SHA.
- [x] **Step 7: Obtain independent whole-branch review and close gaps.** Review
      against the approved spec/plan, query lifecycle, message
      expiration/targeting, fullscreen truthfulness, tests, and user guidance.
      Fix material findings and rerun affected verification. Report exact
      acceptance limitations. Follow the approved session handoff protocol for
      fresh review, integration fixes, PR creation, and verified merge into
      `dev`.

Task 5 steps 1–6 are complete: see the
[session record](2026-10-04-overview-window-sync-acceptance-progress.md) for
production results and resolved regression gates. Step 7's independent review
and [fresh follow-up](2026-10-04-overview-window-sync-follow-up-review.md)
are complete. R1/R2 are independently closed; R3 Minor documentation is corrected
and verified in the [integration record](2026-10-04-overview-window-sync-integration.md).
Final candidate acceptance and protected PR/merge gates remain pending.
