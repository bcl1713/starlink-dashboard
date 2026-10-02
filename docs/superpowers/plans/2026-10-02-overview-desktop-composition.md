# Overview #219 Desktop Composition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for recommended native execution, or `superpowers:subagent-driven-development`
> if Brian selects delegation. Track the checkbox steps below.

**Goal:** Fit the globe-first desktop Overview at actual 1920×1080 in ordinary
and native fullscreen views, preserving operational context and controls.

**Architecture:** Compose the already-delivered five metrics, arrival panel,
planning card and conditional legend around the existing full-size globe. One
right-side layout region reserves space for the fullscreen control and map
exceptions. CSS owns placement and shared surfaces; existing components retain
their queries, derivation, chart lifecycle and scene geometry.

**Tech Stack:** React 19, TypeScript, Three.js/React Three Fiber, uPlot, CSS
container queries, Vitest/Testing Library and Playwright Chromium.

**Spec:**
[Approved responsive Overview design](../specs/2026-09-30-responsive-overview-design.md)
and [issue #219](https://github.com/bcl1713/starlink-dashboard/issues/219). This
is the desktop composition slice; #220 owns mobile stage/interaction.

**Status:** Brian approved native implementation on 2026-10-02. Native
execution is recommended because the two implementation tasks share the same
layout and browser contracts, followed by one acceptance task.

## Global Constraints

- Five metrics: latency (ms), downlink (Mbps), uplink (Mbps), packet loss (%)
  and obstruction (%). Signal quality remains excluded.
- Preserve the existing globe, natural time-based lighting, route geometry,
  uPlot and shared subscriptions. No political boundaries or warning banner.
- Retain latest-observation provenance, separate network/position freshness,
  gaps, accessible unavailable states and fixed five-minute rolling statistics.
- Preserve native document fullscreen, manual orbit/zoom, configured satellite
  geometry and supported warning semantics; never change data to fit a mockup.
- One component tree across sizes/fullscreen; no hidden legacy controls,
  duplicated panels or z-index patches. Keep narrow flow usable until #220.
- Target 16–24 px margins and 400–440 px metrics; typography/glass numbers in
  the design are starting points to tune against actual browser fit/readability.
- No backend/API change, dependency replacement, merge, deployment or release to
  `main` belongs to this plan.

## Review Focus

1. Ordinary navigation removes roughly 65px: all panels must still fit at the
   actual 1920×1080 viewport, with an accessible fullscreen entry control.
2. Concurrent refresh failures expand map and metric messages: truthful text
   must remain readable without pushing panels into each other.
3. Long POI names, dates and planning identifiers: wrap without clipping values
   or introducing internal scrolling; fixed unavailable copy must stay readable.
4. Fullscreen exit, text enlargement and resize: preserve mounted chart/globe
   state, controls, persisted duration and the operator's chosen camera.
5. Bright terrain, dark ocean and unsupported blur: maintain text/trace contrast
   and geography visibility; measured lighting must not become an aesthetic fix.

## Selected baseline and migration inventory

GitHub `dev`, rechecked/fetched on 2026-10-02:
`d3862415cafbc96f5efce6b6d42c16e0b182f4e1` (PR #233, #218). Inspect immutable
sources with `git show <SHA>:<path>`; the current checkout is still
`feat/217-arrival-states` at `a0378890`, so do not infer baseline source from
its working files. #216 and #217 are already integrated; #218 code is also
integrated regardless of its issue's open roadmap label. No branch was created
for this draft. After approval, recheck `dev`, reconcile drift and use
`superpowers:using-git-worktrees` for an isolated implementation branch.

The source inventory below must be checked against the rendered baseline DOM at
execution before edits. Existing #218 captures are historical references, not
exact-`dev` acceptance for #219.

| Existing element                                                 | Disposition | Owner and destination                                                         |
| ---------------------------------------------------------------- | ----------- | ----------------------------------------------------------------------------- |
| `Canvas`, atmosphere, city lighting and stars                    | Reuse       | `OverviewPage.tsx`; full-size background within the page                      |
| Route, aircraft, GEP, track, satellite/link and POI scene layers | Reuse       | Existing projections/draw guards; retain geometry and labels                  |
| Four configured clocks                                           | Move        | `OverviewClockPanel`; compact top row with existing zones/failure text        |
| Native fullscreen button                                         | Move        | `OverviewFullscreenControl`; reserved right-column slot beneath planning card |
| Current network metrics box                                      | Remove      | Already absent after #216; assert absence rather than resurrecting it         |
| Five history panels and plot-only motion                         | Reuse       | `OverviewMetricHistoryPanels`; desktop left stack                             |
| Shared freshness/window header and accessible trace descriptions | Reuse       | Metrics group; keep exception space and actual selected duration              |
| Old three-column grid/repeated visible legends                   | Remove      | Already replaced; delete remaining obsolete desktop overrides if present      |
| Five-row Upcoming POIs table                                     | Replace     | Already replaced by #217; retain only `OverviewArrivalPanel`                  |
| Arrival projection/panel                                         | Move        | Existing derivation; bottom of the central space between side regions         |
| Planned satellite card                                           | Move        | `OverviewPlannedSatelliteCard`; upper right, honest empty/error states        |
| Conditional globe legend                                         | Move        | `OverviewMapLegend`; lower right                                              |
| Operational map exceptions                                       | Move        | `OverviewMapStatus`; above legend in the same lower-right group               |
| History duration selector and map diagnostics                    | Reuse       | Already in Configuration via #218; verify persisted editor and navigation     |
| POI/satellite accessible name lists                              | Reuse       | Existing noninteractive screen-reader lists; no legacy focusable controls     |
| Narrow fixed-canvas/flow fallback                                | Reuse       | Interim reachable single tree; explicit stage replacement belongs to #220     |
| Conflicting ordinary/fullscreen overlay rules                    | Replace     | `OverviewOverlayLayout.css`; one desktop fit regime                           |

Containing blocks: `.app-shell` uses `100dvh`; `.app-route-content` flexes below
navigation, scrolls and has paint containment. `.overview-page` is a positioned
size-query container. The current globe is fixed in flow and absolute in desktop
rules; overlay boxes are relative in flow and absolute in desktop rules. The
desktop minimum is currently 1140px container height ordinarily and 1080px in
fullscreen, which leaves ordinary 1920×1080 in scrolling fallback. Arrival has
its own inline-size container and a 700px/43.75rem stacking rule. Chart canvases
already have explicit uPlot sizing overrides; retain them.

Operational paths: Configuration owns the persisted history editor, four-clock
settings and map diagnostics; other navigation retains satellite/route/mission
selection. OrbitControls disables pan and retains damping, distance limits 3–28
and initial camera `[0, 0, 22]` with 45° FOV. Keep those contracts and the
accessible POI/satellite identities. No automatic follow, camera reset or
satellite-scale change is needed to deliver layout.

## File ownership and layout decisions

Paths below are relative to `frontend/mission-planner` unless explicitly rooted.

- `src/pages/OverviewPage.tsx`: compose existing components; add one
  `.overview-right-overlays` containing satellite wrapper, fullscreen control
  and map wrapper. Rename `.overview-bottom-overlays` to
  `.overview-metrics-overlays`; remove the superseded placement selector.
- `src/pages/OverviewOverlayLayout.css`: own desktop/flow placement, rail
  budgets and clock typography. One desktop container query requires both
  1500px/93.75rem width and 1012px/63.25rem height. Larger root text therefore
  selects reachable flow; smaller root text cannot defeat pixel fit floors.
- Desktop: 20px edges, clocks at top with 52px time, 16px label, 8px block
  padding and 4px label/time gap. Rail/right region start at 136px and end 20px
  above the container bottom. Metrics width 440px; header plus five equal cards
  with 8px gaps. Header block padding is 6px, with a one-row 18px refresh-error
  line at this width. Reserve at least 48px actual plot height in every card.
- Right region: 320px width; CSS Grid rows `auto auto minmax(12px, 1fr) auto`.
  Planning card occupies row 1, fullscreen button row 2, status/legend group row
  4; explicit 12px separation reserves the control without shortening the metric
  rail. Fullscreen removes that same button using its existing hook.
- Arrival wrapper: left inset 480px, right inset 360px, bottom 20px; center the
  existing content-sized panel within that region. At 1920px it has 1080px
  available width, allowing two sections without the narrow stacking rule.
- `src/pages/OverviewMetricHistoryPanel.css`: keep desktop titles at 26px,
  observed values at 36px, axis labels at 16px and messages at 13px/14px. Use
  4px block padding in desktop cards; retain the 28px message reserve and actual
  measured plot sizing. Update the shared fit query to match layout.
- `src/pages/OverviewArrivalPanel.css`: match the new desktop query; preserve
  section/countdown wrapping and phase/freshness text. Keep 26px headings, 36px
  countdowns and 18px secondary text as starting values.
- `src/pages/OverviewPage.css` and `OverviewPlannedSatelliteCard.css`: retain
  conditional legend styling; tune desktop samples/text to 18px/24px. Use
  smaller 24px fixed empty/loading/error copy. Selected IDs retain the prominent
  readout; IDs longer than 24 characters use 20px/24px wrapped text to preserve
  the control/legend budget. Derive state/long-ID classes from the existing
  state in `OverviewPlannedSatelliteCard.tsx`.
- `src/pages/OverviewVisualTokens.css`: retain the delivered 50% navy/10px
  backdrop glass and 90% opaque fallback initially. Tune only if bright/dark
  acceptance shows insufficient contrast; apply blur solely to backdrops.
- Tests: extend `src/pages/OverviewPage.layers.test.tsx`; add
  `tests/e2e/overview-desktop-composition.spec.ts`. Update obsolete geometry
  expectations in metric-cleanup/fullscreen suites and every test locator using
  the renamed metrics wrapper. Use existing fixtures and
  `support/globe-visual-ready.ts`; no new acceptance platform or subscriptions.
- Documentation: update repository-root `docs/features/overview.md` and add
  `docs/reports/2026-10-02-overview-desktop-composition.md`, indexed in
  `docs/reports/README.md`, when actual implementation evidence exists.

The central clear rectangle is bounded by metric right +20px, right-region left
−20px, clock bottom +20px and arrival top −20px. Record its real bounds; target
at least 900×500px at default-text 1920×1080. Do not move scene geometry or
force an entire global route onto the visible hemisphere. Use representative
valid route/aircraft/next-POI/destination fixtures to verify clear visible
context; manual orbit remains available for globe-occluded context.

## Task 1: Deliver the desktop frame without losing controls

**Files:** `OverviewPage.tsx`, `OverviewOverlayLayout.css`,
`OverviewMetricHistoryPanel.css`, `OverviewArrivalPanel.css`,
`OverviewPage.layers.test.tsx` and the new desktop browser suite.

**Interfaces:** Consume unchanged component props and query results from the
selected baseline. Produce one metrics wrapper and one right-region wrapper; no
component export or service signature changes. Browser geometry measures real
bounding boxes, scroll sizes and the Canvas/uPlot nodes.

- [x] Capture baseline DOM/controls at ordinary/fullscreen 1920×1080 and
      reconcile every inventory row before editing. Confirm Configuration has
      one labelled history editor, with current persisted value.
- [x] Add failing browser cases `ordinary desktop fits every overlay` and
      `fullscreen round trip preserves scene and history`. Assert four clocks,
      five plots, one planning card/legend/arrival, no legacy table/current box,
      no page/panel scroll and pairwise nonoverlap of visible panel/control
      bounds. Assert 440px rail, plots ≥48px and clear rectangle ≥900×500px.
      Retain DOM node identities across fullscreen entry/exit and check
      navigation restores.
- [x] Run the new cases from the frontend. Expected red: ordinary view scrolls
      under the current threshold; inspect actual failures.

      ```bash
      npx playwright test tests/e2e/overview-desktop-composition.spec.ts \
        --project=chromium --headed --workers=1
      ```

- [x] Implement the wrappers and single fit regime above. Remove old duplicate
      fullscreen/ordinary placement blocks and obsolete selectors. Preserve flow
      and chart sizing; do not hide obsolete trees or raise overlay z-index.
- [x] Extend the rendered component test for exactly one fullscreen entry,
      planning card, legend and arrival; retain Configuration history tests. Add
      browser cases for root text 8/12/16/24px, 1920×900, 1500×1080, 1536×1080
      and phone 390×844/844×390/360×800. Assert intended fit/flow, reachable
      controls/cards and no horizontal overflow; enlarged text uses flow.
      Ordinary/fullscreen 1500/1536×1080 use the frame at default text, with
      stacked arrival sections; containers below 1012px height use flow. At
      1920×1080, ordinary/fullscreen fit at roots 8/12/16px; 24px uses flow.
- [x] Run the new suite plus `overview-poi-responsive.spec.ts`,
      `overview-metric-cleanup.spec.ts` and metric-history-fullscreen coverage.
      Update old fallback expectations only where this slice intentionally
      changes them; retain containment/plot-motion assertions. Expected green:
      geometry, node retention and control access pass in both desktop modes.
- [x] Commit this usable frame as `feat(overview): compose desktop overlays`.
      Satellite/arrival semantics already landed; do not reintroduce interim
      panels.

## Task 2: Finish glass/readability and exception fit

**Files:** `OverviewPage.css`, `OverviewVisualTokens.css`,
`OverviewPlannedSatelliteCard.tsx`/`.css`/`.test.tsx`, desktop browser suite and
repository-root `docs/features/overview.md`.

**Interfaces:** Consume the existing planning-state discriminator, legend draw
guards and arrival state. Produce state-specific styling only; data contracts,
clock zones, network/position freshness and arrival derivation remain unchanged.

- [ ] Add failing `exceptions retain desktop fit` and
      `long content remains readable` cases: all query errors together, stale
      network/position, no route, no selected satellite, `UNAVAILABLE`, a
      128-character satellite ID and two 120-character POI/destination names
      with multi-day countdown/date text. Assert complete accessible copy,
      wrapping, no internal/page overflow and no overlapping panel bounds.
      Include destination-only and late departure.
- [ ] Run the new tests before styling. Expected red: fixed unavailable text or
      expanded right-region content violates the target hierarchy/fit assertion.
- [ ] Implement state styling and right-region typography above. Keep map
      exceptions separate from legend and planning claims. Tune spacing against
      measured bounds; retain visible stale/error text and the central clear
      area.
- [ ] Add/run `backdrop fallback preserves contrast and geometry`: disable only
      the existing optional CSSSupportsRule as in metric-cleanup coverage;
      assert computed 90% navy background and `backdrop-filter: none`. Capture
      bright terrain/dark ocean with and without blur; inspect actual images.
      Verify panel children/plots have no text-blurring `filter` and remain
      legible.
- [ ] Update desktop operation/fullscreen guidance: ordinary 1920×1080 now fits;
      entry control moved beneath planning card; Escape restores navigation.
      Document text/short-viewport flow and Configuration's persisted history
      path. Remove the superseded ordinary-view fallback claim and obsolete
      thresholds.
- [ ] Run focused card/layer/arrival/clock/fullscreen unit tests and the new
      browser cases; expected green without changing semantic derivation tests.
- [ ] Commit as `feat(overview): finish desktop panel readability`.

## Task 3: Verify exact-head rendering and preserve operational context

**Files:** Existing browser suites, new desktop suite, rooted report and index.
**Interfaces:** Use the final pushed candidate SHA and existing acceptance
workflow; report manifest links, actual CSS viewport, renderer and fixture use.

- [ ] Run `./tools/verify frontend` and
      `ACCEPTANCE_POLICY_BASE_SHA=<selected-base> ./tools/verify static` from
      root. Expected: unit/build and static gates pass. Run `git diff --check`.
- [ ] Run serial headed desktop, globe, clock, arrival, planned-satellite,
      metric-cleanup, metric-history/fullscreen and POI-responsive suites.
      Verify manual orbit/zoom pose survives fullscreen/resizing without
      remount; duration changes from Configuration resize the same mounted
      plots. Preserve stationary labels, plot-only translation, gaps, rebase and
      resize checks.
- [ ] At the exact pushed SHA capture CDP screenshots and a short recording:
      ordinary/fullscreen fit, day/night lighting, bright terrain/dark ocean,
      opaque fallback, long/stale/unavailable states and fullscreen round trip.
      Exercise history duration, sample gap/recovery, rebase and tab resume;
      inspect the recording. Record viewport bounds/scroll state and current SHA
      in evidence.
- [ ] Use the production Nginx/backend/Prometheus view for real-path smoke;
      identify intercepted fixtures separately. With valid visible-hemisphere
      route/aircraft/POI/destination data, verify operational labels/context
      remain outside panels. Check no-route aircraft/GEP and configured
      satellite detail paths; never fabricate valid simulation coordinates in
      production evidence.
- [ ] Obtain and record an operator ten-foot assessment. Physical distance and
      device interaction cannot be established by software screenshots. Existing
      #218 SwiftShader rebase failures remain a baseline limitation: reproduce
      unchanged baseline if encountered; never loosen assertions or claim motion
      acceptance passes. Resolve a regression before handoff; report
      baseline-only failures and acceptance limitations explicitly.
- [ ] Write the report/index with exact evidence links, checks, before/after
      disposition verification and outstanding limitations; no fabricated
      captures. Review final diff for obsolete wrappers/CSS and hidden focusable
      controls. Commit documentation, refresh exact-final-SHA evidence if
      sources change, and obtain independent whole-branch review using the
      selected execution method. Any push/PR follows the approved integration
      choice; no merge/deploy or closure of #210/#211/#213/#220 is implied. Stop
      for Brian's plan approval before Task 1.
