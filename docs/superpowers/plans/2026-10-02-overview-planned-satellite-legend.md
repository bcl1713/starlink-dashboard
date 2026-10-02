# Overview #218 Planned Satellite and Legend Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` for recommended
> native execution, or `superpowers:subagent-driven-development` if Brian
> selects delegation. Track the checkbox steps below.

**Goal:** Make satellite selection explicitly planning data and show a compact
legend for rendered map layers while preserving settings, diagnostics and
supported warning semantics.

**Architecture:** Extract small satellite and legend views from Overview. Use
the existing projections and scene guards as their authority. Move the history
editor and detailed map diagnostics to Configuration; keep short operational
exceptions outside the legend and planning card.

**Tech Stack:** React 19, TypeScript, React Query, Three.js, CSS container
queries, Vitest/Testing Library and Playwright Chromium.

**Spec:** [Approved responsive Overview design](../specs/2026-09-30-responsive-overview-design.md),
specifically its satellite/map contracts and delivery boundaries.
[Issue #218](https://github.com/bcl1713/starlink-dashboard/issues/218) selects
this slice of [#213](https://github.com/bcl1713/starlink-dashboard/issues/213).

**Status:** Brian approved native implementation on 2026-10-02.
Recommended execution: native, because the four tasks share the Overview and
Configuration integration and existing browser fixtures.

## Baseline and authority

Selected `dev`: `7ea084979fa237e4e1403bd26e9556ced36de1fd`, checked through
GitHub on 2026-10-02 after PR #230 merged #217. Its tree is
`0ca0b7cdf169a9061c2857608caac752f3b76bc6`. The existing checkout at
`a0378890475355da8be311989ff633c3254361c1` has that identical tree, so local
source inspection covers the exact selected baseline. Leave the existing
`feat/217-arrival-states` branch intact during planning. After approval, recheck
`dev`, reconcile any drift, and create an isolated implementation branch from
the selected base using `superpowers:using-git-worktrees`.

`OverviewPage.tsx` currently owns eight diagnostic legend rows and the history
selector. Satellite ID comes from `/api/active-x-link`; catalog coordinates come
from `/api/satellites`. The backend derives normal/warning from the existing
configured forbidden relative-azimuth rule, not a measured connection. Preserve
the blue/red `satcomLineStyle` and link geometry. The history trail and five
graphs already share one history query and persisted duration.

## Global constraints

- Card content: `X-BAND`, selected identifier, `PLANNED SATELLITE`.
- No illustration, green connection dot, update age or connection claim.
- Legend names: Aircraft; Planned route; Track history; Ground entry point;
  Planned satellite link. Only render entries whose scene guards are true.
- Preserve aircraft/GEP without an active route and keep unavailable route
  state explicit outside the legend. Samples identify enabled rendered layers;
  temporary camera/globe occlusion does not toggle legend entries.
- Preserve generated POI and configured satellite labels and accessible names,
  including collision-hidden labels. Neither becomes a sixth legend entry.
- Reuse shared glass tokens, existing subscriptions, geometry, natural lighting,
  camera, fullscreen and arrival behavior. No dependency or API changes.
- No counts, selectors or explanatory/debug paragraphs in the Overview legend.
  Keep configuration and diagnostics reachable in Configuration.
- #219 retains final desktop composition/camera tuning; #220 retains mobile
  stage, expandable legend and touch/rotation redesign. This slice must remain
  usable in the current scrolling fallback and native fullscreen.

## Review focus and presentation decisions

1. An empty selection must not imply connectivity: show `X-BAND / NO SATELLITE
   SELECTED / PLANNED SATELLITE`; loading uses `LOADING…`, failure or malformed
   selection uses `UNAVAILABLE`. Test cached-selection refresh failure too.
2. A selected ID absent from a valid X-band catalog remains the selected planning
   ID, but cannot manufacture link geometry or a link legend entry. Show the
   compact exception `Planned link unavailable` separately and test recovery.
3. Cached renderable geometry during query errors still needs its legend sample.
   Visibility follows the actual draw guards; short failure/stale text outside
   the legend prevents retained scene data from looking newly verified.
4. A failed duration save or saved custom duration must remain understandable
   after relocation. Test loading, GET/PUT failures, pending edits, custom values
   and shared-query invalidation through the new Configuration control.
5. Hidden POI/satellite labels must retain distinct accessible identities. Test
   collision fallback, occlusion-independent names and long satellite IDs.

Keep normal planning state out of the exceptions area. A supported `warning`
gets visible text `Planned link warning` and an accessible description naming
the existing configured azimuth rule, without an alarm banner or new threshold.
Do not announce it as current when its selection refresh failed; report
`Satellite selection unavailable` and retain any warning only as last known.
Do not add freshness to the planning card. Map status distinguishes status-feed
age from independently verified position freshness already owned by #217.

## Task 1: Planning state and text-only satellite card

**Files:** Create `frontend/mission-planner/src/pages/overview-planned-satellite.ts`,
`OverviewPlannedSatelliteCard.tsx`, `OverviewPlannedSatelliteCard.css` and their
corresponding `.test.ts` / `.test.tsx` files in that directory.

**Interfaces:** Export `PlannedSatelliteState` as a discriminated union of
`{ kind: 'selected'; satelliteId: string }` and
`{ kind: 'none' | 'loading' | 'unavailable' }`. Export
`derivePlannedSatelliteState(selection: unknown, isLoading: boolean,
isError: boolean): PlannedSatelliteState`. Export
`OverviewPlannedSatelliteCard({ state }: { state: PlannedSatelliteState })`.
Reuse `projectActiveConfiguredXBandSatelliteId`; explicit null is no selection,
while malformed/missing loaded responses fail closed. Error precedes cached ID;
a valid ID does not depend on GPS/network freshness or catalog geometry.

- [x] Write projection tests with assertions equivalent to:

  ```ts
  expect(derivePlannedSatelliteState({ satellite_id: 'X-6' }, false, false))
    .toEqual({ kind: 'selected', satelliteId: 'X-6' });
  expect(derivePlannedSatelliteState({ satellite_id: null }, false, false))
    .toEqual({ kind: 'none' });
  expect(derivePlannedSatelliteState({ satellite_id: 'X-6' }, false, true))
    .toEqual({ kind: 'unavailable' });
  ```

  Also cover loading, blank/non-string IDs and missing responses. Component
  tests assert the exact three text rows for every state, accessible region
  `Planned satellite`, no image/SVG/live status/age, and wrapping of long IDs.
- [x] Run `npm run test:unit -- src/pages/overview-planned-satellite.test.ts
  src/pages/OverviewPlannedSatelliteCard.test.tsx` from the frontend; verify
  failure because the modules do not exist.
- [x] Implement the projection and view with non-interactive text and shared
  glass styling. Use `overflow-wrap: anywhere` for IDs. No timer or query hook
  belongs in this component.
- [x] Rerun the focused tests; require all cases to pass. Commit only this task's
  files with `feat(overview): add planned satellite card`.

## Task 2: Relocate history controls and map diagnostics

**Files:** Create `OverviewHistorySettingsCard.tsx`,
`OverviewHistorySettingsCard.test.tsx`, `OverviewMapDiagnostics.tsx` and
`OverviewMapDiagnostics.test.tsx` under `frontend/mission-planner/src/pages/`.
Modify `ConfigurationPage.tsx`, `ConfigurationPage.test.tsx`,
`docs/features/system.md` and `docs/features/overview.md`.

**Interfaces:** Export no-prop `OverviewHistorySettingsCard()` and
`OverviewMapDiagnostics()` views owning existing query hooks. Mount each once
in Configuration, separate from clock-loading/error branches. The editor uses
`useOverviewHistorySettings` and `useUpdateOverviewHistorySettings`; the
diagnostics use existing status, history, satellite and active-link queries,
`useCurrentTime`, and the unchanged projection/look-angle helpers.

- [x] Write editor tests asserting labelled `Overview history window`, options
  300/900/1800/3600 seconds, preservation of a saved 1200-second custom value,
  disabled loading/pending state, and distinct read/save failures. Assert a
  900-second edit calls the existing mutation once. Diagnostics tests assert
  valid configured counts, selected ID, current/last-known status, track-history
  loading/failure, GEP unavailable, configured GEO azimuth/elevation and explicit
  missing geometry. Assert planning terminology and supported warning text.
- [x] Run the two new component tests and Configuration tests; verify missing
  modules/new sections fail before implementation.
- [x] Implement the two cards and mount them independently in Configuration.
  Preserve the current mutation's invalidation of both history/settings query
  keys. Do not introduce a history cadence editor, satellite selector, new
  endpoint or second application query client. Preserve needed diagnostics
  without importing the entire Overview scene.
- [x] Document Configuration as the new duration/diagnostics location. Explain
  shared trail/graph duration, fixed five-minute rolling statistics, planning
  geometry and the existing warning rule. Remove transitional claims that the
  selector remains in the globe legend; retain unchanged polling guidance.
- [x] Rerun focused tests including the existing update-history-settings hook
  tests; require success and commit with
  `feat(configuration): retain overview settings and map diagnostics`.

## Task 3: Conditional legend, operational exceptions and page integration

**Files:** Create `OverviewMapLegend.tsx`, `OverviewMapLegend.test.tsx`,
`OverviewMapStatus.tsx`, `OverviewMapStatus.test.tsx` and
`OverviewPage.layers.test.tsx` under `frontend/mission-planner/src/pages/`.
Modify `OverviewPage.tsx`, `OverviewPage.contract.test.ts`, `OverviewPage.css`,
`OverviewOverlayLayout.css`, `OverviewVisualTokens.css` and
`docs/features/overview.md`.

**Interfaces:** `OverviewMapLegend` receives boolean props `aircraft`, `route`,
`history`, `groundEntryPoint`, `plannedLink`, plus
`linkState: 'normal' | 'warning' | null`. Keep accessible label `Globe legend`.
`OverviewMapStatus({ messages }: { messages: readonly string[] })` renders
concise exception text in an independently labelled `Map status` region and
renders nothing when empty. Use polite status updates, not repeated alerts.

- [x] Write legend tests asserting exactly the five approved labels and order
  when enabled, and omission of each disabled layer. Assert no form control,
  count or diagnostic text, samples hidden from accessibility APIs, and a
  planned-link sample distinct from track by width/treatment as well as color.
  Test normal/warning sample styling and status text separately.
- [x] Write a page test with Canvas mocked as a scene boundary: no route plus
  valid aircraft/GEP retains both markers and entries; fewer than two history
  points omits history; selected ID without catalog geometry omits link only;
  loading/error combinations show honest exceptions. Cached geometry plus
  refresh failure keeps matching entries and displays its failure. Verify POI
  and configured satellite identities remain accessible even with hidden Html
  labels. Update the obsolete source assertion requiring generated-POI prose;
  retain single-query and geometry contracts.
- [x] Run the new tests and existing page contract tests; verify the changed
  behavior fails before integration.
- [x] Integrate Task 1 and the new legend using exactly the scene predicates:
  `Boolean(aircraftPosition)`, `hasRenderableRoute`,
  `aircraftHistoryPoints.length >= 2`, `Boolean(groundEntryPoint)` and
  `Boolean(activeConfiguredXBandLink)`. Remove the selector/mutation and verbose
  diagnostic computations from Overview; keep its history-settings query for
  the metric group's selected duration. Preserve all scene geometry guards.
- [x] Move route exceptions and short status/history/link failures into Map
  status, including selected-but-unprojectable link and supported warning text.
  Keep the existing accessible Map POIs list and add a separate accessible list
  of configured satellite IDs, independent of globe occlusion. Do not use
  network freshness to assert GPS validity; leave arrival provenance untouched.
- [x] Add the card below the upper-right clock area and keep legend/status at
  lower right within existing desktop container conditions. Extend current
  scrolling fallback and shared glass/fallback selectors for the card/status;
  remove obsolete three-column legend/selector styles. Keep content readable
  at 360px and enlarged text; final camera/layout and expandable mobile legend
  remain later slices. Document the conditional legend and unavailable states.
- [x] Rerun focused tests plus satellite projection, satcom style, flow consumer,
  POI marker and arrival regressions. Commit with
  `feat(overview): show rendered layers and preserve map exceptions`.

## Task 4: Browser regressions and exact-candidate acceptance

**Files:** Create
`frontend/mission-planner/tests/e2e/overview-planned-satellite-legend.spec.ts`.
Modify `overview-globe.spec.ts`, `overview-metric-history.spec.ts`,
`overview-metric-history-fullscreen.spec.ts`, `overview-metric-cleanup.spec.ts`
and the POI screenshot baseline in the same e2e directory where affected.
Record results in
`docs/reports/2026-10-02-overview-planned-satellite-legend.md` and link them from
`docs/reports/README.md`.

- [x] Add browser cases for selected/null/error satellite state; missing or
  invalid catalog; normal/warning link; all/partial/no layers; route failure
  without losing aircraft/GEP; POI collision labels and long IDs. Require real
  globe readiness using the existing `waitForGlobeVisualReady` helper.
- [x] Update old legend expectations to the approved layer labels, short Map
  status or Configuration diagnostics. Duration-save browser tests navigate
  through Configuration, save, return, and verify trail/graph window updates.
  For tests asserting motion/rebase on the same chart instance, retain that
  requirement using the existing mounted-panel test harness with controlled
  window/history props; navigation/remounting cannot prove a seamless rebase.
  Update obsolete control selectors throughout the existing suites.
- [x] Verify missing data, text enlargement and overlay containment at
  1920×1080 ordinary/native fullscreen, 390×844, 844×390 and 360px portrait.
  Extend overlap assertions to the card and Map status. Preserve current
  fallback scrolling; do not claim #220 mobile-stage acceptance.
- [x] Run `./tools/verify frontend` and `./tools/verify static` from the root,
  setting `ACCEPTANCE_POLICY_BASE_SHA` to the exact reachable selected base for
  the static gate. Require passing Vitest, production build and applicable
  static checks. Run the changed/new Chromium suites serially, plus existing
  arrival and POI-responsive regressions. Inspect snapshot changes manually.
- [x] Commit the tested candidate, record its full SHA and obtain exact-SHA CDP
  screenshots and a short recording over bright terrain/dark ocean, including
  blur fallback, missing selection, warning and route failure. Verify an
  isolated production Docker/Nginx/backend/Prometheus path as required by the
  development workflow; fixture tests alone are insufficient. Read the cloud
  Docker guidance before starting containers. This baseline has no sealed
  Overview acceptance lane, so an unrelated lane cannot certify this slice.
- [x] Report SHA, viewport, source mode, browser/renderer, fixture versus
  production coverage, checks and limitations. Obtain independent review before
  a PR is ready. Pushing a candidate/creating a PR requires authorization in
  the execution session; merge, deployment and issue closure are outside this
  plan. If evidence infrastructure is unavailable, report the precise gap and
  leave acceptance pending rather than asserting completion.

## Plan self-review

Tasks cover #218's card/unavailable state, conditional layers, existing warning
semantics, no-route context, marker accessibility, relocated controls/diagnostics,
documentation and exact-candidate rendered evidence. All five review-focus
conditions have owning tests above. No chart, arrival, backend or mobile-stage
redesign is proposed. Brian approved this plan before implementation on 2026-10-02.
