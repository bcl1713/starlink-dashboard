# Overview Five Truthful Metric Panels — Presentation Tasks

Continuation of
[the #216 implementation plan](2026-09-30-overview-five-metric-panels.md). Its
global constraints, interfaces and review focus apply here.

## Presentation and acceptance

### Task 3: Shared header, stationary latest values and removal of duplicate box

**Files:** Modify `src/pages/OverviewMetricHistoryPanels.tsx`, `.test.tsx`,
`src/pages/OverviewMetricHistoryPanel.tsx`, `.css`, `.test.tsx`,
`src/pages/OverviewPage.tsx`, `src/pages/OverviewPage.css`,
`src/pages/OverviewPage.contract.test.ts`; remove `OverviewMetricsPanel.tsx`
only after confirming no other imports. Add focused docs to
`docs/features/overview.md` in this task.

**Interfaces:** The parent retains the accepted newest same-window bundle (not
an older arriving response) and passes `latestObserved(...)` readout and the
existing `error`, `selectedWindowSeconds`, `nowMs` to panels. Header derives
`networkHistoryState(...)` and prints `Display: <selected minutes or seconds>`
and `Rolling statistics: 5 minutes` distinctly. Do not relocate the selector or
change route/position stale status. Keep `nowMs` from `useCurrentTime(1_000)`
for age text, not as a fabricated data timestamp.

- [ ] **Step 1: RED — component tests:** assert a value `7 ms` and
      `Observed 00:01:45 UTC` for a 105s sample at 110s, then
      `Last observed 7 ms · 25s old` at 130s rather than `7 ms` as a current
      value; absent/malformed series renders `Unavailable`; request error
      renders explicit last-known/refresh-failed wording. Assert five titles,
      one group freshness label, one display duration, one rolling-window label,
      no `History available`, repeated `Graph traces`, or
      `Current network metrics`/signal quality. In page contract assert
      `/api/status` still feeds aircraft/X-band while history still feeds all
      five panels and aircraft trail. Add a same-window older-response test
      asserting readout and plot stay on the accepted newer history.
- [ ] **Step 2: Run** the following; expect new assertions to fail against old
      presentation:

  ```bash
  npm run test:unit -- OverviewMetricHistoryPanels \
    OverviewMetricHistoryPanel OverviewPage.contract
  ```

- [ ] **Step 3: GREEN — render** a single group header with class
      `overview-metric-history-panels__header` and label
      `Network history context`, with explicit group status and separate
      display/rolling labels; within each existing panel keep `<h3>`,
      `<strong className="overview-metric-history__latest">` plus age/provenance
      text _outside_ `.overview-metric-history__surface`. For example:

```tsx
<strong className="overview-metric-history__latest">
  {readout?.state === 'fresh' ? `${readout.value} ${descriptor.unit}` : 'Unavailable'}
</strong>
<span className="overview-metric-history__age">
  {readout ? `${readout.state === 'stale' ? 'Last observed' : 'Observed'} ${new Date(readout.timestampSeconds * 1000).toISOString().slice(11, 19)} UTC` : 'No observed sample'}
</span>
```

If stale, show the last-known numeric value in secondary copy with explicit age,
never a prominent current value. Remove duplicate current-network box from
`OverviewPage` but leave `useStatus()` intact. Preserve fixed axes and chart
size via CSS while adding readouts; desktop redesign is reserved for #219.
Update Overview user guidance with Prometheus observation authority and
failure/missing behavior, five metrics, line/band meaning, persisted display
window versus fixed trailing-five-minute window, and selector location pending
issue #218.

- [ ] **Step 4: Run** focused unit tests, entire `npm run test:unit`,
      `npm run lint`, `npx prettier --check src/pages`, `npm run build` from
      `frontend/mission-planner`; run repository Markdown formatting/lint on
      `docs/features/overview.md` separately. Resolve test snapshots/contract
      selectors to the new truthful copy. Commit
      `feat(overview): unify five readouts and network history context`.

### Task 4: Motion/acceptance gate on the exact candidate head

**Files:** Modify `src/pages/OverviewMetricHistoryPanel.test.tsx`,
`src/pages/overview-metric-motion.test.ts`,
`tests/e2e/overview-metric-history.spec.ts`,
`tests/e2e/overview-metric-history-fullscreen.spec.ts` only where new
bands/readouts require assertions; add docs correction in
`docs/features/overview.md` alongside the changed behavior. Do not alter globe
or desktop composition here.

**Interfaces:** No new API; test the five aligned uPlot columns and unchanged
`motionOffsetPixels`/retention behavior under repaint.

- [ ] **Step 1: RED — motion tests:** with two distinct bundles at 5s intervals
      assert each series' x for an unchanged timestamp stays within one CSS
      pixel before/after the same-frame rebase; test a delayed 8s poll reaches
      overscan cap without extrapolating, a 400→300 CSS-px resize recalculates
      pixels/second from measured plot viewport and sets the new uPlot size,
      selected-window change resets retained history, hidden/resumed tab does
      not replay all missed transitions, and `setData()` count stays tied to
      changed bundles/resize (not frame ticks). A real headed-browser check must
      inspect _painted_ positions, since jsdom cannot test compositor
      interpolation.
- [ ] **Step 2: Run** focused tests to capture failing assertions first. Keep
      any existing established history-continuity fixtures and serial headed
      Playwright conventions; do not loosen an assertion just to make a run
      green.
- [ ] **Step 3: GREEN — repair only demonstrated regressions** in
      `OverviewMetricHistoryPanel.tsx` or `overview-metric-motion.ts`: keep
      high/low/average/observed in the same translated clipped surface, x-scale
      rebase dynamic, axes/readouts outside it, and preserve data nulls. If this
      requires a new architecture or backend data contract, stop for an updated
      design/plan instead of improvising.
- [ ] **Step 4: Verify** full frontend units, lint, formatting, build, relevant
      backend history contract tests and serial headed Chromium Overview specs
      at 1920×1080 against the **exact pushed SHA**. Capture screenshot plus a
      short recording spanning at least two distinct history refreshes, gap,
      resize/duration and resume; inspect trace/average/band continuity and
      label stationarity over bright/dark geography. Report whether runtime uses
      fixtures or live backend; collect CI job URLs and independent review
      findings. Commit test/doc corrections with a Conventional Commit before
      final push and repeat exact-head verification if the SHA changes.

## Self-review and implementation handoff

- Coverage is intentionally limited to #216's shared values/freshness, five
  panels, envelope, gap/scale/motion, tests and documentation. #217–#220 and
  #210/#211/#207 remain separately gated. The existing history endpoint already
  supplies rolling values; this plan does not invent signal-quality or new
  backend telemetry.
- Before implementation, the worker verifies the actual `dev` SHA, installed
  uPlot `1.6.32` band behavior/types, current CSS/Playwright selectors and
  backend sample timestamp semantics. If any contradict the baseline, revise the
  plan for Brian's review before coding.
- Implementation **begins in a new session only after Brian reviews this plan**.
  Use an isolated feature worktree from then-current `dev`, subagent-driven
  TDD/task reviews and whole-branch review; maintain the plan-owned ledger
  alongside work. Do not implement on this docs-planning branch.
