# Phase 2: Exact Fullscreen Layout

## Identity, input, and objective

Repository `bcl1713/starlink-dashboard`; PR
`https://github.com/bcl1713/starlink-dashboard/pull/143`; base `dev`; feature
`feature/react-operations-overview`. Reset baseline is
`07593c69040ad447000bf526d6453ec5c6faacfa`; archive source is historical SHA
`e649ce169cd5adcbdd83d6264290b30d5221599e` at expected ref
`archive/pr-143-pre-simplification-e649ce1`.

Input is Oracle's published, independently reviewed Phase 1 SHA from
`SESSION-HANDOFF.md`. Implement the overview's native browser fullscreen at
exactly 1920x1080 with no document scroll, without changing Phase 1 data
semantics. Oracle owns remote publication.

## Product and scope contract

Follow [the product contract](00-product-contract.md). At 1920x1080 native
fullscreen, exactly four clocks; current-position map; top-five applicable POIs;
latency current plus five-minute minimum/average/maximum; current download and
upload; GEP; obstruction; packet-loss current/average/maximum; selected refresh
interval; and last successful update or concise failure must all be visible at
once without scroll or disclosure. Each region has a non-zero bounding box
wholly within the viewport.

No root/document horizontal or vertical scroll is allowed. Passing by hiding
required content, clipping controls, unreadable global scaling, or disabling
keyboard access is forbidden. Fullscreen entry/exit preserves selected cadence,
layer/filter state, last-good data, and focus; API rejection has a visible
fallback.

`document.fullscreenElement` must equal the overview root. Route, recent track,
active-link, satellites, mission events, weather radar, and ancillary controls
are optional salvage and never Phase 1 or Phase 2 completion dependencies.

**In:** layout, component boundaries needed for layout, fullscreen
control/state, focused visual/accessibility tests, and minimal style tokens.

**Out:** changes to polling/API contracts, the retired six-viewport gate,
real-stack publication acceptance, Grafana parity/retirement, and operator docs.
Other widths receive bounded smoke/accessibility checks only.

## Advisory paths after inspection

Likely but non-binding:

- `frontend/mission-planner/src/App.tsx` and `src/App.css`
- `frontend/mission-planner/src/index.css`
- `frontend/mission-planner/src/pages/OverviewPage/`
- `frontend/mission-planner/src/pages/OverviewPage/OverviewPage.tsx`
- `frontend/mission-planner/src/pages/OverviewPage/overview-layout.css`
- `frontend/mission-planner/src/pages/OverviewPage/*.test.tsx`
- `frontend/mission-planner/tests/e2e/overview.spec.ts`
- `frontend/mission-planner/playwright.config.ts`

Inspect actual Phase 1 output before choosing files. Do not import the archive's
layout wholesale.

## Bounded TDD task order

**TDD expectation:** Each layout behavior starts with a deterministic component
or browser RED, reaches minimum GREEN without hiding required content, then is
refactored before rerunning dimensions, accessibility, and state checks.

1. **Measure current candidate.** Pin exact clean input; capture 1920x1080
   normal and native-fullscreen dimensions, overflow, every exact inventory
   region, focus order, and console errors. Retain exactly one viewport
   screenshot, never a full-page screenshot. Record gaps, not aesthetic guesses.
2. **Fullscreen state.** RED component/browser tests cover supported entry,
   change/exit events, rejected API fallback, unmount cleanup, focus movement
   and return, and retained product state. Implement minimally.
3. **Grid skeleton.** RED tests require the overview root to be the fullscreen
   element, all exact inventory regions simultaneously visible with non-zero
   boxes wholly within 1920x1080, and root/document dimensions within viewport.
   Implement explicit rows/columns and bounded `minmax(0, ...)` ownership.
4. **Map and rail.** RED tests assert dominant map/controls remain usable,
   Leaflet invalidates size after transitions, rail content is accessible, and
   no map/control box crosses or overlaps its allocated area.
5. **Metrics and freshness.** RED tests assert latency current plus five-minute
   min/average/max, download/upload, obstruction, packet-loss
   current/average/max, selected interval, and last success/concise failure stay
   visible and readable without disclosure or label overflow.
6. **Density and text.** RED tests cover long safe labels,
   unavailable/stale/error messages, browser zoom smoke, keyboard order, visible
   focus, contrast, reduced motion, and no inaccessible clipping.
7. **State continuity.** Exercise cadence `1/2/5/10/30/paused`, manual refresh,
   layer/filter changes, entry, active fullscreen, exit, and rejection. Assert
   data polling remains independent and never restarts in a burst.
8. **Bounded secondary smoke.** Run one normal desktop and one narrow-width
   smoke for reachability, no horizontal overflow, and accessible disclosure; do
   not recreate the six-viewport release matrix.
9. **Refactor and stabilize.** Remove incidental magic values, centralize layout
   tokens, keep files at or below policy limits, and rerun the exact oracle.

Every implementation task follows RED, GREEN, REFACTOR with a focused command
and cohesive commit. A screenshot supports but does not replace dimensions and
accessibility assertions.

## Exact checks

Minimum focused check after each change:

```bash
set -euo pipefail
cd frontend/mission-planner
npx vitest run src/pages/OverviewPage
npx playwright test tests/e2e/overview.spec.ts --grep "1920x1080|fullscreen"
```

Minimum phase-wide checks:

```bash
set -euo pipefail
cd frontend/mission-planner
npm run lint
npm run build
npx vitest run
npx playwright test tests/e2e/overview.spec.ts

cd ../..
pre-commit run --all-files
git diff --check
```

Use inspected script names if different and record substitutions. Browser tests
must request a 1920x1080 viewport and exercise the real Fullscreen API where the
runner permits it; a mocked unit test alone is insufficient. Assert
`document.fullscreenElement` is the overview root and record every exact
inventory bounding box and document/root `client*`/`scroll*` dimension.

## Independent gates

**Specification review first:** at the exact candidate SHA verify every required
region, no-scroll/no-overlap/readability, state/focus entry-exit-rejection,
secondary smoke boundaries, unchanged data contract, and honest test evidence.

**Quality review second:** inspect CSS/layout cohesion, semantic structure,
accessible naming/focus, resize/event cleanup, brittle pixel assumptions,
component/file size, and regression clarity. Reviewers do not edit. Any fix
creates a new SHA and invalidates both prior visual evidence and reviews.

## Public handoff, docs, cleanup, and stop

Oracle posts base/feature and exact input/output SHAs, changed paths,
focused/full results, 1920x1080 dimensions and screenshot paths,
state/accessibility results, review dispositions, docs impact, gaps, cleanup,
and next action.

Documentation impact is roadmap/handoff changes only if the contract changed;
operator instructions remain Phase 4. Remove task-owned browser profiles,
screenshots not retained as bounded evidence, reports, servers, and ports. End
clean.

Completion requires exact native-fullscreen 1920x1080 no-scroll bounding-box
PASS, state/focus PASS, focused/full checks PASS, spec then quality approval,
and an immutable clean candidate. Stop. Phase 3 starts in a fresh independent
session from Oracle's published Phase 2 SHA and performs real-stack acceptance;
Phase 2 does not self-certify it.
