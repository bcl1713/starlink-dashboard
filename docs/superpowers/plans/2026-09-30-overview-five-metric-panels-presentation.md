# Overview Five Truthful Metric Panels — Presentation Tasks

Continuation of
[the #216 implementation plan](2026-09-30-overview-five-metric-panels.md). Its
global constraints, interfaces and review focus apply here.

## Presentation and acceptance

### Task 5: Shared header, stationary latest values and removal of duplicate box

**Files:** Modify `src/pages/OverviewMetricHistoryPanels.tsx`, `.test.tsx`,
`src/pages/OverviewMetricHistoryPanel.tsx`, `.css`, `.test.tsx`,
`src/pages/OverviewPage.tsx`, `src/pages/OverviewPage.css`,
`src/pages/OverviewPage.contract.test.ts`; remove `OverviewMetricsPanel.tsx`
only after confirming no other imports. Add focused docs to
`docs/features/overview.md` in this task.

**Interfaces:** Pass the existing `/api/status` result and
`Boolean(statusError)` from `OverviewPage` into `OverviewMetricHistoryPanels`;
derive `statusMetricReadout(...)` once per descriptor and
`networkStatusState(...)` for one group header. Validate collection timestamps
with `statusObservationAgeMs(status.timestamp, nowMs)` before advancing accepted
status: allow up to 5,000 ms of future skew, clamp displayed negative age to
zero, and reject malformed timestamps or greater skew without changing the last
accepted timestamp. Then accept only a payload not older than the last accepted
status. An invalid response renders unavailable rather than certifying retained
data as current; on a failed refresh, keep last-known readouts but pass
`requestFailed=true` so none looks fresh. Chart history stays the accepted
newest same-window bundle, independent of status; `error` refers only to history
refresh. Print `Display: <selected minutes or seconds>` and
`Rolling statistics: 5 minutes` distinctly; render a separate history-error
message when applicable. Do not relocate the selector or change route/position
stale state. `nowMs` from `useCurrentTime(1_000)` is the viewer clock for
timestamp validation, freshness classification and displayed age.

- [ ] **Step 1: RED — component tests:** with the Task 3 status fixture, assert
      prominent `7 ms` and `Observed 00:01:45 UTC` at 109s; at 130s assert
      prominent `Unavailable` plus `Last observed 7 ms · 25s old` in secondary
      copy. At 109s with a failed status refresh, assert the same last-known
      copy and no prominent `7 ms`; with only a history error, assert a separate
      `History refresh unavailable` message without relabelling a fresh status
      sample as old. An unverified legacy status response, `null` field or false
      availability flag renders `Unavailable`, even if the numeric fallback is
      zero. A verified zero remains a current value. Assert five titles, one
      group freshness label, one display duration, one rolling-window label, no
      `History available`, repeated `Graph traces`, or
      `Current network metrics`/signal quality. In page contract assert
      `/api/status` still feeds aircraft/X-band while history still feeds all
      five panels and aircraft trail. Add independent out-of-order status and
      history response tests: neither rewinds its own accepted data. Cover valid
      → excessively future → valid and valid → malformed → valid sequences;
      rejected timestamps must not prevent recovery or replace the retained
      sample on a failed poll. Allow exactly 5,000 ms of future skew and reject
      5,001 ms. New history must remain accepted during status rejection, while
      older history cannot rewind on valid status recovery. Assert no additional
      status/history subscriptions mount per panel.
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
  {readout?.state === 'stale'
    ? `Last observed ${readout.value} ${descriptor.unit} · ${Math.floor(readout.ageMs / 1000)}s old`
    : readout
      ? `Observed ${new Date(readout.observedAtMs).toISOString().slice(11, 19)} UTC`
      : 'No timestamped observation'}
</span>
```

If stale, show the last-known numeric value in secondary copy with explicit age,
never a prominent current value. Remove duplicate current-network box from
`OverviewPage` but leave `useStatus()` intact. Preserve fixed axes and chart
size via CSS while adding readouts; desktop redesign is reserved for #219.
Update Overview user guidance with `/api/status` availability/current-value
authority versus Prometheus history evaluation timestamps; distinguish status
failure from history failure, measured zero from unavailable, and old history
whose provenance predates this contract. Describe five metrics, line/band
meaning, persisted display window versus fixed trailing-five-minute window, and
selector location pending issue #218. Document that history requests remain
every five seconds; a future 1 Hz request default belongs to #224.

- [ ] **Step 4: Run** focused unit tests, entire `npm run test:unit`,
      `npm run lint`, `npx prettier --check src/pages`, `npm run build` from
      `frontend/mission-planner`; run repository Markdown formatting/lint on
      `docs/features/overview.md` separately. Resolve test snapshots/contract
      selectors to the new truthful copy. Commit
      `feat(overview): unify five readouts and network history context`.

### Task 6: Motion/acceptance gate on the exact candidate head

**Files:** Modify `src/pages/OverviewMetricHistoryPanel.test.tsx`,
`src/pages/overview-metric-motion.test.ts`,
`tests/e2e/overview-metric-history.spec.ts`,
`tests/e2e/overview-metric-history-fullscreen.spec.ts` only where new
bands/readouts require assertions; add docs correction in
`docs/features/overview.md` alongside the changed behavior. Do not alter globe
or desktop composition here.

**Interfaces:** No new API; test the five aligned uPlot columns and unchanged
`motionOffsetPixels`/retention behavior under repaint.

- [ ] **Step 1: RED — motion tests:** with distinct bundles at both 1s and 5s
      intervals (the latter remains the shipped request cadence) assert each
      series' x for an unchanged timestamp stays within one CSS pixel
      before/after the same-frame rebase; test a delayed 8s poll reaches
      overscan cap without extrapolating, a 400→300 CSS-px resize recalculates
      pixels/second from measured plot viewport and sets the new uPlot size,
      selected-window change resets retained history, hidden/resumed tab does
      not replay all missed transitions, and `setData()` count stays tied to
      changed bundles/resize (not frame ticks). A real headed-browser check must
      inspect _painted_ positions, since jsdom cannot test compositor
      interpolation.
- [ ] **Step 2: Run**
      `npm run test:unit -- overview-metric-motion OverviewMetricHistoryPanel`
      from `frontend/mission-planner` to capture failing assertions first. Keep
      any existing established history-continuity fixtures and serial headed
      Playwright conventions; do not loosen an assertion just to make a run
      green.
- [ ] **Step 3: GREEN — repair only demonstrated regressions** in
      `OverviewMetricHistoryPanel.tsx` or `overview-metric-motion.ts`: keep
      high/low/average/observed in the same translated clipped surface, x-scale
      rebase dynamic, axes/readouts outside it, and preserve data nulls. If this
      requires a new architecture or backend data contract, stop for an updated
      design/plan instead of improvising.
- [ ] **Step 4: Verify** on the exact pushed SHA with the commands below. From
      `frontend/mission-planner`: `npm run test:unit`, `npm run lint`,
      `npx prettier --check src/pages src/services/status.ts`, `npm run build`,
      then the following serial headed Chromium suite. From
      `backend/starlink-location`: run the backend contract command. From the
      repository root run `markdownlint-cli2` on `docs/features/overview.md`,
      `docs/api/endpoints/core.md` and
      `docs/api/models/health-status-models.md`.

  ```bash
  npx playwright test --project=chromium --headed --workers=1 \
    tests/e2e/overview-metric-history.spec.ts \
    tests/e2e/overview-metric-history-fullscreen.spec.ts \
    tests/e2e/overview-globe.spec.ts
  python -m pytest tests/integration/test_overview_history_api.py \
    tests/integration/test_status.py \
    tests/unit/test_starlink_client.py \
    tests/unit/test_metrics.py \
    tests/unit/test_overview_history_prometheus.py \
    tests/unit/test_overview_history_rollups.py -q
  ```

  Capture a 1920×1080 screenshot and short recording spanning at least two
  distinct history refreshes, gap, resize/duration and resume; inspect
  trace/average/band continuity and label stationarity over bright/dark
  geography. Report whether runtime uses fixtures or live backend; collect CI
  job URLs and independent review findings. Commit test/doc corrections with a
  Conventional Commit before final push and repeat exact-head verification if
  the SHA changes. These commands do not prove final sealed #207 acceptance.

## Self-review and implementation handoff

- Coverage is intentionally limited to #216's per-metric observation
  availability, status and Prometheus publication, five panels,
  gap/scale/motion, tests and documentation. #217–#220 and #210/#211/#207 remain
  separately gated. The existing history endpoint already supplies rolling
  values; this plan does not invent signal-quality telemetry.
- Before implementation, the worker verifies the actual `dev` SHA, installed
  uPlot `1.6.32` band behavior/types, current CSS/Playwright selectors,
  `/api/status` timestamp provenance and the Prometheus history evaluation-time
  semantics. If any contradict the baseline, revise the plan before coding.
- Implementation **begins in a new session only after Brian reviews this plan**.
  Use an isolated feature worktree from then-current `dev`, subagent-driven
  TDD/task reviews and whole-branch review; maintain the plan-owned ledger
  alongside work. Do not implement on this docs-planning branch.
