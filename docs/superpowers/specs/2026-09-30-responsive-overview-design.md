# Globe-first responsive Overview — design

## Intent, authority and status

The single-user `/overview` is a situational-awareness display answering **where
are we, and where are we going?** On a 1920×1080 display viewed from roughly ten
feet, the globe remains the full-screen visual anchor behind compact, readable
overlays. On phones, it remains the prominent stage while the surrounding
information reflows for portrait and landscape. Use the two images linked in
[epic #213](https://github.com/bcl1713/starlink-dashboard/issues/213) for visual
hierarchy only; their routes, values, positions, and times are not operational
data or application verification. Preserve the renderer's natural time-based
day/night illumination and existing route geometry. Do not add political
boundaries, warning banners, new alarm thresholds, a replacement globe, or a
replacement chart library.

This document specifies product contracts and module boundaries, **not an
executable implementation plan or permission to implement**. It is intended to
live on `dev` while unrelated work continues. Its code observations refer to
immutable `dev` SHA `72ebc23c76b0a1ffccad48f1954e6602c6b8aedd`; before selecting
any implementation slice, re-inspect the new `dev` head, reconcile changes here
and in #213, and obtain approval of that slice's written plan. Issue #210
remains the ten-foot readability review; the partially delivered #149 roadmap
was closed as superseded; #211 is a separate performance investigation. Do not
silently duplicate their distinct work. The approved
[#216 metric-provenance amendment](2026-09-30-overview-metric-provenance-design.md)
adds a source-availability contract to this design; its implementation must
follow the revised #216 plan and independent review.

## Current contracts and the five-metric decision

At the observed SHA, `OverviewPage.tsx` composes the existing Three.js globe,
four configured clocks, current `/api/status` metrics, a diagnostic-heavy
legend, five metric-history panels, and a five-row upcoming-POI table. The
page's narrow layout currently fixes the globe canvas behind scrolling content;
mobile stage/gesture behavior is not thereby proven. `/api/overview-history`
reads a bounded Prometheus bundle and five-minute trailing low/average/high for
the selected persisted history duration; `useOverviewHistory` fetches it every
five seconds. `OverviewMetricHistoryPanel.tsx` already uses uPlot on a clipped
plot-only surface with stationary external labels/axes, roughly 7.5 seconds of
overscan, CSS translation between refreshes, and a rebase on fresh history.
Adapt that mechanism, preserving the shared history query and its settings; do
not create a second subscription per panel.

**Five graphs only:** latency (ms), downlink (Mbps), uplink (Mbps), packet loss
(%), obstruction (%). The requested sixth signal-quality graph is removed from
this design at Brian's direction because there is no trustworthy live
signal-quality observation. Prometheus does expose
`starlink_signal_quality_percent`, but the live-client adapter currently assigns
a constant `100.0` with the note “Not directly available”; simulation derives it
from obstruction. The existence of a gauge or simulation value does **not**
establish measured live signal quality. Do not plot or present it as observed
telemetry, and remove it from the Overview current-metrics presentation when
that box is replaced. Do not change or remove the underlying metric/export in
this visual initiative without a separate source-contract review. Genuine
signal-quality sourcing, if ever desired, is independent future work. This
overrides the six-graph concept image and the earlier six-graph wording of #213.

The latest-value readout for each of the five graphs is the newest valid
**observed** value with its actual timestamp and freshness contract, not an
average, a cursor value, or a value projected into future time. `/api/status`
and Prometheus history have different cadences; choose one explicit authority
for the displayed value at slice design time, test provenance and age, and do
not merge a fresh-looking status with stale history without marking the
distinction. Network freshness and position freshness are separate. If network
samples are missing, show unavailable/last-known with age as appropriate; never
relabel an old point as current.

## Shared presentation and data boundaries

Use existing components and subscriptions as the starting point. A shared
frosted-panel treatment styles clocks, metric panels, satellite planning card,
map legend and arrival panel; it is a style contract, not a mandate to add a
pass-through wrapper component. Telemetry ingestion and trailing statistics stay
outside metric presentation; chart lifecycle, data alignment and motion stay
separate from value formatting; a pure arrival projection consumes the existing
POI/ETA response and a common time basis; satellite planning information never
borrows measured network freshness.

Starting glass values: charcoal/navy at about 80% opacity,
`backdrop-filter: blur(16px)`, light subtle border, soft shadow and 12–16 px
corners. Blur the geography behind panels, not text or traces. Keep high
contrast and transparent chart backgrounds, with sufficiently opaque solid
fallback where backdrop blur is unavailable. Use tabular numerals, visible
keyboard focus, and text in addition to color for operational state. Tune
against bright terrain, dark ocean, real viewport geometry and ten-foot viewing;
these values are starting points rather than pixel-exact acceptance conditions.

The shared header shows `NETWORK - UPDATED 1s AGO` at left and `LAST 5 MIN` at
right for a five-minute selection; `LAST` reflects the actual display duration.
Per Brian's PR #229 follow-up, the **five-minute rolling-statistics window**
stays distinct in accessible descriptions and operator guidance, without a
visible rolling label. Keep partial, stale, unavailable and refresh errors
explicit. Remove “History available,” repeated trace keys and the separate
Current network metrics box. Preserve persisted history selection; moving its
selector requires an accessible replacement control. Keep position-stale and
route-unavailable states truthful outside the network group.

## Chart contract and motion

Reuse uPlot and the current Prometheus/React pipeline for five panels. Each has
a stationary title, prominent observed value/unit, fixed readable scale context
and clipped graph. In each graph: observed cyan ~2–2.5 px, trailing average
dashed subdued white ~1–1.5 px, and one translucent gray min/max envelope around
`rgba(180, 195, 215, 0.14)` without prominent boundary strokes. Sparse subtle
grid, linear paths, no continuous markers and no built-in legend/cursor.
Validate the installed uPlot version's current `bands` API, types and official
examples before coding; a candidate aligned order is
`[timestamps, rollingHigh, rollingLow, rollingAverage, observed]`, with enabled
high/low series whose strokes are visually suppressed and average/observed drawn
above. Do not use obsolete `series.band` examples.

Continue to use the backend's per-timestamp trailing five-minute Prometheus
rollups, not statistics recomputed from only the visible chart or future
samples. Preserve nulls and break markers: an outage is a gap, never zero, a
bridged line or a fabricated extension. Keep stable truthful y ranges: 0–100%
for obstruction and packet loss, per subsequent user steering. Latency and
throughput adapt to observed and aggregate highs, with hysteresis to avoid scale
churn after peaks leave. No continuous future point may be appended to fill
overscan.

Only the plot-data surface moves; title, current value, units, axes, card border
and background remain fixed. Observed, average and both envelope boundaries
share one transform. Derive motion from actual **visible plot width / selected
duration in seconds** and elapsed time rather than card width or assumed sample
interval. Preserve the existing buffer and same-frame rebase so historical
timestamps stay at the same screen coordinates when the rendered origin changes;
do not advance the x domain and apply an uncompensated CSS shift. Ensure
overscan covers the existing redraw cadence, recalculate uPlot dimensions,
overscan and motion together on container resize/history changes, and reconcile
elapsed time after tab resume without replaying queued motion. Do not call
`setData()` on every animation frame solely for animation. When source data runs
out, show a gap/stale state rather than a newly observed flat line. Respect
reduced-motion preference without falsifying time or gaps. Offscreen rendering
suspension is optional only if measured beneficial and it never stops
ingestion/history retention or damages return-to-view continuity.

## Desktop composition and map semantics

At 1920×1080 start with 16–24 px margins, four top clocks, a left column of
**five** ~400–440 px metric panels, a compact upper-right planned-satellite
card, a lower-right legend and a bottom-center arrival panel. Fit without
page/internal scrolling or overlay overlap and leave a broad central globe with
the aircraft, next POI, destination and relevant route within a tested safe
area. No globe-in-a-column desktop fallback. Desktop starting typography:
important labels ~26–30 px, key values ~36–44 px and clocks ~48–56 px, tuned for
ten-foot readability. Layout must reserve real space for controls and panels,
not solve collisions with ever-higher z-index or obscure operational route
features.

The satellite card is configuration/planning data: only `X-BAND`,
selected/planned identifier (for example `X-6`) and `PLANNED SATELLITE`. No
illustration, green connection dot, update age or measured-connection claim.
Retain the existing configured satellite/link geometry and any operational
normal/warning accessibility semantics only where genuinely supported; call the
legend entry `Planned satellite link`, with a line style distinct from the
aircraft track. The map legend is a conditional symbol/line sample and name for
visible relevant layers: Aircraft, Planned route, Track history, Ground entry
point, Planned satellite link. Configuration counts, diagnostic prose and
selectors move to suitable settings/diagnostics rather than disappear if they
remain necessary. Aircraft/GEP context remains visible with no route; explicitly
communicate route-unavailable state outside a fabricated visible-layer entry.
Generated POI markers and configured satellite markers also render on the
current globe. Keep their own visible/accessible labels or an on-demand detail
path, including when mobile collision handling suppresses visual labels; do not
misrepresent them as one of the five line/symbol samples or silently hide them.

The arrival panel shows one next upcoming POI and the destination landing
estimate. With an intermediate event, show `NEXT POI` (name, UTC ETA,
nonnegative countdown) and `LANDING · destination` (UTC ETA, nonnegative
countdown) in two parts of one compact panel. When the next POI is the
destination, combine to one `LANDING · destination — countdown · ETA ...Z`
section. Identify the destination by `kind: arrival` and stable ID, not display
text. Reuse the route-aware ETA endpoint and its `calculated_at`, `upcoming`,
`flight_phase` and availability semantics; a current frontend type may need
alignment with fields already returned by the backend. Derive both countdowns on
one UTC/time basis and do not silently substitute scheduled
`expected_arrival_time` for an unavailable estimate. Handle absent/passed
destination, no remaining POIs, unavailable ETA, stale position, predeparture
anticipated ETA and post-arrival state explicitly; no negative countdown or
invented landing time. A landable destination not returned by the current
endpoint is a contract finding for the relevant slice, not permission to guess
from a marker label. At the observed baseline, `/api/overview/upcoming-pois`
reads cached coordinator position and speed but does **not** validate the
telemetry sample timestamp; `calculated_at` is request time, not evidence that
the position is fresh. The arrival slice must establish age/provenance for the
position used in its ETA, preferably in that endpoint's explicit response
contract. If a reliable same-sample timestamp cannot be obtained, suppress or
label the estimate as unavailable rather than trusting a separate fresh request
or updating a stale countdown. This may require a narrowly scoped backend
contract change.

## Mobile layout, camera and interaction

The mobile concept in #213 is a **1672×941 composite** depicting proposed
390×844 portrait and 844×390 landscape CSS viewports; it is not proof of browser
behavior. Mobile reuses the same data subscriptions, chart instances and globe
renderer, with CSS Grid/Flexbox/media queries based on available width **and
height**, not user-agent or orientation alone. Avoid parallel mobile/desktop
render trees. Preserve selected history duration, the fixed trailing-five-minute
rollup meaning, camera intent and arrival state through rotation. Use actual
container measurements for Three.js and uPlot; do not stretch a chart canvas
with CSS.

Portrait: clocks in a compact 2×2 grid; full-width globe stage around 320–380
CSS px adjusted for available viewport/safe area; one network freshness/history
header; five panels in two columns, falling to one where necessary. **Normal
document scrolling** reaches all panels; no independently scrolling metric
container. Inside the globe stage, place a small text-only
`X-BAND / selected ID / PLANNED` card at an upper corner, the same arrival state
at bottom (long names wrap without pushing countdowns out), and a labelled
expandable legend. Keep relevant route/aircraft/next POI/destination visible in
the available map-safe area where their data exist.

Landscape: one compact clock row; below it, a globe stage roughly 70–75% wide
and a vertically scrollable five-panel metrics rail using the rest, with
practical readable minimum around 210–240 CSS px. The globe stays visible while
the rail scrolls. Put planning card, expandable legend and arrival strip within
the stage. If either region cannot remain readable at the actual width/height,
fall back to the stacked layout; do not crush graphs just to satisfy a
percentage. Use `dvh` where supported with a safe fallback; account for browser
chrome and safe-area insets without horizontal page overflow.

Use normal phone text instead of ten-foot typography: initial secondary labels
~12–14 px, metric titles ~14–16 px, values ~22–28 px, clocks ~20–24 px; at least
44×44 CSS px touch targets, subject to rendered review. Default touches permit
page scrolling without accidentally rotating the globe. If gestures are enabled,
require an explicit Explore map mode with obvious exit/Follow aircraft; scope
gesture handling to the stage and never disable browser scroll/zoom globally.
Legend button exposes expanded state, supports keyboard/focus dismissal, and
does not trap access to map/arrival information. Reframe the globe once for
meaningful stage/overlay-safe-area changes, without altering route geometry or
resetting an operator's manual camera for minor browser-chrome resizing. Respect
reduced motion and accessible state labels.

## Delivery boundaries, tests and documentation

The umbrella design supports independently reviewable **candidate** slices: (1)
five-panel shared values, band, freshness and scrolling; (2) POI/landing
derivation; (3) planning satellite and visible-layer legend; (4) desktop glass
composition; (5) mobile responsive layout, touch and rotation. Split or reorder
only after checking then-current `dev`; avoid a single giant visual PR. Each
slice gets its own approved implementation plan, tests, documentation impact and
exact-head review/acceptance. Keeping `dev` usable after each slice matters more
than adhering to these draft names. The spec can be updated by a separately
reviewed docs change as product assumptions evolve; no stale snapshot is an
implementation directive.

Focused tests should cover source/provenance and freshness of latest values,
trailing-statistics alignment, band gaps, scale choices and elapsed-time/rebase
math; arrival identity and missing/stale/landed states; conditional legend
labels and planning-only card; and mobile layout/legend/touch/resizing state.
Run relevant frontend/backend project checks. At an exact pushed head, capture
actual 1920×1080 screenshots and a short motion recording across bright/dark
geography, five panels, gaps, delayed samples, buffer rebase and resize. Capture
actual 390×844, 844×390 and ~360 px portrait CSS viewports plus a brief
rotation/scroll recording; verify all five panels reachable/readable, no
horizontal overflow, portrait document scroll, landscape rail scroll,
camera/touch behavior, long names, destination-only arrival, blur fallback and
desktop regression. A concept image alone is never acceptance evidence. Record
browser/device limits and performance measurements honestly; #211's longer-run
degradation remains separate unless reproduced in scope.

Documentation impact is **in scope** for each product slice: update Overview
user guidance (five graph meanings, observed versus trailing average/envelope,
freshness, gaps, history/rolling windows, mobile controls), relevant
operator/configuration help (relocated selector, planned satellite semantics),
API documentation only if a response contract changes, and architecture notes if
source/camera/scroll boundaries change. No releases to `main` are authorized by
this design.

## Alternatives and rationale

- **Selected:** adapt the existing Three.js globe, single history query, uPlot
  plot-only CSS motion and POI/ETA endpoint, then compose one responsive view.
  This preserves the already-working contracts and makes the expensive
  chart/touch behavior testable by slice.
- **One all-at-once visual rewrite:** fewer interim layouts but a broad
  regression surface and opaque review of motion, freshness, camera and arrival
  truthfulness; rejected.
- **Separate mobile dashboard or SVG/custom chart replacement:** simpler
  isolated styling at first but duplicates subscriptions/state/rendering and
  risks drift from desktop; rejected.

The main trade-off is retaining an honest five-panel display rather than
mimicking the sixth chart in the image. Real signal quality requires its own
trustworthy acquisition contract before it can appear as observed telemetry.

## #216 presentation cleanup boundary

Brian selected the screenshot-guided #216 cleanup after #228. The
[cleanup plan](../plans/2026-10-01-overview-metric-cleanup.md) brings shared
navy glass tokens and the desktop metric column forward from #219. It also moves
the existing POI table intact to bottom-center to reserve room. The five cards
use stacked uppercase titles and capped current values, one shared
freshness/window context, sparse numeric y labels and accessible rather than
visible per-card UTC bounds. #217 still owns arrival content; #218 owns
satellite/legend semantics; #219 owns final composition/camera/clock tuning;
Issue #220 owns mobile interaction.
