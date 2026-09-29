# Overview metric-history graphs — Integration task 5

> This task file extends
> [the implementation plan](./2026-09-29-overview-metric-history.md). Read its
> spec, global constraints, interfaces, and Review Focus first.

## Task 5: Five-panel Overview composition, browser proof, and documentation

**Files:** Create
`frontend/mission-planner/src/pages/OverviewMetricHistoryPanels.tsx` and
`.test.tsx`; modify `OverviewPage.tsx`, `OverviewPage.css`,
`OverviewPage.contract.test.ts`; create
`frontend/mission-planner/tests/e2e/overview-metric-history.spec.ts`; modify
existing `tests/e2e/overview-globe.spec.ts` snapshot fixture/expectations if
truly required by layout. Create `docs/api/endpoints/overview-history.md`;
modify `docs/features/overview.md` and relevant API index if it has an endpoint
listing.

**Interfaces:** Compose five `OverviewMetricHistoryPanel` instances from **the
single** `useOverviewHistory()` result already in `OverviewPage.tsx`, the
existing `useOverviewHistorySettings()` result, and the existing `currentTime`;
render above `UpcomingPoisPanel`. Leave current-metrics and aircraft-trail
projection on their existing sources. No new fetch from child panels.

- [ ] **Step 1: RED layout/contract/browser tests.** Component test asserts all
      five accessible panel headings, one shared history result, five separate
      graphs and no internal scrollbar/secondary API hook. Update contract test
      to assert graph region and POIs are siblings in reserved left-column flow
      rather than overlapping absolute overlays. In Playwright, mock the
      existing history GET with 5 raw and 15 aggregate traces, plus
      route/status/POI fixtures. A geometric acceptance assertion is:

```typescript
const graphs = page
  .getByLabel("Overview metric history")
  .locator("[data-metric-panel]");
await expect(graphs).toHaveCount(5);
const pois = await page.getByLabel("Upcoming POIs").boundingBox();
for (const panel of await graphs.all()) {
  const box = await panel.boundingBox();
  expect(box && pois && box.y + box.height <= pois.y).toBeTruthy();
}
```

Assert exactly one history GET for a polling tick, five visible panel boxes at
1920×1080, unobscured legend and globe interaction, visible non-color trace
names, monotonic left translation under controlled time, changed window data
replacing old, and a failed fetch that retains last-good but shows unavailable.
Include a 44rem responsive non-overlap case and a screenshot after the
visual-ready guard; adapt the existing Overview snapshot only after confirming
intended product change.

- [ ] **Step 2: Run RED.** `npm run test:unit -- --run`
      `src/pages/OverviewMetricHistoryPanels.test.tsx`
      `src/pages/OverviewPage.contract.test.ts`;
      `npx playwright test tests/e2e/overview-metric-history.spec.ts --project=chromium`;
      expect no panels and layout assertions to fail, not a harness-bootstrap
      failure.
- [ ] **Step 3: GREEN integration and docs.** Compose panels in a left
      structural region above the POI component, preserve existing fullscreen
      and responsive behavior, and avoid pass-through z-index wrappers. The
      wiring must reuse the current query result, e.g.:

```tsx
<div className="overview-left-stack">
  <OverviewMetricHistoryPanels
    history={overviewHistory}
    error={isOverviewHistoryError}
    selectedWindowSeconds={overviewHistorySettings?.window_seconds}
    nowMs={currentTime}
  />
  <UpcomingPoisPanel
    state={upcomingPoiState}
    pois={upcomingPoiView.topFive}
    currentTime={new Date(currentTime)}
  />
</div>
```

Derive a bounded panel height from available desktop space; do not add an
internal scrollbar or shrink labels below legibility. Document
`/api/overview-history` raw `series` and `rolling_5m` shapes, availability and
503 semantics, query window/step bounds, and one five-second client poll;
describe the five graphs, sample gaps, 5m statistics, legend window, and future
configuration-page controls in `docs/features/overview.md`. Grafana remains
fallback.

- [ ] **Step 4: Verify and commit.** Run focused Vitest and Playwright, all
      Overview Playwright cases, frontend lint/format/build, backend history
      unit/integration tests, Markdown lint, and `git diff --check`; inspect
      browser screenshot at 1920×1080 and changed files. Stage only scoped
      files; commit `feat(overview): integrate five metric history graphs`.
