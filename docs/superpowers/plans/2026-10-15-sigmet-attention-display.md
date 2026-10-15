# SIGMET attention: display and acceptance tasks

Continuation of the [implementation plan](2026-10-15-sigmet-attention.md).

## Task 4: Select SIGMETs through the visible map

**Files:**

- Create frontend `src/pages/aviation-weather/sigmet-picking.ts` and
  `sigmet-picking.test.ts`.
- Modify frontend `aviation-inspection.ts`, `AviationLayer.tsx`,
  `AviationDetails.tsx` and their tests in that directory.
- Modify frontend `src/pages/OverviewPage.tsx` and
  `OverviewPage.layers.test.tsx`.

**Interfaces:**

- Export

  ```typescript
  pickSigmetFeatures(view: AviationView, camera: THREE.Camera, point: { x: number; y: number }, viewport: { width: number; height: number }): AviationSelection[]
  ```

  from the new picking module.
- Extend existing `pickAviationFeatures`, `inspectionReports` and
  `resolveAviationSelection` to support visible SIGMETs. Preserve existing
  `AviationSelection = { layer: AviationLayer; id: string }` and the
  `AviationLayer.onSelect(candidates)` signature.
- Add

  ```typescript
  visibleSigmetReports(view: AviationView, camera: THREE.Camera, viewport: { width: number; height: number }): AviationSelection[]
  ```

  for the keyboard chooser. Reuse the map's admitted and filtered geometry
  rather than exposing every report in the feed.

- [x] **Step 1:** Replace tests that explicitly prohibit SIGMET picking with
  regressions for visible interiors and boundaries, holes, multipolygons,
  dateline crossing, overlap candidates, viewport edges, near-horizon
  visibility and far-side exclusion. Keep station and click-versus-drag
  tests. Add a keyboard test selecting a visible SIGMET and assert reports
  outside the rendered map are absent from the chooser.
- [x] **Step 2:** Run picking, inspection, layer and details tests; confirm
  expected failures without breaking fixture/camera setup.
- [x] **Step 3:** Implement picking with the existing ray/camera and spherical
  geometry conventions; treat the hit as a point on the visible globe,
  account for holes and dateline wrapping, and return all visible
  overlapping candidates in stable identifier order. Do not add map
  listeners that bypass the existing drag threshold or leak on unmount.
- [x] **Step 4:** Integrate Task 3's selection mutation when a user chooses one
  SIGMET; overlapping hits first open a compact chooser, with no selection
  write until the user chooses. Focus the resulting card after confirmed
  success. Clicking an existing pending bulletin focuses it without
  repeating a write; clicking a cleared one reopens it. Without a route show
  inspectable report details and a local explanation instead of persisting
  selection. Distinguish loading/save errors from a confirmed selection.
- [x] **Step 5:** Run the owning frontend tests, including existing METAR/TAF
  picking, keyboard navigation, globe gesture behavior and renderer disposal
  regressions. Commit as `feat: inspect and select SIGMETs on the globe`.

## Task 5: Deliver the quiet Overview and compact relevant-only Configuration

**Files:**

- Modify frontend `src/pages/aviation-weather/RouteSigmetNotices.tsx`,
  `RouteSigmetSettings.tsx`, `AviationSettingsCard.tsx`, `AviationWeather.css`
  and their adjacent tests.
- Modify frontend `src/pages/OverviewPage.tsx` and its layer tests.
- Add frontend `src/pages/aviation-weather/SigmetAttentionCard.tsx` and
  `SigmetAttentionCard.test.tsx` for the shared concise card and confirmed
  acknowledgement behavior.

**Interfaces:**

- Component interface:

  ```typescript
  SigmetAttentionCard({ item, onAcknowledged }: { item: SigmetAttentionItem; onAcknowledged?: () => void })
  ```

  uses the existing acknowledgement hook and renders identifier,
  hazard/severity, segment or `Selected`, a collapsed full report, and
  Acknowledge.
- Component interface:

  ```typescript
  RouteSigmetNotices({ presentation, focusedNoticeKey }: { presentation: SigmetPresentation; focusedNoticeKey?: string | null })
  ```

  uses the full attention list from Task 3, renders nothing at zero, and pages
  at most three cards. Clamp the page when entries disappear and navigate to an
  explicitly selected key.
- Configuration consumes the same union as Task 3, but includes cleared
  intersections in a collapsed Cleared section. Selected-only acknowledgements
  leave the list entirely. Keep a collapsed Diagnostics section outside the main
  list.

- [x] **Step 1:** Add tests asserting zero attention produces no region or
  reserved wrapper; four pending bulletins render `SIGMETS: 4` and at most
  three cards; navigation reaches the fourth; acknowledgement on page two
  clamps correctly; removed disclaimer/route/status prose is absent. Assert
  the status border uses the first pending card's stable color and
  reduced-motion CSS disables animation.
- [x] **Step 2:** Add Configuration tests with hundreds of unrelated reports:
  only matched and selected rows appear, full reports and Cleared start
  collapsed, selected-only acknowledgement removes its row, route
  acknowledgement moves to Cleared, Show again restores attention, and
  failures retain confirmed state. Assert map-only filtering cannot change
  the relevance list or count.
- [x] **Step 3:** Run the owning card, notices, settings and Overview layer
  tests; confirm expected failures.
- [x] **Step 4:** Implement the shared card and relevant-only UI. Exact status
  copy is `SIGMETS: N`; use `Pending`, `Cleared`, `Selected`, `Acknowledge`,
  `Show again`, `Previous`, and `Next` for controls/sections. Use a smooth
  2.5-second border/glow pulse on pending cards and the status border; under
  `prefers-reduced-motion: reduce` render a steady bright border. Keep
  readable text contrast throughout. Remove mobile/desktop wrapper gaps when
  empty. Retain the optional map filter with label
  `Show intersecting polygons only`.
- [x] **Step 5:** Put source/evaluation diagnostics and explanatory validity
  limits in Configuration's collapsed Diagnostics and expanded reports. Keep
  failed write messages next to their action, not in the ten-foot status
  count. Run all owning tests plus frontend unit suite, lint and production
  build with explicit limits. Commit as
  `feat: simplify SIGMET attention and configuration displays`.

## Task 6: Verify production paths, capture evidence, and provide the revised review server

**Files:**

- Modify `frontend/mission-planner/tests/e2e/route-sigmets-production.spec.ts`,
  `tests/e2e/support/route-sigmets-probe.ts`, and
  `tools/acceptance/aviation-weather/runner.py` only as needed for the extended
  scenarios.
- Update `tools/tests/test_route_sigmets_acceptance.py` for runner proof
  requirements.
- Update `docs/features/overview-weather.md` and `docs/api/aviation-weather.md`.
- Create `docs/reports/2026-10-15-sigmet-attention.md` with exact candidate SHA,
  results and evidence paths.

**Interfaces:**

- Keep

  ```bash
  tools/acceptance/aviation-weather/run.sh exact-SHA provisioned-browser-executable
  ```

  Add runner proof fields `quiet_overview`, `manual_selection`,
  `shared_acknowledgement`, `configuration_relevance`, and
  `screenshots_complete`; reject PASS when any required proof is absent or
  false.
- Add production scenarios using two independent browser contexts and the actual
  selection/acknowledgement endpoints. Probe geometry to locate candidates, but
  perform selection with actual pointer/keyboard input against the native
  renderer.

- [x] **Step 1:** Add failing acceptance scenarios for zero-result silence,
  unknown-only silence, four-count/three-card navigation, map
  nonintersection selection, overlap chooser, same bulletin with several
  polygons, selecting a cleared bulletin, and selecting without a route.
  Verify cross-display convergence within the existing 8,000 ms bound and
  refresh persistence.
- [x] **Step 2:** Add scenarios covering selected-only acknowledgement from
  Overview, simultaneous selection/acknowledgement, route/run switch during
  a pending write, amendment/expiry/cancellation, compact Configuration with
  a large unrelated feed, and reduced-motion presentation. Capture actual
  Configuration Pending/Cleared, not only Overview. Update runner proof
  tests and verify they fail before adding the required evidence checks.
- [x] **Step 3:** Complete runner proof collection and retain source/browser
  provenance. Run backend `test_route_sigmets_*.py` plus aviation
  runtime/main regressions, runner unit tests, frontend full unit suite,
  ESLint and production build. Use 10-minute limits for tests/lint and a
  20-minute build limit, each with a 10-second termination grace period.
  Apply repository formatting checks and `git diff --check`.
- [x] **Step 4:** On a clean committed candidate, run

  ```bash
  timeout --kill-after=10s 35m tools/acceptance/aviation-weather/run.sh "$candidate_sha" "$browser_path"
  ```

  with the runner's required `ROUTE_SIGMET_REAL_CAPTURE` set to the retained
  pinned real-source capture, the configured actor Docker endpoint
  preserved, and a distinct `starlink-route-sigmets-*` project. Capture
  desktop 1920×1080 and mobile 390×844: empty Overview, pending Overview,
  selected-only Overview, and Configuration Pending/Cleared. Verify fixture
  validity dates before the run. If it fails or times out, verify the owned
  process tree and containers are gone before retrying.
- [x] **Step 5:** Review screenshots for readability, clipping, pulse/color
  consistency and empty layout. Verify cleanup receipts report no acceptance
  containers, networks, disposable volumes, browsers, workers or listeners.
  Record test counts, SHA, limitations and evidence paths in the report;
  update feature/API documentation to describe geographic relevance without
  implying altitude/time matching. Commit the evidence report and rerun only
  checks affected by any new changes; if product code changes, obtain fresh
  exact-SHA acceptance.
- [x] **Step 6:** Start a separate persistent synthetic review instance on an
  available LAN port, with explicit owner/Compose project/volumes/stop
  command recorded first. Seed pending intersections, one cleared
  intersection, and a selectable nonintersecting polygon. Use synthetic
  validity covering the review period. Confirm API responses and both
  screens through a closed-after-check browser context. Leave only this
  explicitly requested review runtime and the earlier review runtime alive;
  report both URLs and stop commands so the user can compare them.
- [x] **Step 7:** Use the requesting-code-review skill for a whole-branch review
  and fix material findings with regression evidence. Push the feature
  branch and open a PR against `dev`, accounting for the original SIGMET
  feature's integration state. Include the reviewed spec/plan and acceptance
  evidence in the PR. Keep the worktree while the PR is open. After merge,
  clean up task-owned worktree/branches/files per workspace rules, while
  retaining a review service only as long as the user's request requires it.
