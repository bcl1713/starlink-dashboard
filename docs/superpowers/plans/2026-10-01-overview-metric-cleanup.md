# Overview #216 Cleanup Plan

**Status:** Brian authorized implementation and a PR after reviewing this plan
and the supplied screenshot. Implementation targets `dev`; no merge, deployment
or issue closure is authorized.

**Goal:** Make the five metric panels readable from roughly ten feet and
visually close to the desktop concept in
[#213](https://github.com/bcl1713/starlink-dashboard/issues/213). Establish
shared visual choices that #217–#220 can reuse without redesigning each panel.

**Baseline:** `dev` at `8c963f55e1a7a4d96314351d058130720742efc6`, the merge of
PR #228. The GitHub branch ref and relevant files were inspected at this SHA.
The local checkout is older; do not implement from its current `HEAD`.

**Design authority:** The approved
[responsive Overview design](https://github.com/bcl1713/starlink-dashboard/blob/8c963f55e1a7a4d96314351d058130720742efc6/docs/superpowers/specs/2026-09-30-responsive-overview-design.md)
and its metric-provenance amendment. This is a follow-up to the delivered #216
data/chart work, not a repeat of its original source-contract plan.

**Visually inspected reference:** Brian supplied `1000001637.jpg`, a 1280×720
rendition of the concept, after the repository PNG could not be retrieved
through the connector. The attachment was inspected directly and the plan below
reconciled with it. The original #213 reference remains
`issue-assets/213/inspo.png` on `issue-assets/213-globe-first-concept`, blob
`7be91f3401e64ae8724de6f21be4f7e1330897dc` (1672×941). Neither image is an
application capture; sample values, routes and clock locations are illustrative.
Its sixth signal-quality chart remains excluded. Capture the actual application
at 1920×1080; do not upscale either illustration and call it verification.
Attachment SHA-256:
`c872166fa4a09a6b0fa7dcebf95081525b7f593484488bda949401c1b7b75403`.

## What changes

The normal display shows a full-background globe, existing top clocks, and one
left column containing five matching glass cards. Match the reference's
upper-left alignment: a short uppercase metric title, the large current value
directly below it, then the wide history graph. Do not right-align the value
opposite the title. Sparse numeric y labels sit beside the graph; there is no
per-card time footer. All text and exceptional states stay stationary. Fresh
timestamps, duplicate units and trace legends stop competing with the value.

This plan intentionally brings the metric column and shared surface styling
forward from #219. Full desktop composition, clock typography/camera tuning, and
the final arrival/satellite/legend layouts remain later work. Move the existing
POI table intact to the bottom-center region to make room; do not change its
five-row content, ETA behavior or expand/collapse behavior here.

### Shared visual foundation

Create Overview-scoped CSS custom properties in
`src/pages/OverviewVisualTokens.css`, imported once by `OverviewPage.css`. Apply
them to metric cards/context and the existing clocks, POI surface, legend and
fullscreen control. Share surface styling now; preserve those other components'
content and internal typography until their own slices. Use the same tokens for
future arrival and satellite cards; avoid a wrapper component or a new global
design system.

| Choice        | Starting target, tuned in the actual browser                  |
| ------------- | ------------------------------------------------------------- |
| Glass         | Charcoal/navy, about 80–84% opacity; transparent plots        |
| Backdrop      | 16px blur; blur geography behind panels, never text or traces |
| Fallback      | About 94% opaque navy when backdrop filtering is unsupported  |
| Border        | 1px cool blue-gray border, about 20–30% opacity               |
| Shape         | 14px corners, restrained dark shadow, no bright outer glow    |
| Spacing       | 20px desktop outer margin; 8–10px card gaps; 10–12px padding  |
| Main text     | Near-white; tabular numerals; restrained medium/bold weight   |
| Secondary     | Muted cool gray with readable contrast on bright/dark terrain |
| Metric title  | Start at 26px; uppercase with restrained tracking             |
| Current value | Start at 36–40px; unit smaller but plainly readable           |
| Context/axes  | Start at 16–18px; no dense explanatory paragraphs             |
| Observed      | Existing cyan, 2.25px stroke, no point markers                |
| Average/band  | Existing dashed subdued white and translucent gray envelope   |

Treat the sizes as a hierarchy and browser-tuning budget, not acceptance by CSS
declaration alone. Keep meaningful visual differences for unavailable states;
color is supplemental to text. Retain visible keyboard focus. Match the
reference's flat navy tint and faint blurred geography behind cards. Use a
narrow header, aligned card edges and consistent inner left alignment; avoid
heavy gradients, prominent glow, opaque plot rectangles or bulky badges. Keep
the strong globe geography and day/night contrast visible around panels.

### Information and number formatting

- Visible titles: `Latency`, `Downlink`, `Uplink`, `Packet loss`, `Obstruction`.
  Preserve complete metric names in accessible descriptions and documentation.
  Keep the descriptor IDs and Prometheus metric keys.
- Put the current value and its unit together once. Remove the extra unit from
  the title and repeated units on both y-axis bounds. The accessible chart
  description still identifies the unit and scale.
- Latency: whole milliseconds. Downlink/uplink: at most one decimal Mbps. Packet
  loss/obstruction: at most two decimal percentage points. Trim trailing zeros
  and normalize rounded negative zero. Examples: `7.49 → 7 ms`,
  `53.347 → 53.3 Mbps`, `0.236 → 0.24%`, `3 → 3%`.
- A genuine zero stays `0`. A positive value below one displayed increment uses
  `<1 ms`, `<0.1 Mbps` or `<0.01%`, so rounding does not imply zero. Never
  substitute a missing/non-finite value with zero. Preserve signs for unexpected
  finite negative values rather than silently clamping data.
- Add a pure formatter in `overview-metric-format.ts`. Use it for fresh and
  last-known values, with deterministic decimal separators. Formatting must
  never mutate raw history, readout values, aggregates or y-domain values.
  Extreme finite magnitudes need a readable scientific-notation fallback and a
  complete accessible value, rather than overflow or truncation.
- Use sparse zero/midpoint/upper y labels with subtle stationary horizontal
  reference lines, as in the image. Drop the midpoint only when unreadable. Axis
  formatting must describe the actual domain; do not round an axis to a
  misleading different bound or use `<...` there. Keep obstruction 0–100% and
  the existing stable packet-loss range; no new scale policy.
- Remove visible per-card time labels and repeated `Time (UTC)` footers,
  matching the reference. Keep full UTC bounds in accessible chart descriptions,
  derived from the existing visible plot edge, not a new wall-clock
  approximation. The selected display duration stays visible once for the group.
  Do not introduce a shared clock/lifecycle refactor.
- Make the group context a slim strip: network freshness and observation age on
  the left; display duration and `Rolling: 5 minutes` on the right or a compact
  second line. For example, `NETWORK · UPDATED 1s AGO`,
  `Display: 30 min · Rolling: 5 min`. Derive age from accepted verified status,
  never request completion or history evaluation time. Use explicit stale,
  partial and unavailable wording; show no update age without an observation.
  The image's ambiguous `LAST 5 MIN` must not replace the two distinct windows.
  Consolidate global status/history failure messages here.
- Remove the always-visible trace key and fresh per-panel `Observed ... UTC`
  line. Keep provenance and trace meanings in accessible descriptions and user
  guidance; no hover-only requirement for operational information.
- A fresh metric has no extra status prose. A stale metric still has prominent
  `Unavailable` and secondary `Last <formatted value> · <age> old`. A metric
  with no verified observation has `Unavailable` without invented age/value.
  Keep a short per-metric aggregate/history exception where the group cannot
  express the difference. Reserve room so failures do not unexpectedly increase
  card height or push another chart offscreen.

## Composition and preserved behavior

At a true 1920×1080 page viewport, start with a 420–440px left column about 20px
from the edge, below the clocks with 16–24px clearance. A roughly 48–68px group
header and five roughly 156–172px cards should fit with 8px gaps and a
bottom/control reserve. Start graphs around 56–64px high; prefer extra graph
height when actual available space permits it. Tune measured geometry rather
than shrinking the values to force a fit. Use the six-card illustration as a
density guide, not a reason to add a sixth card or leave a signal-quality
placeholder. Five cards can use the freed space for readability and chart height
while preserving the central globe.

Use the desktop column in ordinary and native-fullscreen views when actual
content width/height support it. The app shell may reduce ordinary content
height; measure that space rather than assuming screen size equals viewport.
Keep native fullscreen entry/exit and shell hiding. Reserve space for its
control in ordinary view. No page/internal metric scrolling at the target
fullscreen viewport; no overlay overlap or obscured controls.

Decouple metric and POI wrappers in `OverviewPage.tsx`. Place the intact POI
panel bottom-center, outside the left column and right legend, with its existing
usable table width (start around 720px). Its current large table is
transitional; #217 replaces the content with the arrival strip. Keep broad
central globe space above it. If actual ordinary/short-screen geometry cannot
fit, retain a readable document-flow fallback with no horizontal overflow; do
not silently hide rows or shrink ten-foot text. Preserve narrow-screen normal
document scrolling and phone-sized text. #220 still owns the mobile globe stage,
rail, touch mode and rotation design.

Keep one React tree and the existing subscriptions, globe camera/lighting, route
geometry, position freshness, POI derivation, planned link semantics, history
selector and persistence. #218 relocates the selector and simplifies legend
content. Do not mount separate fullscreen/mobile panels.

Preserve #228: `/api/status` remains latest-value authority with explicit
availability, monotonic accepted observations, a 10-second stale boundary, up to
5 seconds of future skew, and clamped displayed age. Status and history errors
remain independent. Keep the shared bounded history/cache pipeline, 5-second
default and 1-second opt-in; no polling/backend changes.

Keep existing uPlot band order, null gaps, real spikes, retention, overscan,
plot-only CSS motion and same-frame rebase. Resize must update measured plot
width/height and motion rate together. Titles, values, axes and surfaces never
enter the translated data layer. No per-frame data upload, extra query,
fabricated future extension or claim of seamless arbitrary-outage recovery.

## Implementation tasks

Paths below are relative to `frontend/mission-planner/`, except `docs/`. Use
focused RED/GREEN checks for changed behavior and rendered checks for
appearance. Record each task's result and relevant limitations in the PR.

### 1. Pin the base and formatting contract

- [x] Recheck then-current `dev`; compare the supplied, inspected concept
      against this contract and reconcile intervening changes. Use an isolated
      feature checkout; do not code on the stale local baseline.
- [x] Add `src/pages/overview-metric-format.ts` and `.test.ts`. Cover decimal
      rounding, zero, tiny positives, trailing zeros, negative zero/signs, large
      finite values, and no mutation. Keep availability decisions in readout
      projection, outside formatting.
- [x] Use the formatter in `OverviewMetricHistoryPanel.tsx`; update focused
      component expectations for fresh and stale examples. Preserve data shapes.

### 2. Simplify panels and shared context

- [x] Modify `OverviewMetricHistoryPanels.tsx`, its `.test.tsx` and
      `.retention.test.tsx`, `OverviewMetricHistoryPanel.tsx` and `.test.tsx`,
      and presentation labels in `overview-metric-history.ts`.
- [x] Implement the information hierarchy above. Keep existing classes and data
      selectors where their meaning remains valid. Move provenance checks from
      assertions on always-visible timestamp prose to accessible content; retain
      acquisition-time ordering and stale-boundary assertions.
- [x] Check all-fresh, partial, all-stale, unavailable, failed status refresh,
      history-only failure, metric-specific aggregate loss and recovery. Verify
      source-zero versus missing, skew allowance, and out-of-order retention.
      Test that shared update age uses accepted observation time and disappears
      when no verified observation exists; it must not borrow fresh history age.
      A fresh status must not conceal stale or missing chart history.

### 3. Apply glass styling and desktop metric placement

- [x] Create `OverviewVisualTokens.css`; modify `OverviewPage.css` and
      `OverviewMetricHistoryPanel.css` to consume it. Add subtle horizontal
      reference lines in a stationary CSS layer behind the translated plot,
      aligned with its measured height and y-domain. Do not put moving vertical
      gridlines into the data surface. Leave uPlot options and scale/data
      semantics intact.
- [x] Modify `OverviewPage.tsx` to separate metric and POI placement. Update
      `OverviewPage.contract.test.ts` for the new structural seam while
      retaining shared subscriptions and existing globe/route/POI semantics.
- [x] Remove conflicting fullscreen compact rules. Choose fit breakpoints using
      actual available content geometry, keeping the short/narrow fallback.
      Verify no state change remounts the globe or the five chart trees.

### 4. Browser evidence, documentation and review

- [x] Update `tests/e2e/overview-metric-history.spec.ts` and
      `overview-metric-history-fullscreen.spec.ts`: replace old above-POIs
      layout assertions with measured separation, five visible/readable cards,
      and intact POIs. Retain painted-motion/gap/rebase checks; avoid loosening
      them.
- [ ] Capture actual 1920×1080 ordinary and native-fullscreen views, bright
      terrain/dark ocean, blur fallback, populated/empty POIs and all metric
      state cases. Record viewport, DPR, exact SHA, source mode and renderer.
      Compare beside the concept for hierarchy, glass, spacing and globe
      prominence.
- [ ] Capture a short motion recording across two refreshes, a gap/recovery,
      resize, duration change and tab resume. Exercise 1s and 5s incoming
      bundles and DPR 1/2. Check measured plot motion, stationary labels,
      clipping and resize/rebase continuity. Verify new styling does not cause
      data uploads on status-only ticks. Report existing delayed-outage limits
      honestly.
- [ ] Smoke-check 390×844, 844×390 and a short desktop viewport for readable
      fallback, reachable panels, keyboard controls and no horizontal overflow;
      these are regression checks, not completion of #220. Obtain an operator
      ten-foot readability check; software-rendered screenshots cannot prove it.
- [x] Update `docs/features/overview.md` for precision, accessible trace and
      timestamp context, exception wording, and transitional desktop placement.
      Add this narrowly advanced visual foundation/placement boundary to the
      responsive design so #217–#220 inherit it without conflicting scope
      claims.
- [ ] Run relevant checks and independent review at the exact pushed head.
      Target `dev`; document remaining #217–#220 work. No merge/deploy is part
      of this plan. Do not close #213, #210, #211 or performance follow-up #224.

## Verification and completion criteria

Run focused changed formatter/component/retention tests first, then from the
repository root `./tools/verify frontend`. Run frontend ESLint and changed-file
Prettier; lint changed Markdown and check `git diff --check`. Required static CI
remains applicable; its local canonical command requires an exact reachable
`ACCEPTANCE_POLICY_BASE_SHA`. No backend/API change or backend rebuild is
planned. From `frontend/mission-planner`, run the existing serial headed suites:

```bash
npx playwright test --project=chromium --headed --workers=1 \
  tests/e2e/overview-metric-history.spec.ts \
  tests/e2e/overview-metric-history-fullscreen.spec.ts \
  tests/e2e/overview-globe.spec.ts \
  tests/e2e/overview-poi-responsive.spec.ts
```

Browser fixtures prove their exercised contracts, not the production proxy path.
Verify a clean exact-SHA production Nginx/backend/Prometheus view too. The
baseline has no sealed Overview acceptance contract; do not present an unrelated
final lane as acceptance. Follow the applicable acceptance workflow and report
fixture/production and software/hardware rendering separately.

Complete when all five metric cards fit and remain legible, capped values never
hide tiny loss as zero, freshness/missingness stays truthful, existing
motion/resize tests pass, and captured rendering shows the shared glass style
and broad globe composition. Include before/after evidence and unresolved
limitations. Implementation is complete; full-scene acceptance remains pending.
