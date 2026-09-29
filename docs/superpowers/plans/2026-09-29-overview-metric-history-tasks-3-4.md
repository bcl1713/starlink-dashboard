# Overview metric-history graphs — Frontend tasks 3–4

> This task file extends
> [the implementation plan](./2026-09-29-overview-metric-history.md). Read its
> spec, global constraints, interfaces, and Review Focus first.

## Task 3: Typed frontend projection and honest history states

**Files:** Modify `frontend/mission-planner/src/services/overview-history.ts`;
create `frontend/mission-planner/src/pages/overview-metric-history.ts` and
`.test.ts`; modify
`frontend/mission-planner/src/hooks/api/useOverviewHistory.test.ts` only if the
existing single-query contract needs an additional assertion. Do not add a
graph-specific API hook.

**Interfaces:** `OverviewHistoryBundle.rolling_5m` maps metric names to
`{state, min, avg, max}`. `state` is `available` or `unavailable`; the other
fields are `OverviewHistorySample[]`. Export `OVERVIEW_METRIC_GRAPHS` ordered
descriptors `{id, metric, label, unit}`.
`projectMetricHistory(bundle, descriptor, nowMs)` returns
`{state, times, observed, min, avg, max, visibleRightSeconds}`. `state` is
`available`, `empty`, or `unavailable`; `times` is `number[]`, each trace is
`(number|null)[]`, and `visibleRightSeconds` is a number. Times are epoch
seconds; null means a gap, not zero.

- [ ] **Step 1: RED for five metric mappings and four-trace alignment.** Use a
      parameterized Vitest table for the five exact metric IDs/units. Supply raw
      timestamps `[100, 105, 115]` and aggregate timestamps `[100, 110, 115]`;
      assert sorted union `[100,105,110,115]` and null where not sampled:

```typescript
const result = projectMetricHistory(bundle, OVERVIEW_METRIC_GRAPHS[0], 117_500);
expect(result.times).toEqual([100, 105, 110, 115]);
expect(result.observed).toEqual([4, 5, null, 7]);
expect(result.min).toEqual([3, null, 3, 4]);
```

A missing metric yields `empty`, a rollup `state:'unavailable'` yields
`unavailable` while retaining raw data, non-finite/malformed samples are
dropped, and stale intervals do not connect across a 10-second hole. For an
empty/old response and `nowMs` later than its right buffer, assert no generated
future timestamps; for a window change the consuming component must not project
old `bundle.window_seconds` as current under the newly selected setting.

- [ ] **Step 2: Run RED.** `npm run test:unit -- --run`
      `src/pages/overview-metric-history.test.ts`
      `src/hooks/api/useOverviewHistory.test.ts`; expect missing module and/or
      assertions.
- [ ] **Step 3: GREEN projection.** Add types to the existing service, keep
      `overviewHistoryApi.get()` at `/api/overview-history`, and build a
      deterministic timestamp union and null-array projection. A minimal
      alignment core is:

```typescript
const times = [
  ...new Set([...raw, ...min, ...avg, ...max].map(([timestamp]) => timestamp)),
]
  .filter(Number.isFinite)
  .sort((left, right) => left - right);
const at = (samples: OverviewHistorySample[]) => {
  const byTime = new Map(
    samples.filter(([t, v]) => Number.isFinite(t) && Number.isFinite(v)),
  );
  return times.map((time) => byTime.get(time) ?? null);
};
return { times, observed: at(raw), min: at(min), avg: at(avg), max: at(max) };
```

Insert null gap markers when adjacent timestamps exceed the expected
`bundle.step_seconds` sufficiently that a continuous line would be false; do not
fill measurements. Use `nowMs/1000 - 7.5` as initial visible right edge, bounded
by the response window, not as a fabricated sample. Handle mismatch of selected
window in the consuming component without changing the request URL. Preserve
current five-second `useOverviewHistory` hook and no extra invocation.

- [ ] **Step 4: Verify and commit.** Run focused Vitest, `npm run lint`,
      `npm run build`, `git diff --check`; inspect stage, commit
      `feat(overview): project shared metric history`.

## Task 4: uPlot panel and continuously translated plot

**Files:** Add `uplot` dependency/lock entry to
`frontend/mission-planner/package.json` and `package-lock.json`; create
`src/pages/OverviewMetricHistoryPanel.tsx`,
`src/pages/OverviewMetricHistoryPanel.test.tsx`, and focused
`src/pages/overview-metric-motion.ts`/`.test.ts`; add plot-specific styles to
`src/pages/OverviewPage.css` or new `OverviewMetricHistoryPanel.css` imported
once. Consume Task 3 projected arrays. Keep component under the repository's
300-line cohesion target by separating motion math and styles.

**Interfaces:** `OverviewMetricHistoryPanel` receives `descriptor`, `history`,
`error`, `selectedWindowSeconds`, and `nowMs` props. `history` is the shared
`OverviewHistoryBundle | undefined`; the panel makes no query.
`motionOffsetPixels({elapsedSeconds, widthPixels, windowSeconds, bufferSeconds})`
returns a nonpositive bounded translation; `bufferSeconds=7.5`. Use a fixed
viewport and outside-the-translation title, four-trace legend, units, status and
accessible text. uPlot axes should not move with the plot canvas: render fixed
axis labels outside the translated surface or isolate a plot-only uPlot surface.
CSS compositor translation, not interpolated measurement values, advances it. On
new data, rebase to a mathematically equivalent screen position without a
backward jump; on missed polls, clip/stop at the valid sample edge and mark
unavailable or last-known as appropriate.

- [ ] **Step 1: RED for motion, lifecycle, and state.** Parameterize motion
      tests including 0s, 2.5s, 5s, >7.5s missed fetch, negative elapsed, zero
      width, clock reversal, and non-finite inputs; verify bounded finite
      transforms and reset continuity:

```typescript
expect(
  motionOffsetPixels({
    elapsedSeconds: 2.5,
    widthPixels: 400,
    windowSeconds: 1800,
    bufferSeconds: 7.5,
  }),
).toBeCloseTo(-(2.5 / 1800) * 400);
expect(
  Number.isFinite(
    motionOffsetPixels({
      elapsedSeconds: Number.NaN,
      widthPixels: 400,
      windowSeconds: 1800,
      bufferSeconds: 7.5,
    }),
  ),
).toBe(true);
```

In React Testing Library mock `uplot` constructor/`setData`/`destroy`,
`ResizeObserver` and timers. Assert panel title, four named traces, units, empty
and partial-rollup-unavailable text, last-known error text, a data point not
extended to `now`, one plot creation per mount, `setData` on fresh bundle,
resize, and destroy on unmount. Assert the translated element does not contain
the title/legend/axis-label elements.

- [ ] **Step 2: Run RED.** `npm run test:unit -- --run`
      `src/pages/overview-metric-motion.test.ts`
      `src/pages/OverviewMetricHistoryPanel.test.tsx`; expect missing
      modules/behavior.
- [ ] **Step 3: GREEN plot.** Install with `npm install uplot --save`; create an
      instance with fixed surrounding UI and disabled moving axes:

```typescript
const plot = new uPlot(
  {
    width,
    height,
    axes: [{ show: false }, { show: false }],
    series: [
      {},
      { label: "Observed" },
      { label: "Low (5m)" },
      { label: "Average (5m)" },
      { label: "High (5m)" },
    ],
  },
  [
    projection.times,
    projection.observed,
    projection.min,
    projection.avg,
    projection.max,
  ],
  plotHost,
);
// On a fresh bundle: plot.setData(nextProjection); on unmount: plot.destroy().
```

Put the uPlot canvas in a clipped overscanned
`.overview-metric-history__viewport`; drive
`transform: translate3d(var(--history-offset),0,0)` on only its inner plot
surface using a CSS transition/animation anchored to the actual bundle timestamp
and bounded by `motionOffsetPixels`. Keep textual/axis UI outside that surface.
Use ResizeObserver to size/recalculate; preserve the previous transform at
rebase before restarting its continuous motion. Favor linear paths, no spline
smoothing or span-gaps; stop motion when hidden or exhausted. Keep graph
error/last-good text legible even when data remains.

- [ ] **Step 4: Verify and commit.** Run focused tests, `npm run lint`,
      `npm run build`,
      `npx prettier --check 'src/pages/OverviewMetricHistoryPanel*'`
      `'src/pages/overview-metric-motion*'`; inspect stage (including lockfile),
      commit `feat(overview): render moving metric history panels`.
