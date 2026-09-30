# Overview Five Truthful Metric Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver #216: five reusable Overview panels with trustworthy observed
readouts, one network-history freshness/window header, a trailing-five-minute
envelope, and continuous plot-only motion.

**Architecture:** Keep the single `/api/overview-history` query and existing
bounded per-metric retention. Derive readouts and group freshness from the
newest valid _observed Prometheus history samples_, never `/api/status`; align
the four existing time series into uPlot's five-column band input; keep the
current plot-only CSS rebase and stationary external text/axes. This is a
data/presentation slice, not #217 arrival, #218 legend, #219 desktop
composition, or #220 mobile layout.

**Tech Stack:** React 19, TypeScript 5.9, uPlot **1.6.32** (lockfile), Vitest,
Playwright, existing FastAPI/Prometheus history response.

**Spec:** `docs/superpowers/specs/2026-09-30-responsive-overview-design.md`
(approved by #214); scope boundary
[#216](https://github.com/bcl1713/starlink-dashboard/issues/216). Planning
baseline: `dev` `e8a004db9717d4405e6fab047e9b97932a54872e`. Recheck immutable
`dev` at implementation start; reconcile intervening chart fixes before editing.

## Global Constraints

- Five only: latency, downlink, uplink, packet loss and obstruction. Do not show
  signal quality as a live observation; do not remove its underlying
  metric/export.
- History display duration is persisted and selectable (5/15/30/60 minutes plus
  saved custom); trailing statistics are **five minutes**, not the display
  interval. The aircraft trail shares this query.
- `/api/status` position freshness is distinct from this slice's Prometheus
  network-history freshness. Never present an old observed sample as current; a
  query's response time is not an observation time.
- Preserve existing bounded history query, five-second poll, per-timestamp
  backend rollups, null gaps, original sample timestamps, plot-only compositor
  translation, same-frame rebase, and native-fullscreen behavior. No fabricated
  points, zero substitution, global bloom, second per-panel query or every-frame
  `setData()`.
- Keep the existing Overview window selector accessible in the legend until #218
  relocates it. Keep Overview globe, route, GEP, POIs, X-band semantics and
  `/api/status` for non-network consumers.
- Documentation impact **in scope**: update `docs/features/overview.md` to
  explain latest-observed provenance, five panel meanings, envelope/average,
  freshness, gaps and separate display/rolling windows. No backend/API change is
  planned; if implementation discovers one is necessary, stop and seek revised
  scope.
- TDD RED→GREEN per task; independent task review and final whole-branch review;
  exact pushed SHA for headed Chromium 1920×1080 screenshot plus short motion
  recording and CI evidence. Fixture browser proof must not be described as
  live-backend or sealed #207 acceptance. PR targets `dev`, never `main`.

## Review Focus

1. **Clock skew/future samples:** a timestamp later than the viewer clock must
   not produce a fresh readout; test future/invalid samples in Task 1.
2. **Partial metric loss:** one missing metric must not make all five appear
   fresh; test group partial/unavailable and stale per-panel value in Task 1.
3. **Out-of-order refresh:** an older same-window response must not rewind a
   value or chart; test Task 3 alongside existing retention tests.
4. **Band holes:** missing low/high at a timestamp or a long poll gap must not
   paint across the hole; test Task 2 and headed Task 4.
5. **Resize or tab resume at a rebase:** fixed labels and all traces/band edges
   must remain aligned; test Task 3 and headed Task 4.

## File responsibilities

- `src/pages/overview-metric-history.ts`: existing descriptor/projection; keep
  one aligned timestamp vector and explicit nulls.
- `src/pages/overview-metric-readout.ts` (new): pure history-observation
  selection, per-metric freshness and conservative group summary. No fetches or
  React.
- `src/pages/overview-metric-scale.ts` (new): pure, labelled y-domain policy by
  metric; no rendering.
- `src/pages/OverviewMetricHistoryPanel.tsx` and `.css`: stationary
  readout/title/axes, uPlot band and plot-only lifecycle. Keep source file
  cohesive: extract an options builder to `overview-metric-plot-options.ts`
  (new) if the rendering file would expand further; do not introduce a
  pass-through component.
- `src/pages/OverviewMetricHistoryPanels.tsx`: single group header and five
  descriptors sharing the parent's response; panel-specific readout is derived
  here and passed down.
- `src/pages/OverviewPage.tsx`: remove only `OverviewMetricsPanel` presentation;
  continue polling status for globe/link and history for aircraft/charts;
  preserve the window selector until #218.
- `docs/features/overview.md`: operator-facing behavior and limitations.
  Existing `docs/api/endpoints/overview-history.md` is unchanged unless the API
  contract changes.

Paths below are relative to `frontend/mission-planner/` unless prefixed `docs/`.

### Task 1: Observed values and network freshness

**Files:** Create `src/pages/overview-metric-readout.ts`,
`src/pages/overview-metric-readout.test.ts`; modify
`src/pages/overview-metric-history.ts` only if descriptor typing needs
tightening.

**Interfaces:** Consume `OverviewHistoryBundle`,
`OverviewMetricGraphDescriptor`, `OVERVIEW_METRIC_GRAPHS`; produce
`latestObserved(bundle, descriptor, nowSeconds): MetricReadout | null` and
`networkHistoryState(bundle, descriptors, nowSeconds, requestFailed): NetworkState`.
Define `MetricReadout` as
`{ value: number; timestampSeconds: number; state: 'fresh' | 'stale' }`;
`NetworkState` is `'loading' | 'fresh' | 'partial' | 'stale' | 'unavailable'`.
Keep display formatting separate. Define freshness as age <=
`max(15, 3 * step_seconds)` seconds (at the existing five-second poll, a missing
poll does not instantly flip to stale); reject invalid/nonpositive step by using
15 seconds. Request failure is always stale/partial, never fresh, even if cached
samples remain. Prefer conservative `partial` if at least one metric lacks a
fresh observed sample while another has one.

- [ ] **Step 1: RED — write parameterized tests** in
      `overview-metric-readout.test.ts` for all five descriptor keys and a table
      of `[samples, now, expected]`:
      `[[[100, 0], [105, 7]], 110, {value:7,timestampSeconds:105,state:'fresh'}]`,
      `[[[100, 7]], 130, {value:7,timestampSeconds:100,state:'stale'}]`,
      `[[[100, NaN], [110, Infinity]], 110, null]`,
      `[[[120, 9], [105, 7]], 110, {value:7,timestampSeconds:105,state:'fresh'}]`,
      `[[[105, 0]], 110, {value:0,timestampSeconds:105,state:'fresh'}]`. Add
      group tests with five populated series → fresh, one absent → partial, all
      absent → unavailable, all old → stale, and requestFailed true → stale or
      partial but never fresh.
- [ ] **Step 2: Run**
      `npm run test:unit -- src/pages/overview-metric-readout.test.ts` from
      `frontend/mission-planner`; expect failure because the module is absent.
- [ ] **Step 3: GREEN — implement** with actual sample timestamps, not bundle
      `end_timestamp_seconds` as a proxy:

```ts
const maxAge = Math.max(
  15,
  3 *
    (Number.isFinite(bundle.step_seconds) && bundle.step_seconds > 0
      ? bundle.step_seconds
      : 5),
);
const candidates = (bundle.series?.[descriptor.metric] ?? []).filter(
  (entry): entry is [number, number] =>
    Array.isArray(entry) &&
    entry.length === 2 &&
    Number.isFinite(entry[0]) &&
    Number.isFinite(entry[1]) &&
    entry[0] <= nowSeconds,
);
const newest = candidates.reduce<[number, number] | null>(
  (best, sample) => (!best || sample[0] > best[0] ? sample : best),
  null,
);
return newest
  ? {
      value: newest[1],
      timestampSeconds: newest[0],
      state: nowSeconds - newest[0] <= maxAge ? "fresh" : "stale",
    }
  : null;
```

Implement the group reducer using `latestObserved` on **every** descriptor,
prioritizing request failure, then all-missing, partial, all-stale, all-fresh.
Keep the failure wording truthful when last-good data remains.

- [ ] **Step 4: Run** the focused test and existing
      `src/pages/overview-metric-history.test.ts`; expect both pass. Commit
      `feat(overview): derive observed metric freshness from history`.

### Task 2: One envelope, truthful scale and gaps

**Files:** Create `src/pages/overview-metric-scale.ts`, `.test.ts`,
`src/pages/overview-metric-plot-options.ts`, `.test.ts`; modify
`src/pages/OverviewMetricHistoryPanel.tsx`,
`src/pages/overview-metric-history.test.ts` and its component test.

**Interfaces:** Produce
`metricScale(descriptor, projected, previous?: YRange): YRange` and
`metricPlotOptions(args: MetricPlotArgs): uPlot.Options`. Define `YRange` as
`{min: number; max: number}` and `MetricPlotArgs` as
`{width: number; height: number; yRange: YRange; descriptor: OverviewMetricGraphDescriptor}`.
The data order is `[times, max, min, avg, observed]` with indices 1/2 for the
uPlot band. Confirm installed `uplot@1.6.32` `dist/uPlot.d.ts`
`Options.bands`/`Band` and tagged high-low demo before implementation; _do not_
use obsolete `series.band` documentation.

- [ ] **Step 1: RED — tests:** in the plot-options test assert exactly five
      series (including x), `bands` equals
      `[{series:[1,2],fill:'rgba(180, 195, 215, 0.14)'}]`, high/low remain
      enabled but have no visible stroke, average is subdued white dashed,
      observed is cyan with 2–2.5px stroke, no point markers/cursor/legend and
      x-range stays dynamic. Reuse the existing
      `overview-metric-history.test.ts` fixture: its aligned arrays must become
      `[[100,105,110,115],[5,null,6,8],[3,null,3,4],[4,null,4,6],[4,5,null,7]]`
      for timestamp/high/low/average/observed respectively. A long gap inserts a
      shared null timestamp and all four arrays have null there. In scale tests
      assert obstruction `[0,100]` for small samples, packet loss with 0.2%
      remains visibly distinguishable yet includes 0 and explicit upper axis
      value, and other scales include min/max with finite nondegenerate bounds;
      a previous domain must resist small oscillations but expand immediately
      for a new peak.
- [ ] **Step 2: Run**
      `npm run test:unit -- overview-metric-scale overview-metric-plot-options OverviewMetricHistoryPanel`.
      Expect missing modules or old ordering to fail.
- [ ] **Step 3: GREEN — extract the options builder** from the existing
      component, retaining the existing dynamic x-range and plot-only host. Use
      this band configuration and source ordering (verify actual package typings
      first):

```ts
const data = [
  projection.times,
  projection.max,
  projection.min,
  projection.avg,
  projection.observed,
] as uPlot.AlignedData;
const bands: uPlot.Band[] = [
  { series: [1, 2], fill: "rgba(180, 195, 215, 0.14)" },
];
// series: [{}, {label:'High',stroke:'transparent',width:0},
// {label:'Low',stroke:'transparent',width:0},
// {label:'Average',stroke:'#e2e8f0',width:1.25,dash:[5,4]},
// {label:'Observed',stroke:'#67e8f9',width:2.25}]
```

Retain `spanGaps: false`; test in actual uPlot browser that a band does not
bridge one-sided null edges, and if it does, make both band edges null where
either is null before constructing the aligned data (without changing raw
observation semantics). Scale policy: obstruction fixed 0–100; packet loss upper
at least 1% and a rounded 10% margin above observed peak, expanding on
exceedance rather than oscillating on every poll; other metrics start at zero
and expand to a rounded 10% headroom over the combined observed and aggregate
high, with existing-domain retention on small changes. Ensure delayed responses
cannot clip real spikes.

- [ ] **Step 4: Run** focused tests plus `npm run build`; expect pass. Commit
      `feat(overview): draw one rolling envelope and readable scales`.

### Tasks 3–4: Presentation and exact-head acceptance

Continue in
[the companion tasks document](2026-09-30-overview-five-metric-panels-presentation.md).
Both documents form one #216 plan and require Brian’s review before
implementation.
