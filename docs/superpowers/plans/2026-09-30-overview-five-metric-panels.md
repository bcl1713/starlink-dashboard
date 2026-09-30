# Overview Five Truthful Metric Panels Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver #216: five reusable Overview panels with trustworthy observed
readouts, one network-history freshness/window header, a trailing-five-minute
envelope, and continuous plot-only motion.

**Architecture:** Keep the existing `/api/status` subscription for current
network/obstruction values and its telemetry collection timestamp, and the
single `/api/overview-history` query for Prometheus plots and aircraft trail. Do
not use Prometheus range-query evaluation timestamps as observation age. Align
the four existing history series into uPlot's five-column band input; keep the
plot-only CSS rebase and stationary external text/axes. This is a
data/presentation slice, not #217 arrival, #218 legend, #219 desktop
composition, or #220 mobile layout.

**Tech Stack:** React 19, TypeScript 5.9, uPlot **1.6.32** (lockfile), Vitest,
Playwright, existing FastAPI/Prometheus history response.

**Spec:** `docs/superpowers/specs/2026-09-30-responsive-overview-design.md`
(approved by #214); scope boundary
[#216](https://github.com/bcl1713/starlink-dashboard/issues/216). Planning
baseline: `dev` `e8a004db9717d4405e6fab047e9b97932a54872e`. Recheck immutable
`dev` at implementation start; reconcile intervening chart fixes before editing.

**Visual intent:** Refer to the desktop and mobile sample images embedded in
[parent issue #213](https://github.com/bcl1713/starlink-dashboard/issues/213)
for chart-panel hierarchy and shared styling. They are illustrative, not
application captures or pixel-exact acceptance criteria. In particular, their
sixth signal-quality chart is explicitly excluded: this slice delivers five
truthful graphs. Desktop composition belongs to #219 and mobile layout to #220;
this slice verifies its panels in the existing Overview without claiming either
later layout is complete.

## Global Constraints

- Five only: latency, downlink, uplink, packet loss and obstruction. Do not show
  signal quality as a live observation; do not remove its underlying
  metric/export.
- History display duration is persisted and selectable (5/15/30/60 minutes plus
  saved custom); trailing statistics are **five minutes**, not the display
  interval. The aircraft trail shares this query.
- The prominent values and group network freshness come only from the shared
  `/api/status` telemetry sample and its `timestamp`, not from request time or
  Prometheus history evaluation timestamps. Keep the position-state wording
  independent; one source timestamp does not make a stale position fresh.
- The Overview history hook remains on its existing **five-second request
  cadence** for #216. The 1 Hz future request-cadence goal is not the Prometheus
  scrape rate (already 1 Hz) or the range-query step (one second for the default
  30-minute window). One-second requests would increase repeated 16-query
  Prometheus bundles; track the eventual default in #224 and qualify it with
  #211 performance evidence before changing it. Tests must support both 1s and
  5s arriving bundles without assuming one poll interval.
- Preserve existing bounded history query, five-second poll, per-timestamp
  backend rollups, null gaps, range-query time coordinates, plot-only compositor
  translation, same-frame rebase, and native-fullscreen behavior. No fabricated
  points, zero substitution, global bloom, second per-panel query or every-frame
  `setData()`.
- Keep the existing Overview window selector accessible in the legend until #218
  relocates it. Keep Overview globe, route, GEP, POIs, X-band semantics and
  `/api/status` for non-network consumers as well.
- Documentation impact **in scope**: update `docs/features/overview.md` to
  explain `/api/status` latest-value provenance versus Prometheus history, five
  panel meanings, envelope/average, freshness, gaps, separate display/rolling
  windows and current five-second request cadence. No backend/API response
  change is planned; if one is necessary, stop and seek revised scope.
- TDD RED→GREEN per task; independent task review and final whole-branch review;
  exact pushed SHA for headed Chromium 1920×1080 screenshot plus short motion
  recording and CI evidence. Fixture browser proof must not be described as
  live-backend or sealed #207 acceptance. PR targets `dev`, never `main`.

## Review Focus

1. **Clock skew/future samples:** a status timestamp later than the viewer clock
   must not produce a fresh readout; test future/invalid timestamps in Task 1.
2. **Partial metric loss:** one missing metric must not make all five appear
   fresh; test group partial/unavailable and stale per-panel value in Task 1.
3. **Out-of-order refresh:** an older status payload or same-window history
   response must not rewind readouts or chart; test Task 3 and retention.
4. **Band holes:** missing low/high at a timestamp or a long poll gap must not
   paint across the hole; test Task 2 and headed Task 4.
5. **Resize or tab resume at a rebase:** fixed labels and all traces/band edges
   must remain aligned; test Task 3 and headed Task 4.

## File responsibilities

- `src/pages/overview-metric-history.ts`: existing descriptor/projection; keep
  one aligned timestamp vector and explicit nulls.
- `src/pages/overview-metric-readout.ts` (new): pure status sample projection,
  per-metric freshness and conservative group summary. No fetches or React.
- `src/services/status.ts`: type the existing backend `obstruction` response
  explicitly; do not add an endpoint or change its runtime contract.
- `src/pages/overview-metric-scale.ts` (new): pure, labelled y-domain policy by
  metric; no rendering.
- `src/pages/OverviewMetricHistoryPanel.tsx` and `.css`: stationary
  readout/title/axes, uPlot band and plot-only lifecycle. Keep source file
  cohesive: extract an options builder to `overview-metric-plot-options.ts`
  (new) if the rendering file would expand further; do not introduce a
  pass-through component.
- `src/pages/OverviewMetricHistoryPanels.tsx`: single group header, five
  descriptors sharing one history response, and status-derived readouts passed
  to the individual panels. It does not start a new subscription.
- `src/pages/OverviewPage.tsx`: remove only `OverviewMetricsPanel` presentation;
  continue polling status for globe/link and history for aircraft/charts;
  preserve the window selector until #218.
- `docs/features/overview.md`: operator-facing behavior and limitations.
  Existing `docs/api/endpoints/overview-history.md` is unchanged unless the API
  contract changes.

Paths below are relative to `frontend/mission-planner/` unless prefixed `docs/`.

### Task 1: Status-observed values and network freshness

**Files:** Create `src/pages/overview-metric-readout.ts`,
`src/pages/overview-metric-readout.test.ts`; modify `src/services/status.ts` to
type backend `obstruction.obstruction_percent`. Keep the graph descriptor's
existing metric keys for Prometheus; map status fields by its five `id` values.

**Interfaces:** Consume `StatusResponse` and `OverviewMetricGraphDescriptor`;
produce `statusMetricReadout` and `networkStatusState` with signatures:

```ts
statusMetricReadout(status: StatusResponse | undefined,
  descriptor: OverviewMetricGraphDescriptor, nowMs: number,
  requestFailed: boolean): MetricReadout | null;
networkStatusState(readouts: (MetricReadout | null)[]): NetworkState;
```

`MetricReadout` contains finite `value`, `observedAtMs`, `ageMs`, and
`state: 'fresh' | 'stale'`; `NetworkState` is
`'fresh' | 'partial' | 'stale' | 'unavailable'`. Use the existing
status-freshness threshold of **5,000 ms** (`ageMs >= 5000` is stale), reject
future/invalid timestamps and non-finite values, and treat a failed
`/api/status` request as stale even when React Query keeps last-good data. No
history-step value influences network freshness.

- [ ] **Step 1: RED — write parameterized tests** in
      `overview-metric-readout.test.ts`. Use a status fixture with timestamp
      `1970-01-01T00:01:45.000Z`, network values `latency_ms: 7`,
      `throughput_down_mbps: 0`, `throughput_up_mbps: 2`,
      `packet_loss_percent: 0.2`, and obstruction `{obstruction_percent: 3}`.
      Assert each descriptor maps to the correct value; at `nowMs=110_000` every
      readout is stale (5s boundary), while `nowMs=109_000` is fresh. Replace
      one metric with `NaN` → null and group partial; remove all five →
      unavailable; requestFailed true at 109s → all stale, never fresh. Future,
      malformed and absent status timestamps yield null, not a fresh value.
- [ ] **Step 2: Run**
      `npm run test:unit -- src/pages/overview-metric-readout.test.ts` from
      `frontend/mission-planner`; expect failure because the module is absent.
- [ ] **Step 3: GREEN — type the existing response** and project source fields
      without using history evaluation timestamps:

```ts
// Add to StatusResponse in src/services/status.ts:
// obstruction?: { obstruction_percent?: number };
const fields = {
  latency: status?.network?.latency_ms,
  downlink: status?.network?.throughput_down_mbps,
  uplink: status?.network?.throughput_up_mbps,
  "packet-loss": status?.network?.packet_loss_percent,
  obstruction: status?.obstruction?.obstruction_percent,
};
const value = fields[descriptor.id as keyof typeof fields];
const observedAtMs = Date.parse(status?.timestamp ?? "");
const ageMs = nowMs - observedAtMs;
if (
  typeof value !== "number" ||
  !Number.isFinite(value) ||
  !Number.isFinite(observedAtMs) ||
  ageMs < 0
)
  return null;
return {
  value,
  observedAtMs,
  ageMs,
  state: requestFailed || ageMs >= 5_000 ? "stale" : "fresh",
};
```

Implement `networkStatusState` over all five projected readouts: all null →
unavailable; all fresh → fresh; all non-null stale → stale; other mixes →
partial. Keep failure wording truthful when last-good data remains.

- [ ] **Step 4: Run** the focused test and existing
      `src/pages/overview-metric-history.test.ts`; expect both pass. Commit
      `feat(overview): derive current metric freshness from status`.

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
