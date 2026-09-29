# Overview metric-history graphs — design

## Intent and scope

Issue [#149](https://github.com/bcl1713/starlink-dashboard/issues/149) calls for
native `/overview` history graphs as the next parity slice. Operators should see
real historical network behavior beside the existing globe, while keeping
Grafana as the supported fallback and comparator. This slice covers five
separate line-graph panels: network latency (ms), downlink throughput (Mbps),
uplink throughput (Mbps), packet loss (%), and dish obstruction (%). Every panel
plots the observed metric and its trailing five-minute low, average, and high as
four distinguishable traces. Obstruction is a line graph, not a gauge. Uplink
and downlink are separate positive-valued graphs, not Grafana's sign-inverted
combined throughput graph.

The existing current-metrics readout, aircraft history trail, route/globe
context, clocks, and Upcoming POIs remain. No Grafana edits or retirement.
Signal quality is not in the selected graph set. The current legend-selected
history timeframe remains the authority for the graphs and aircraft trail.
Moving the timeframe to configuration, making the five-second poll cadence
configurable, and adding per-panel visibility settings are explicitly future
work; do not add provisional configuration controls in this slice.

## Existing contracts at design time

At `dev` commit `405a18c1e8950b104affb76c72c436309df9544f`,
`/api/overview-history` exposes a bounded Prometheus history bundle, used by the
aircraft trail. It reads the persisted `/api/overview-history/settings` window
and polls through the frontend hook every five seconds. The default selected
window is 30 minutes; the visible selector offers 5, 15, 30, and 60 minutes,
plus an existing persisted custom value. The separate `/api/status` drives the
current-metrics panel once per second. The Grafana Fullscreen Overview refreshes
once per second and graphs latency with five-minute `min_over_time`,
`avg_over_time`, and `max_over_time`; its throughput and packet-loss charts do
not yet carry those aggregates and obstruction is a gauge. This design
intentionally extends the four-trace treatment to all five selected native
panels.

Before implementation, recheck these contracts against the then-current
immutable `dev` SHA and reconcile any intervening changes. Do not design from
the divergent primary checkout.

## Presentation and layout

A fixed left-side graph region sits below the existing top overlays and above
Upcoming POIs. It contains five **individual** compact metric panels,
simultaneously visible at 1920×1080, with no internal scrolling. Reserve space
in normal structural layout for the graphs and POIs instead of placing one over
another or obscuring the globe legend and operational map context. Preserve
legible titles, units, status, and the four-trace key; no tiny-chart compromise
merely to claim all five fit. At narrower widths the panels reflow with the
page's responsive content instead of overlapping the globe or POIs. Do not
introduce a new drawer, accordion, or per-panel visibility controls.

Use uPlot as the lightweight multi-series Canvas chart. Plot only actual
Prometheus samples and calculated aggregates; linear segments must break at
missing or stale intervals rather than imply continuous telemetry. A clipped,
overscanned plot surface provides space to the right for data returned by the
latest poll. CSS compositor translation moves the plotted surface continuously
left over time while labels, units, status, and fixed surrounding UI stay put.
Start the visible right edge approximately 1.5 polling periods behind current
time (7.5 seconds with a five-second poll), so newly fetched data enters the
offscreen buffer first. Do not add a special latency badge: this is ordinary
monitoring rather than trading telemetry. Refresh/rebase the surface without a
visible jump; do not scroll sampled values by inventing intermediate data. Time
and value axes must remain readable and aligned with the translated plot; do not
blindly translate uPlot's entire canvas if that shifts fixed labels/axes. Pause
or bound animation when hidden, unmounted, clock assumptions fail, or the data
buffer is exhausted, and show stale/unavailable state without fabricating new
points. If this motion model cannot be implemented legibly with uPlot and CSS in
the available footprint, return for design review rather than silently switching
to a different visualization contract.

## Data flow and API

Prometheus is canonical for historical values and calculations. Extend the
**existing** `/api/overview-history` response and its single frontend
query/poll, rather than adding a second browser endpoint or duplicating observed
metric series. Preserve the current `window_seconds`, start/end timestamps,
step, and raw `series` fields so the aircraft trail continues to consume the
same data. Add a clearly named rolling-five-minute aggregate map keyed by the
five metric identifiers, with timestamped minimum, average, and maximum arrays
and explicit availability when an aggregate cannot be obtained. The charts read
observed values from the existing raw `series` and aggregates from the added
map. All history uses the same persisted selected window, query boundaries,
sample step, and five-second frontend polling cadence; one frontend fetch
provides the trail and all five charts. Backend Prometheus queries may be
separate internally when required for the aggregation, but share one coherent
time/step plan and one API response. Preserve the existing single-flight
behavior for identical windows. Bound both per-series samples and the total
response/query budget appropriate to five four-trace charts, including persisted
custom windows. Do not turn missing, NaN, or malformed values into zero.

Calculate trailing five-minute low/average/high in Prometheus (`min_over_time`,
`avg_over_time`, `max_over_time` over five minutes), not from only the rendered
viewport's downsampled samples. The preceding five-minute input at the left edge
is Prometheus's responsibility; no synthetic pre-window values. Align raw and
aggregate timestamps by their actual sample times; preserve gaps when samples
are absent, and avoid joining distinct timestamps as if they were simultaneous.
An aggregate-query failure must not erase a successfully fetched raw aircraft
trail: return truthful aggregate-unavailable state for the affected charts while
retaining the raw bundle. A failed raw history fetch marks both the trail and
charts unavailable; it does not alter live `/api/status`. A last-good response
may remain on screen after a failed fetch, but must be explicitly marked as
last-known/unavailable and must not be extended to the present. Window changes
must invalidate the old chart range rather than temporarily label it as current.
Keep refresh and window configuration ownership where it already lives; do not
create another persisted setting.

## Tests, acceptance, and documentation

Use TDD for the Prometheus planner/projection and frontend series
alignment/state behavior. Backend tests cover exact rolling PromQL semantics for
all five metrics; existing raw-field compatibility; shared query window/step and
single-flight behavior; total response bounds; malformed/non-finite samples;
absent metric series; partial aggregate failure with usable raw trail; raw fetch
failure; selected/custom windows; and unchanged live `/api/status` behavior.
Frontend tests cover metric/unit mapping, independent four-trace gaps and
values, **one shared five-second history poll**, window changes, last-good/error
states, component cleanup, and no invented interpolation. Prove scrolling and
refresh/rebase behavior with deterministic time and browser evidence, including
a missed poll and recovery. Verify compact five-panel fit and non-overlap at
1920×1080, responsive presentation, globe interaction and retained POIs/legend,
and accessible non-color series labels and state text. Use exact-head rendered
browser acceptance and the project quality gates before claiming delivery.

Documentation impact is in scope: document the **extended
`/api/overview-history` contract** in API documentation and explain the five
graph meanings, trailing-five-minute statistics, gaps, and the existing
timeframe control in the Overview user/architecture documentation. Explicitly
state future configuration-page visibility and cadence/timeframe controls are
deferred; do not promise them in this PR. Grafana remains a supported fallback.

## Alternatives and rationale

- **Selected:** uPlot plus a clipped overscanned plot and CSS translation. It
  best matches the requested continuous movement at a modest chart payload,
  provided axes stay aligned and gaps remain truthful.
- **uPlot with continuously redrawn x-scale:** less plot isolation, but more
  repeated Canvas work across five panels and no CSS-led motion.
- **Custom SVG:** complete motion control, but unnecessary charting, cursor,
  axis, and gap-handling code.

The design's key trade-off is the added plot/axis isolation needed for
compositor motion. Verify that rendering early; do not hide its complexity by
compromising time accuracy or existing Overview context.
