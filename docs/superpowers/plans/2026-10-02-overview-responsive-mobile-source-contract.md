# Overview #220 Responsive Source and Layout Contract

**Status:** Approved supporting contract for the
[implementation plan](2026-10-02-overview-responsive-mobile.md). Review both
documents before execution; Brian approved implementation on 2026-10-02.

## Selected baseline and source findings

Fetched GitHub `dev` on 2026-10-02: `fa1bba47844f329fb0d3ae4a7c1c4471526c52f2`
(PR #237, #219). #216–#219 are integrated. The original checkout remains
`feat/217-arrival-states` at `a0378890`; inspect selected sources with
`git show <base>:<path>` rather than using that checkout's old component files.
Re-fetch/reconcile `dev` after approval, before creating an isolated
implementation worktree.

Current fallback findings:

- `OverviewOverlayLayout.css` keeps the globe fixed behind relative full-width
  panels. Metrics and arrival wrappers use `pointer-events: none`.
- `OverviewPage.tsx` always enables OrbitControls. Wheel/drag events reaching
  the fixed canvas can operate it while the operator intends to scroll.
- `.app-shell` has `100dvh`; `.app-route-content` already provides a bounded
  scroll viewport below navigation. Overview also has its own overflow owner.
- Desktop requires both 1500px/93.75rem width and 1012px/63.25rem height. A
  nominal 2000×1333 viewport satisfies the pixel floors at a 16px root, but may
  fail the font-relative floors or actual available-height budget. The reported
  fallback's exact cause is not yet a measured browser finding.
- Five uPlot instances already use measured plot `clientWidth/clientHeight` and
  `setSize`, with shared width-derived overscan/rebase. No reduced-motion
  preference is currently consumed by the plot component.
- POI collision layout currently compares labels with `window.innerWidth` and
  `window.innerHeight`; those are insufficient for a bounded mobile stage.
- Desktop `OverviewMapLegend` is always expanded. Planning and arrival
  components already contain truthful exception states and complete names.
- Initial camera is `[0, 0, 22]`, FOV 45°, pan disabled, distance range 3–28.
  There is no existing Follow aircraft control to relocate.

These are source observations. The prior #219 report/evidence is historical; it
does not establish exact-base responsive rendering. Its local CDP endpoint was
unavailable during planning. Execution starts with baseline reproduction,
including an operator's actual scaled-display measurements.

## Layout and input decisions

Paths below are relative to `frontend/mission-planner` unless rooted otherwise.

### One tree and one page scroll owner

Keep clocks and metrics as page siblings. Add `.overview-map-stage` containing
the existing Canvas, planning/right group, arrival and map controls. This is a
stable parent across modes, not conditional rendering or DOM reparenting. Keep
accessible POI/satellite lists mounted. Native fullscreen still targets
`document.documentElement` and restores navigation on exit.

Measure `.app-route-content` client width/height through a page ref's parent,
plus computed root font size and safe-area padding. Do not measure growing page
scroll height as available viewport height. Expose one `data-layout` on
Overview; replace the repeated desktop size-query placement/typography guards
with that same selected mode across layout, metric, arrival, legend and planning
CSS. Retain the arrival inline-size container.

In stacked mode, `.overview-page` has auto height/min-height 100% and visible
overflow; `.app-route-content` is the sole page scroll owner. Keep a stable
bounded shell measurement even as content grows. Desktop and landscape use
height 100%; landscape metrics alone own their intentional rail scrolling. Avoid
a second Overview scroller inside the shell.

Use this initial resolver policy, pinned by unit tests and tuned only against
rendered fit with documented reasons:

- Desktop retains the four existing pixel/font-relative minimums and 20px edges.
  Never infer system scaling from `devicePixelRatio` or multiply CSS dimensions
  by 1.5. Text or content that exceeds its desktop fit budget selects reachable
  stacked flow, with a stable fallback until that fit input changes.
- Landscape requires usable content width at least 800px, height at least 300px
  and at most 600px, four compact clocks fitting a single row, a rail
  `clamp(210px, 28% of usable width, 240px)` and remaining map width at least
  560px after a 12px gap. Require an actual post-clock stage height at least
  220px; otherwise stack. Use font-relative equivalents of readability minima as
  additional floors for enlarged text. At 844×390 ordinary/default text the
  target is landscape; 704px width and insufficient-height cases stack.
- All other available sizes use stacked flow. Constrain the main content to
  1200px and center it on a wide fallback desktop. Metrics use auto-fit columns
  with a 170px/10.625rem minimum and 8px gaps: two at 390px and one at 360px
  under default text/12px edges. Do not let wide fallback cards fill 2000px.
- Portrait clocks use 2×2 at normal phone text, one column if enlarged text
  cannot fit. Landscape clocks use one row. Labels initially use 12–14px, metric
  titles 14–16px, values 22–28px and clocks 20–24px; honor text enlargement.
- Portrait stage starts at 320–380px height, using available dynamic viewport
  height, safe-area padding and `vh` before `dvh` fallback declarations.
  Preserve at least a 120px-high map-safe rectangle. Planning is upper corner,
  controls occupy their own reachable row, arrival is bottom and legend is
  expandable. Normal short next/landing sections use compact columns where they
  fit.
- Measure overlay rows: if long text, expanded legend or concurrent failures
  consume the map-safe rectangle, put those same elements in stage flow and
  allow stage/page growth. In landscape, select stacked mode instead of
  shrinking or internally scrolling map/arrival content. Keep status text
  visible independently of the collapsed legend.

Fit feedback compares intrinsic panel sizes with the candidate geometry. Do not
let applying stacked CSS immediately select landscape again: reset an overflow
fallback only on viewport/root-text/content/disclosure changes, and test
settling without a ResizeObserver loop.

### Explore map and camera intent

Scrolling layouts start with OrbitControls disabled and the map surface using
`touch-action: auto`. Panels/controls remain hit-testable; decorative samples
alone can pass pointer events. No global wheel/pointer prevention. Mouse wheel
over the stage in stacked mode scrolls the page. In landscape, wheel over the
stage/gaps forwards to the single rail only when needed, without preventing
Ctrl/Meta wheel zoom; native rail wheel remains native and boundary behavior is
tested. Touch rail scroll remains local; stage touches retain browser behavior.

`Explore map` is a pressed-state button enabling orbit/zoom only on the canvas
interaction surface, which can then use scoped `touch-action: none`. Overlays
continue to scroll and never feed map controls. Provide `Exit map exploration`
and Escape dismissal with focus restoration. Disable controls and release
capture on mode exit, blur and layout changes. Keep the manual pose when
exiting; rotation exits gesture capture without resetting that pose.

Brian clarified camera behavior during implementation on 2026-10-02. Initial
framing prefers the route's projected extents within the clear panel-safe area,
including the left desktop rail; it need not place the route at screen center.
Without a route, center on valid aircraft, otherwise retain globe orientation.
The first usable route recovered after an initial fallback may receive one eased
automatic fit. Manual intent prevents this recovery movement. Desktop retains
Reset and the configured-follow status while hiding only the Explore toggle.
Position updates leave this view still by default. `Reset map view` performs a
one-time fit. Continuous following is off by default and selected explicitly in
Configuration, with a browser-local saved preference. Manual input pauses it;
reset resumes it when enabled. Fresh-map status governs following independently
from arrival/GPS provenance. Missing/stale/failed status freezes the pose with a
visible reason. Do not borrow another source's timestamp.

All automatic framing/reset/follow movements use an eased transition, canceled
immediately by manual input. A meaningful stage/overlay change can reframe an
automatic view; manual intent retains position, quaternion, target and zoom
through rotation/fullscreen/chrome changes. Projection aspect still updates. The
clarification supersedes preserving the historical `[0,0,22]` initial view; FOV,
orbit limits, scene coordinates, route geometry and desktop panel layout remain.
A globe-spanning route may have far-side occlusion; no route flattening or
substituted geometry is introduced.

Reduced motion removes continuous CSS plot translation and optional decorative
scene flow/star motion, using truthful discrete time/data updates. Camera
reframing is immediate. Preference changes apply without remounting or altering
data/polling. Preserve existing motion behavior when the preference is absent.

## File ownership and interfaces

- `src/pages/overview-responsive-layout.ts` (new): pure
  `resolveOverviewLayout(input: OverviewLayoutInput): OverviewLayoutMode`; mode
  is `'desktop' | 'landscape' | 'stacked'`. Input contains available CSS
  width/height, root font size, measured clock/overlay heights and content-fit
  flags. Keep eligibility calculations and fit fallback here.
- `src/pages/useOverviewLayout.ts` (new): shell/stage measurements, observer
  cleanup and stable fit feedback. Returns mode and stage-local safe rectangle
  `{ x: number; y: number; width: number; height: number }` in CSS pixels.
- `src/pages/OverviewPage.tsx`: stable composition, existing query consumers,
  `data-layout`, refs and controller inputs; no new queries or arrival math.
- `src/pages/OverviewOverlayLayout.css`, `OverviewPage.css`,
  `OverviewMetricHistoryPanel.css`, `OverviewArrivalPanel.css`,
  `OverviewPlannedSatelliteCard.css`: mode placement/phone typography, one page
  scroll owner, bounded rail, safe areas and fit feedback classes.
- `src/index.css`: add `100vh` fallback before existing `100dvh`; retain shell
  navigation and bounded route-content behavior for other pages.
- `src/pages/OverviewMapLegend.tsx`: optional `collapsible?: boolean` (default
  false), one conditional layer list, expanded button state, Escape/focus
  behavior and 44px target. Preserve all existing draw-guard props.
- `src/pages/OverviewMapControls.tsx` (new): accessible DOM controls consuming
  mode/intent/availability and callbacks; no Three.js or network ownership.
- `src/pages/OverviewMapController.tsx` and `overview-camera-frame.ts` (new):
  controller inside Canvas receives mode, safe rectangle, existing projected
  aircraft coordinate, source timestamp/error and controlled camera intent
  `'automatic' | 'manual' | 'follow'`; pure camera-fit math is separate. Own one
  OrbitControls instance with existing pan/damping/distance contracts.
- `src/pages/overview-poi-label-layout.ts` and its call site: extend
  `layoutOverviewPoiLabels(labels, viewport, reservedBounds?)` with optional
  blocked rectangles in the same coordinate space. Keep existing callers
  compatible; compare against stage bounds and actual overlay rectangles,
  remeasure on settled resize/camera movement, retain accessible fallback.
- `src/hooks/usePrefersReducedMotion.ts` (new): shared matchMedia subscription
  and cleanup; feed plot/controller and existing decorative scene consumers.
- `src/pages/OverviewMetricHistoryPanel.tsx`: preference-aware motion only;
  retain ResizeObserver, uPlot instance and unchanged-domain/rebase rules.
- Tests: pure layout/camera/label tests; map controls/legend/controller tests;
  existing layer/fullscreen/retention tests; new
  `tests/e2e/overview-responsive.spec.ts` and
  `tests/e2e/overview-map-interaction.spec.ts`. Reuse
  `tests/e2e/support/overview-composition.ts` and globe visual readiness; add a
  shared read-only renderer-pose observer for browser tests, using the #219
  devtools-hook approach rather than product debug state.
- Rooted docs: `docs/features/overview.md`, relevant camera/scroll architecture
  guidance, `docs/reports/2026-10-02-overview-responsive-mobile.md` and report
  index. No API documentation changes without an actual contract change.
