# Starlink Dashboard - Features Overview

**Related:** [Main README](../../README.md) | [Setup Guide](../setup/README.md)

Shared displays: [controls](system.md#overview-windows-and-display-controls),
[paced replay](../api/endpoints/simulation-run.md),
[weather](overview-weather.md).

## Feature Categories

### 1. [Monitoring & Dashboards](./monitoring.md)

Core real-time position tracking, network performance metrics, historical data
retention, and native Overview details.

### 2. [Navigation & Timing](./navigation.md)

Route management (KML import, visualization), Point of Interest (POI) tracking
with real-time ETA, and flight phase detection.

### 3. [Mission Communication Planning](./mission-planning.md)

Pre-flight predictive planning tools, real-time timeline preview, satellite
geometry analysis, multi-format briefing exports, and mission timeline
visualization.

### 4. Overview Departure and Arrival

The native Overview globe retains generated operational POI markers for the
active mission. The bottom-center panel fits its content, centers each section's
text and separates next POI from landing with a vertical divider. Narrow screens
stack the sections with a horizontal divider. It shows flight timing:

- Before departure: **SCHEDULED DEPARTURE** with the imported departure name,
  effective mission schedule in UTC, and remaining hours/minutes. Configured
  departure adjustments are included. Once late, elapsed time increases in red
  with **AGO**, such as **12 MIN AGO** or **<1 MIN AGO**. This is scheduled
  timing, independent of GPS; anticipated landing is not shown before flight.
- In flight: **NEXT POI** and **LANDING · destination**, each with route-aware
  UTC ETA and a nonnegative countdown. The nearest eligible event ahead on the
  route stays visible even if its estimate is missing. When the destination is
  next, show only the combined landing section. Destination identity comes from
  `kind: arrival` and stable ID, never its display name.
- After arrival: **LANDED · destination**, without an ETA or countdown. The
  backend flight phase establishes landing; an expired ETA does not.

Arrival estimates use the exact position observation's collection timestamp.
Fresh means less than ten seconds old, allowing up to five seconds of future
clock skew. Network collection and request timestamps cannot renew an old GPS
observation. Missing/invalid GPS coordinates have no verified observation;
genuine zero coordinates remain valid. The timestamp describes collection of
returned coordinates, not a receiver-provided GPS fix timestamp.

In-flight estimates also require a fresh speed observation. Live GPS needs at
least two verified position samples covering 0.1 seconds before speed is known;
the initial compatibility zero cannot enable an ETA. A measured stationary zero
is valid. Missing, stale or failed GPS resets tracking. Automatic flight
detection also requires verified position and speed. An interval of ten seconds
or more between verified observations, including a silent collection pause,
restarts arrival dwell and departure persistence without changing the confirmed
phase. Reused collection timestamps do not advance detection; backward
timestamps break continuity.

Automatic arrival requires continuous verified observations within 100 meters of
the active route's final waypoint for 60 seconds while in flight. Distance is
the direct great-circle distance to that waypoint; a position beyond or beside
the route endpoint cannot establish arrival through projected route progress.
Leaving the radius restarts dwell. This is a proximity confirmation, with no
additional altitude or low-speed landing requirement.

Stale/invalid position suppresses ETA and countdown, with an explicit reason.
Known names and map records remain; stale valid coordinates may identify the
last-known next event, while invalid coordinates cannot establish route
progress. Failed or expired arrival refreshes also suppress timing. Missing
mission, route, schedule, destination and estimates remain explicit. Scheduled
landing times never replace missing estimates, and speed is never invented. UTC
times use **HH:MMZ**, including the date when on another UTC day. Full UTC
provenance remains accessible. Longer countdowns use **1 HR 39 MIN**; positive
intervals under one minute use **<1 MIN**. Arrival stops at **0 MIN**; only
scheduled departure counts past its target. In constrained panels, long
countdowns wrap at word boundaries while preserving enlarged text, centered
alignment and the AGO suffix.

The [Upcoming POIs endpoint](../api/endpoints/overview-upcoming-pois.md)
explains timing provenance and map retention. A route-only active route is not
an active Mission V2 leg (`no_active_mission`). See
[map labels](overview-labels.md) for aircraft protection and accessible names.

### 5. Overview Metric History

Five independent graphs form a left-side column on a sufficiently large native
Overview: network latency (ms), downlink throughput (Mbps), uplink throughput
(Mbps), packet loss (%), and dish obstruction (%). The single **Network history
context** header is a slim strip: **NETWORK - UPDATED 1s AGO** on the left and
**LAST 5 MIN** on the right when five minutes is selected. **LAST** always means
the selected display duration; a custom duration not divisible by a minute uses
seconds. Partial, stale, unavailable and refresh-error states remain explicit.
Rolling-window details stay in accessible descriptions and this guidance. The
cyan observed line, subdued dashed five-minute average and translucent
trailing-five-minute low–high envelope share one plot. Their meanings remain in
accessible chart descriptions rather than an always-visible trace legend.
Prometheus calculates these statistics from the underlying source, not from the
downsampled display window. Gaps remain gaps; missing samples are never
interpolated or presented as zero. Missing envelope boundaries break the band
without hiding valid observed samples. A failed history refresh retains the
newest accepted same-window history, reports **History refresh unavailable**
separately, and never extrapolates samples into the present.

The five stationary prominent readouts come from the existing shared
`/api/status` feed, not Prometheus. Only finite values with explicit per-metric
source availability and a valid collection `timestamp` can be current. Up to
five seconds of future clock skew is allowed; displayed age is clamped to zero
within that allowance, while the acquisition timestamp is preserved for ordering
and freshness. Larger future offsets remain unavailable. A verified measured
zero displays as zero; null, false availability, or legacy responses without
availability display **Unavailable**, even if a compatibility fallback is zero.
A sample is fresh for less than ten seconds. Older samples or a failed status
refresh show **Unavailable** prominently and retain verified last-known values
only in secondary **Last observed** copy with an explicit age. **Status refresh
unavailable** is independent of history failure: fresh status readouts remain
current when history alone fails. One network freshness label summarizes fresh,
partial, stale, or unavailable observations; aircraft/position freshness remains
independent. Out-of-order status responses cannot rewind accepted collection
time, and older history responses cannot rewind their accepted same-window
bundle. Signal quality is not included among these five current observations.

History missingness is bounded by Prometheus scraping: unavailable readings
publish `NaN` to only their current gauges and do not add histogram
observations. After a scrape exposes `NaN` or an absent raw evaluation point,
the history adapter omits that point and the matching five-minute
low/average/high points; trailing statistics alone cannot fill the gap. Finite
observations, including measured zero, resume independently when the raw series
recovers. `query_range` timestamps are evaluation times, not acquisition
timestamps. Before a missing reading is scraped, or while a prior sample remains
eligible within Prometheus lookback, a finite point can still represent an older
scrape. The adapter cannot detect that reuse or promise an immediate
collection-time gap. Current collection age must come from `/api/status`, not
graph timestamps. Pre-change historical zeros are not retrospectively verified
observations. No scrape interval, query budget, history window, or request
cadence changes are required for this publication contract.

The aircraft trail and all five graphs share one history response at the
configured polling cadence (one second by default, with five-second rollback)
and the **Overview history window** editor in **Configuration** (5, 15, 30, or
60 minutes, plus a saved custom window). This persisted **LAST** display
duration is separate from **Rolling statistics: 5 minutes**, which always uses
the fixed trailing-five-minute source window. History requests default to one
second after
[qualified acceptance](../reports/2026-10-04-overview-history-efficiency-follow-up.md).
Set `VITE_OVERVIEW_HISTORY_POLL_SECONDS=5` and rebuild to roll back; invalid
build settings also select five seconds. Mounted Overview history keeps polling
in background tabs and refetches on focus; hidden tabs pause chart motion.
Browser scheduling can delay requests; suspended browsers/devices catch up on
resumption without a wall-clock bound. Failures use five-second polling. Cadence
is separate from the one-second Prometheus scrape rate and range-query
resolution (two seconds for a 60-minute window). The backend reuses completed
snapshots and reconciles an overlapping tail, with bounded full loads for
initialization, recovery and historical corrections. Each graph shows the full
selected window, with a small right-edge freshness margin: at the configured
response cadence, real samples and the UTC axis move left at the selected
window's time scale without a visible jump when fresh responses rebase the plot.
New real samples enter from the right, while old ones leave by clipping at the
left. If the tab is hidden, a fetch fails, or history arrives late or
irregularly, motion may pause and a rebase glitch may be visible; recovery from
an arbitrary outage is not guaranteed seamless. Resuming a hidden tab restarts
motion from its frozen edge rather than replaying every missed transition. With
unchanged history, visibility or fetch-error changes rebase the moving surface
without uploading the same uPlot data again. Projection and scale scans run only
when accepted history or its metric/window changes; clock labels and stale
indicators still update. Data uploads follow changed bundles or measured
viewport resizes, not animation frames. The plots retain only real chart samples
from overlapping responses at the left edge until they leave the visible window;
newer responses replace or remove samples in their covered range. The aircraft
trail still uses only the shared selected-window response. An initial load may
have an empty far-left margin until later polls supply those samples. At the
default 30-minute scale, five seconds of motion is deliberately subtle; no
future samples are invented. The UTC tick labels remain on one line.

The current readouts use whole milliseconds for latency, at most one decimal for
Mbps, and at most two decimals for percentages, with trailing zeros removed. A
positive observation below the displayed increment appears as **<1 ms**, **<0.1
Mbps** or **<0.01%**, rather than implying a measured zero. Full-precision
values remain in the source data and accessible provenance. Fresh per-card
observation timestamps and UTC plot bounds are available to assistive
technology; they no longer occupy repeated visual rows. Last-known values and
their age remain visible when stale. Y-axis labels retain meaningful scale
precision. Packet loss and obstruction always use a 0–100% y-domain. Latency and
throughput include observed and aggregate highs with rounded headroom; their
axes expand for new peaks and shrink when the peak drops below half the prior
upper bound, avoiding small oscillations in chart scale.

At 1920×1080, ordinary and native fullscreen views fit without page scrolling.
Four clocks span the top, five metric cards form a 440px left column, planned
satellite information occupies the upper right, and the legend and map status
sit at the lower right. Departure/arrival stays below the central globe area.
The fullscreen entry control sits beneath the planning card. The same mounted
chart and globe trees resize on fullscreen entry/exit; Escape restores the
navigation.

Clocks and other surfaces share 80% navy glass, a fine border, rounded corners
and 10px backdrop blur. The stronger tint protects secondary text over bright
terrain; a 90% navy fallback protects text when blur is unsupported. Blur
applies to the backdrop, leaving text and plots sharp. Shared refresh-error
space and per-card exception space preserve fit when data becomes stale. Long
satellite identifiers wrap in smaller type while retaining their complete
accessible text. Empty POIs do not move the charts. The legend identifies
rendered map layers; detailed map diagnostics remain available in Configuration.

Layout uses actual Overview container size: the desktop composition requires at
least 1500px and 93.75rem width, and 1012px and 63.25rem height. The metric and
right columns start 136px beneath the clocks. At a 1920×1080 ordinary viewport,
the navigation leaves sufficient content height for the same desktop frame.
Portrait uses a bounded globe stage followed by page-flow metric cards, without
a second metrics scroller. At roughly 844×390 CSS px, landscape keeps the globe
visible beside a 210–240px rail containing all five charts. Enlarged text, long
exceptions, an expanded legend or insufficient height fall back to readable
stacked flow. Layout uses the measured shell, root font and overlay sizes; DPR
or a device name does not select it. Font-relative clock/card columns honor text
enlargement. Normal scroll input over panels, gaps and the globe scrolls the
page or landscape rail. Ctrl/Meta wheel retains browser zoom.

**Explore map** enables deliberate orbit/zoom on the globe. **Exit map
exploration** or Escape returns to scrolling and restores focus. Blur and
rotation release an interrupted gesture. The legend expands with its labeled
button and closes with Escape; controls have at least 44px touch targets. Mobile
navigation's **Toggle navigation** opens Configuration, which contains the
persisted **Overview history window** editor. Its duration applies to the shared
aircraft trail and all five plots, independently of five-minute rollups.

On opening, the camera fits the route's projected extents into the clear map
area between panels; without a route it uses a valid aircraft position. The
route can be off-center on the screen because the metric rail occupies the left.
If route data recovers after opening, it gets one eased fit while the camera
remains automatic; manual exploration keeps your chosen view. Desktop provides
Reset and follow status beneath its fullscreen control. Aircraft movement leaves
the default camera still. **Reset map view** performs another fit. In
Configuration, **Follow aircraft on Overview** opts into continuous following
and is saved in this browser; it defaults off. Manual exploration pauses it, and
reset resumes it. Stale, missing or failed map status pauses following with an
explicit reason. This does not renew GPS/arrival timing.

Automatic camera moves ease into their new pose; manual input cancels them.
Manual pose and mounted canvas/plots survive rotation and fullscreen. Reduced
motion removes camera easing, optional star/flow animation and continuous chart
translation while truthful source updates, gaps and time bounds still update.
The globe's geometry and natural lighting are retained; a route spanning its far
side can remain occluded by Earth.

See
[responsive layout architecture](../architecture/overview-responsive-layout.md)
for measured thresholds, scroll ownership and framing limits.

See the [Overview History API](../api/endpoints/overview-history.md) for raw and
rolling response shapes and error behavior. History-window selection and map
diagnostics are available in Configuration. Cadence controls and per-panel
visibility settings remain future work.

### Planned satellite and map layers

The text-only **X-BAND / selected ID / PLANNED SATELLITE** card shows the
selected configuration from the active mission context, not a measured satellite
connection. No selection shows **NO SATELLITE SELECTED**; loading and failed
selection refreshes remain explicit. A selected ID can remain visible while its
configured map geometry is unavailable.

The legend contains only rendered layers: **Aircraft**, **Planned route**,
**Track history**, **Ground entry point**, **Traffic path** and **Planned
satellite link**. The planned-link sample is thicker than the track sample and
retains the supported blue/red normal/warning styling. Short route,
status/history and satellite exceptions appear separately in **Map status**;
warning text names the existing configured azimuth rule without asserting
connectivity. Cached scene geometry can remain visible after a refresh fails;
its layer sample remains present alongside the failure state. Status-feed age is
independent of the position provenance used for arrival estimates.

Aircraft/GEP and satellites remain visible without a route. POIs, GEP,
satellites and included ADS-B identities use connected callout bubbles.
Placement preserves marker order and avoids overlap. Crowded local groups expose
a keyboard-accessible name list; included ADS-B identities stay individually
labelled. POIs and satellites retain accessible name lists. Settings, GEO
look-angle analysis and optional [ADS-B aircraft](overview-adsb.md) controls are
in **Configuration**, with global positions and read-only details.

### Independent data links

Configuration's shared **Starshield data link** and **X-band data link**
switches default on. Violet **Traffic path** uses fresh measured aircraft–PoP
traffic: amber upload, cyan download. X-band's local 4/4 Mbps, 500 ms activity
is illustrative; warning stops particles and retains its enabled red line.
Hiding links preserves collection, metrics, warnings, route/history, markers and
camera. Hidden pages clear/pause particles; reduced motion keeps lines. See
[shared settings](system.md#shared-data-link-visibility) for persistence/errors.
The deployment laptop still requires hardware validation.

## Related Documentation

See [optional boundaries](overview-boundaries.md), [setup](../setup/README.md),
[API reference](../api/README.md),
[troubleshooting](../troubleshooting/README.md) and [README](../../README.md).
