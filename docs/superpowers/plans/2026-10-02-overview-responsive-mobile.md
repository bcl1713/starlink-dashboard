# Overview #220 Responsive Layout and Interaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> for native execution, or `superpowers:subagent-driven-development` if Brian
> selects delegation. Track the checkbox steps below.

**Goal:** Make all Overview content readable and reachable on phones and scaled
desktops, with deliberate map interaction and preserved camera/chart state.

**Architecture:** Retain one globe, one five-panel history group and the
existing queries/arrival derivation. Measure the shell's available content
viewport and select desktop, landscape stage/rail or stacked page flow. A
dedicated map controller owns gesture permission and camera intent; measured
element sizes continue to drive Three.js and uPlot.

**Tech Stack:** React 19, TypeScript, Three.js/React Three Fiber, Drei
OrbitControls, uPlot, CSS Grid, ResizeObserver, Vitest and Playwright Chromium.

**Spec:**
[Approved responsive Overview design](../specs/2026-09-30-responsive-overview-design.md)
and [issue #220](https://github.com/bcl1713/starlink-dashboard/issues/220),
including its scaled-desktop follow-up.

**Status:** Approved for implementation by Brian on 2026-10-02. Native execution
selected, with an independent whole-branch review. The draft was prepared before
worktree creation or product changes.

## Global Constraints

- Five graphs only: latency (ms), downlink (Mbps), uplink (Mbps), packet loss
  (%) and obstruction (%). Preserve observed-value provenance, separate
  network/position freshness, gaps and fixed trailing-five-minute statistics.
- Reuse the globe renderer, natural day/night illumination, route/satellite
  geometry, uPlot and shared subscriptions. No duplicate responsive trees,
  replacement libraries, new polling, backend/API changes or signal-quality
  readout.
- Preserve persisted history duration, arrival semantics and manual camera
  intent through rotation, fullscreen and resize. Configuration navigation can
  remount Overview; it proves persistence, not instance continuity.
- Portrait uses normal page flow with no metric scroller. Landscape uses a
  readable 210–240 CSS px rail and approximately 70–75% globe stage, falling
  back to stacked flow when either region cannot fit.
- Default responsive touch and wheel input scrolls content without moving the
  camera. Explore map scopes gestures to the globe surface. Keep browser zoom
  available, visible focus and at least 44×44 CSS px interactive targets.
- Preserve the accepted 1920×1080 ordinary/fullscreen desktop composition, 440px
  metric rail and existing deliberate desktop orbit/zoom.
- Exact pushed-SHA screenshots and rotation/scroll recordings are required for
  acceptance. Software emulation does not establish physical-device behavior.
- No merge, deployment, release to `main`, roadmap issue closure or unrelated
  #211 performance investigation is authorized by this plan.

## Review Focus

1. Scaled desktop/root text: actual viewport, root size and content height must
   explain layout selection; wheel input over panels, gaps and globe must have a
   consistent scrolling destination.
2. Browser chrome, safe areas and navigation: shrinking available height must
   select readable flow without camera resets or oscillating layout modes.
3. Long names, errors and enlarged text: complete arrival/planning/status copy
   must remain reachable without covering map controls or clipping countdowns.
4. Interaction changes mid-gesture: rotation, Escape, focus loss and layout
   changes must release pointer capture and leave scroll/focus usable.
5. Delayed/missing data and tab resume: chart resizing must retain gaps,
   provenance, stationary labels and bounded motion without replaying frames.

## Baseline and supporting contract

Selected `dev`: `fa1bba47844f329fb0d3ae4a7c1c4471526c52f2` (PR #237, #219),
fetched 2026-10-02. The original checkout remains `feat/217-arrival-states`; no
implementation branch was created. Recheck `dev` after approval.

Read the
[source and layout contract](2026-10-02-overview-responsive-mobile-source-contract.md)
with this plan. It defines the inspected baseline, one-tree file ownership,
exact initial layout floors, content-fit escape, scroll ownership, gesture and
camera intent, reduced motion and interfaces consumed by the tasks below. These
are implementation decisions for review, not measured browser acceptance.

Paths below are relative to `frontend/mission-planner` unless rooted otherwise.

## Task 1: Deliver measured portrait/landscape/fallback composition

**Files:** layout resolver/hook, Overview composition and CSS, shell fallback,
legend, label layout, responsive browser suite and supporting unit tests above.
**Interfaces:** consumes existing component/query props; produces one stable
stage, `data-layout` and safe rectangle for Task 2. Existing scene coordinates,
chart data and arrival state are unchanged.

- [x] Recheck `dev`, reconcile the approved plan and create an isolated
      worktree. Capture exact-base DOM/geometry at 1920×1080, 390×844, 844×390,
      360×800 and approximately 2000×1333 ordinary/fullscreen. Record actual
      inner/visual viewport, shell/Overview bounds, root font, DPR, zoom if
      known, hit targets and scroll owners; distinguish emulation from physical
      scaling.
- [x] Add failing `portrait uses page flow and reaches five charts`,
      `landscape keeps stage visible while rail scrolls` and
      `scaled desktop chooses measured readable layout` cases. At 390 assert 2×2
      clocks and two card columns; at 360 assert one card column; at 844×390
      assert one clock row, 210–240px rail and at least 560×220px stage. Scroll
      to each card/header/arrival/control, assert no horizontal overflow or
      clipped copy. Retain every canvas/uPlot node across mode changes and
      assert only one tree.
- [x] Add pure boundary cases for four retained desktop floors, landscape
      width/height/root-text floors and candidate overflow fallback; test
      704×900, 844×300, 1920×900 and roots 16/24/32px. Pin stable stacked
      fallback rather than repeated layout toggling under a growing
      long-name/error fixture.
- [x] Run red from frontend using the command below. Expected failures identify
      the fixed background/no bounded stage/current full-width flow, not a
      fixture or WebGL readiness failure.

      ```bash
      npx playwright test tests/e2e/overview-responsive.spec.ts \
        --project=chromium --headed --workers=1
      ```

- [x] Implement one stage and resolver, CSS modes and sole page scroll owner.
      Replace obsolete desktop guards consistently. Implement measured content
      escape to flow, safe-area/dynamic-height handling and conditional legend.
- [x] Extend POI placement tests for stage-origin conversion, reserved control,
      planning/arrival/legend rectangles and impossible packing. Recompute
      labels on actual stage/camera changes; preserve complete accessible marker
      names.
- [x] Add browser cases for long 120-character names, 128-character satellite
      ID, destination-only, late departure, no route, stale network/position,
      independent/all query errors and expanded legend. Require complete text,
      readable map-safe area or stacked escape, 44px controls and no nested map
      scroller. Simulate safe-area padding, navigation expansion, text
      enlargement and browser-height changes; verify observers settle.
- [x] Run resolver/label/legend/layer tests and responsive/arrival/POI browser
      suites. Expected green: one mounted tree, reachable content and correct
      scroll ownership. Keep existing desktop fit assertions at 1920×1080.
- [x] Commit as `feat(overview): compose responsive map stage and metrics`.

## Task 2: Make scrolling and map exploration deliberate

**Files:** map controls/controller, camera math, reduced-motion hook, plot and
scene consumers, interaction browser suite and relevant component tests.
**Interfaces:** consumes Task 1 mode/safe rectangle and existing source
snapshot; produces scoped gesture handling and camera intent without replacing
the Canvas or changing telemetry derivation.

- [x] Add failing `scroll over panels gaps and globe preserves pose`,
      `Explore scopes map gestures and exits accessibly` and
      `rotation preserves manual camera and plot identity` cases. Observe
      renderer pose without mutating it. Drive real mouse wheel/drag and CDP
      touch events, including portrait document scroll and landscape rail scroll
      to all five cards; assert scroll movement and unchanged camera in default
      responsive mode.
- [x] Exercise 2000×1333 ordinary/fullscreen at root 16/24px and representative
      shorter chrome-reduced heights. Desktop-fit view retains deliberate globe
      input; scrolling fallback sends panel/gap/globe wheel to page scroll.
      Check Ctrl/Meta wheel is not swallowed. Record actual layout/scroll
      bounds.
- [x] Add controls/controller tests for manual/automatic/follow transitions,
      failed/stale/missing position, mid-pointer Escape/blur/rotation and focus
      return. Camera-fit math tests cover aspect, safe-area bounds, distance
      clamps, absent aircraft and unchanged manual intent on minor height
      changes.
- [x] Run failing cases before controller edits. Expected red: default input
      changes the camera, no Explore exit path and no responsive framing policy.
- [x] Implement controls/intent and one gated OrbitControls. Ensure pointer
      capture cleanup also works when the viewport changes during a gesture.
      Scope landscape wheel forwarding to stage/gaps in scroll mode; preserve
      native rail behavior and browser zoom. Implement automatic frame fitting
      and Configuration opt-in following with unavailable reason; retain manual
      pose.
- [x] Add/run reduced-motion tests for initial/change preference: no continuous
      plot transform transition or optional scene motion; new data/gaps/time
      bounds still update, renderer/uPlot identities persist. Apply preference
      via one cleanup-safe hook; leave normal-preference motion contract
      unchanged.
- [x] Verify real uPlot/Three.js sizes at DPR1/2/1.5 after repeated rotation.
      Plot viewport width determines `width/windowSeconds` motion rate and
      overscan; canvas CSS bounds and drawing buffer match the selected DPR.
      Assert stationary headings/axes and retained timestamps across
      rebase/resize without stretch.
- [x] Exercise saved/custom duration, missing samples/recovery, delayed polls,
      visibility resume and interrupted rotation. Keep five-minute rollup
      meaning; no new per-panel requests, animation-frame uploads or queued
      replay.
- [x] Run interaction, metric-history/fullscreen, desktop/globe and focused
      camera/control/retention suites. Update hit-target assertions only for the
      intentional scroll policy; do not weaken motion/provenance oracles.
- [x] Commit as
      `feat(overview): scope map exploration and preserve camera intent`.

## Task 3: Verify exact-head behavior and document operation

**Files:** browser suites/support, rooted Overview/architecture docs,
report/index. **Interfaces:** consumes final implementation SHA, geometry logs
and existing acceptance tooling; produces reviewable evidence with
source/runtime identity.

- [ ] Run `./tools/verify frontend`,
      `ACCEPTANCE_POLICY_BASE_SHA=<selected-base> ./tools/verify static` and
      `git diff --check`. Expected: canonical unit/build/static checks pass;
      diagnose failures without skipping gates or relaxing existing assertions.
- [ ] Run serial headed responsive, interaction, desktop composition, globe,
      clock, arrival, planning, metric-cleanup, metric-history/fullscreen and
      POI-responsive coverage. The #219 report records SwiftShader
      painted-rebase and intermittent DPR2 failures: if encountered, reproduce
      unchanged selected base separately. Fix regressions; record baseline-only
      limits honestly.
- [ ] Prepare isolated production Nginx/backend/Prometheus smoke using existing
      acceptance conventions. Read cloud Docker proxy/CA guidance first;
      preserve `DOCKER_HOST`/context and discover the actor-owned runtime
      socket. Use task-specific project/volumes/loopback ports. Verify real
      history persistence, mobile navigation, freshness and unavailable paths;
      identify intercepted route/aircraft/POI fixtures separately from actual
      production responses.
- [ ] After authorized publication, capture the exact pushed candidate SHA at
      390×844, 844×390, 360×800 and ordinary/fullscreen 1920×1080. Capture the
      scaled-desktop reproduction with actual viewport/container/root/DPR/zoom
      measurements. Approximate 2000×1333/DPR1.5 emulation does not prove
      Brian's 3000×2000 physical display at 150% system scaling; request his
      actual-device check after publishing a concrete candidate.
- [ ] Record rotation, page/rail scroll through all five charts, Explore
      enter/exit, manual pose retention, Follow availability/failure and
      fullscreen round trip. Include bright terrain/dark ocean, opaque blur
      fallback, long content, stale/unavailable state, sample gap/recovery and
      tab resume. Inspect stills and recording; record browser/version/renderer,
      CSS/drawing-buffer dimensions, API/fixture provenance and immutable source
      identity in manifest.
- [ ] Update operator guidance for mobile navigation/history settings, portrait
      page versus landscape rail scroll, Explore/Exit/Reset and configured
      following, expandable legend, reduced motion and separate network/position
      freshness. Document the actual resolver thresholds, content escape and
      shell scroll owner; remove the superseded fixed-background mobile claim.
- [ ] Write report/index with exact evidence links and results/limitations.
      Obtain independent whole-branch review using the approved execution
      method. Any publication for review requires the selected integration
      authorization; no merge or deployment is implied. Refresh exact-final-SHA
      evidence if sources change, and keep physical-device validation explicitly
      pending until supplied.
- [ ] Commit documentation as
      `docs(overview): explain responsive map operation`.

## Plan self-review and handoff

Coverage maps portrait/landscape/scale and long-content fit to Task 1; input,
camera, rotation, motion and all five Review Focus cases to Tasks 1–2;
exact-head production/browser/operator evidence and documentation to Task 3.
Source freshness remains independent from camera convenience. Layout observes
the bounded shell, never its own growing content; manual camera survives resize;
Following defaults off in Configuration; reset fits the route once, as Brian
clarified during implementation. All automatic moves ease; manual input cancels.

Brian approved implementation on 2026-10-02 and delegated execution-method
choice; native execution with one final independent review was selected.
Publication, merge and deployment remain separate integration actions.
