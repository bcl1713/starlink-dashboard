# Starlink Dashboard - Features Overview

**Related:** [Main README](../../README.md) | [Setup Guide](../setup/README.md)

This document provides a comprehensive overview of all features available in the
Starlink Dashboard system.

---

## Feature Categories

### 1. [Monitoring & Dashboards](./monitoring.md)

Core real-time position tracking, network performance metrics, historical data
retention, and Grafana dashboard details.

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

See the [Upcoming POIs endpoint](../api/endpoints/overview-upcoming-pois.md) for
timing provenance and independent map retention. A route-only active route is
not an active Mission V2 leg and may report `no_active_mission`. Map POI names
remain accessible even when overlapping globe labels are visually suppressed.
Grafana remains the supported fallback and parity comparator.

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
configured polling cadence (five seconds by default, with one second opt-in) and
the **Overview history window** editor in **Configuration** (5, 15, 30, or 60
minutes, plus a saved custom window). This persisted **LAST** display duration
is separate
from **Rolling statistics: 5 minutes**, which always uses the fixed
trailing-five-minute source window. History requests default to five seconds
while [#224](https://github.com/bcl1713/starlink-dashboard/issues/224)'s
measured performance gate is pending. A reviewed frontend build can select one
second using `VITE_OVERVIEW_HISTORY_POLL_SECONDS=1`; rebuild with `5` to roll
back. Hidden tabs pause interval polling and refetch on focus. Failures use
five-second polling. Cadence is separate from the one-second Prometheus scrape
rate and the selected window's range-query resolution (two seconds for a
60-minute window). The backend reuses completed snapshots and reconciles an
overlapping tail, with bounded full loads for initialization, recovery and
historical corrections. Each graph shows the full selected window, with a small
right-edge freshness margin: under the expected five-second response cadence,
real samples and the UTC axis move left at the selected window's time scale
without a visible jump when fresh responses rebase the plot. New real samples
enter from the right, while old ones leave by clipping at the left. If the tab
is hidden, a fetch fails, or history arrives late or irregularly, motion may
pause and a rebase glitch may be visible; recovery from an arbitrary outage is
not guaranteed seamless. Resuming a hidden tab restarts motion from its frozen
edge rather than replaying every missed transition. With unchanged history,
visibility or fetch-error changes rebase the moving surface without uploading
the same uPlot data again. Projection and scale scans run only when accepted
history or its metric/window changes; clock labels and stale indicators still
update. Data uploads follow changed bundles or measured viewport resizes, not
animation frames. The plots retain only real chart samples from overlapping
responses at the left edge until they leave the visible window; newer responses
replace or remove samples in their covered range. The aircraft trail still uses
only the shared selected-window response. An initial load may have an empty
far-left margin until later polls supply those samples. At the default 30-minute
scale, five seconds of motion is deliberately subtle; no future samples are
invented. The UTC tick labels remain on one line.

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

At 1920×1080 native fullscreen, five navy glass cards form a 440px column with
uppercase titles, large values and stationary sparse scale labels. The compact
departure/arrival panel occupies a separate bottom-center region, while the
existing legend stays at the lower right. Clocks and the other surfaces share
the same glass tint at 50% opacity, fine border, rounded corners and 10px blur.
A 90% navy fallback protects text when backdrop blur is unsupported. Shared
refresh-error space and per-card exception space preserve fit when data becomes
stale. Empty POIs do not move the charts. The compact legend identifies rendered
map layers; detailed map diagnostics remain available in Configuration.

Layout uses actual Overview container size: a desktop column requires at least
93.75rem width and 67.5rem height in fullscreen, or 71.25rem height in ordinary
view where the fullscreen control needs reserved space. Pixel floors also
require 1500px × 1080px in fullscreen and 1500px × 1140px in ordinary view, so
smaller root text cannot activate the rail before the fixed-size cards fit. The
rail starts at 8rem beneath the clocks; larger default text raises the fit
thresholds so it uses readable flow before the clock row can collide with the
metric context. Smaller containers use normal document scrolling so all five
cards and the intact POI queue remain reachable. At an ordinary 1920×1080
browser viewport, navigation reduces the available content height, so this
readable scrolling fallback is intentional. Enter native fullscreen to obtain
the complete ten-foot column without page scrolling; the navigation and
fullscreen button disappear. Exit with the browser's fullscreen shortcut
(usually Escape). Container size changes resize the same chart/globe trees. The
mobile globe-stage and gesture redesign remains separate #220 work.

See the [Overview History API](../api/endpoints/overview-history.md) for raw and
rolling response shapes and error behavior. History-window selection and map
diagnostics are available in Configuration. Cadence controls and per-panel
visibility settings remain future work. Grafana remains a supported fallback and
comparator.

### Planned satellite and map layers

The text-only **X-BAND / selected ID / PLANNED SATELLITE** card shows the
selected configuration from the active mission context, not a measured satellite
connection. No selection shows **NO SATELLITE SELECTED**; loading and failed
selection refreshes remain explicit. A selected ID can remain visible while its
configured map geometry is unavailable.

The legend contains only rendered layers: **Aircraft**, **Planned route**,
**Track history**, **Ground entry point** and **Planned satellite link**. The
planned-link sample is thicker than the track sample and retains the supported
blue/red normal/warning styling. Short route, status/history and satellite
exceptions appear separately in **Map status**; warning text names the existing
configured azimuth rule without asserting connectivity. Cached scene geometry
can remain visible after a refresh fails; its layer sample remains present
alongside the failure state. Status-feed age is independent of the position
provenance used for arrival estimates.

Aircraft/GEP and configured satellites can remain visible without a route.
Generated POIs and satellite markers retain their labels and separate accessible
name lists even when globe occlusion or POI collision handling hides a label.
Settings, counts and GEO look-angle analysis are in **Configuration**, rather
than additional legend rows.

### 6. [System Configuration & Simulation](./system.md)

Environment configuration, REST API documentation, and simulation mode
capabilities (realistic telemetry, route following).

---

## Related Documentation

- [Main README](../../README.md) - Quick start and overview
- [Setup Guide](../setup/README.md) - Installation instructions
- [API Reference](../api/README.md) - Complete API docs
- [Troubleshooting](../troubleshooting/README.md) - Common issues
