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

### 4. Overview Upcoming POIs

The native Overview globe projects generated operational POIs for the active
mission. Imported departure and arrival waypoint names are used as their labels;
the compact **Upcoming POIs** panel is an unscrollable Top 5 queue, while the
map retains operational context independently. In flight, ETA is a route-aware
estimate from current telemetry position and speed against active-route
geometry, including stored interior projections for generated mission events.
Unsafe or unavailable projection/telemetry leaves ETA unavailable rather than
falling back to direct distance. Ordinary estimates display as UTC; anticipated
times retain an explicit label. Scheduled `expected_arrival_time` is provenance
only; `estimated_arrival_time` drives the live urgency colour and ordering and
is not telemetry. See the
[Upcoming POIs endpoint](../api/endpoints/overview-upcoming-pois.md) for all
final states, timing provenance, and retention details. A route-only active
route is not an active Mission V2 leg: Overview may therefore report
`no_active_mission` while a route remains active.

This feature does not modify, retire, or replace Grafana; Grafana remains the
supported fallback and parity comparator.

### 5. Overview Metric History

Five compact, independent graphs sit above Upcoming POIs on the native Overview:
network latency (ms), downlink throughput (Mbps), uplink throughput (Mbps),
packet loss (%), and dish obstruction (%). The single **Network history
context** header identifies the cyan observed line, subdued dashed five-minute
average, and translucent trailing-five-minute low–high envelope. Prometheus
calculates these statistics from the underlying source, not from the downsampled
display window. Gaps remain gaps; missing samples are never interpolated or
presented as zero. Missing envelope boundaries break the band without hiding
valid observed samples. A failed history refresh retains the newest accepted
same-window history, reports **History refresh unavailable** separately, and
never extrapolates samples into the present.

The five stationary prominent readouts come from the existing shared
`/api/status` feed, not Prometheus. Only finite values with explicit per-metric
source availability and a valid, nonfuture collection `timestamp` can be
current. A verified measured zero displays as zero; null, false availability, or
legacy responses without availability display **Unavailable**, even if a
compatibility fallback is zero. A sample is fresh for less than five seconds.
Older samples or a failed status refresh show **Unavailable** prominently and
retain verified last-known values only in secondary **Last observed** copy with
an explicit age. **Status refresh unavailable** is independent of history
failure: fresh status readouts remain current when history alone fails. One
network freshness label summarizes fresh, partial, stale, or unavailable
observations; aircraft/position freshness remains independent. Out-of-order
status responses cannot rewind accepted collection time, and older history
responses cannot rewind their accepted same-window bundle. Signal quality is not
included among these five current observations.

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

The aircraft trail and all five graphs share one history response every five
seconds and the existing window selector in the globe legend (5, 15, 30, or 60
minutes, plus a saved custom window). This persisted **Display** duration is
separate from **Rolling statistics: 5 minutes**, which always uses the fixed
trailing-five-minute source window. The selector remains in the globe legend
pending [#218](https://github.com/bcl1713/starlink-dashboard/issues/218).
History requests remain every five seconds; a future 1 Hz request default
belongs to [#224](https://github.com/bcl1713/starlink-dashboard/issues/224), not
the existing 1 Hz Prometheus scrape rate or range-query step. Each graph shows
the full selected window, with a small right-edge freshness margin: under the
expected five-second response cadence, real samples and the UTC axis move left
at the selected window's time scale without a visible jump when fresh responses
rebase the plot. New real samples enter from the right, while old ones leave by
clipping at the left. If the tab is hidden, a fetch fails, or history arrives
late or irregularly, motion may pause and a rebase glitch may be visible;
recovery from an arbitrary outage is not guaranteed seamless. The plots retain
only real chart samples from overlapping responses at the left edge until they
leave the visible window; newer responses replace or remove samples in their
covered range. The aircraft trail still uses only the shared selected-window
response. An initial load may have an empty far-left margin until later polls
supply those samples. At the default 30-minute scale, five seconds of motion is
deliberately subtle; no future samples are invented. The UTC tick labels remain
on one line.

At 1920×1080 native fullscreen, the five plots form a single vertical column
directly above the equally narrow five-row POI panel. The combined stack is
bottom-anchored with 1rem of viewport padding, matching the other overlays,
including when fewer POIs leave spare space, without internal scrolling or
clearance for the non-fullscreen button. The clocks, stationary readouts, globe
and legend remain visible. The duplicate current-network box is removed. Use the
Overview Fullscreen button to enter native fullscreen; the app navigation and
Fullscreen button disappear in that state. Exit with the browser's fullscreen
shortcut (usually Escape) to restore the ordinary responsive layout and
controls. Native fullscreen below 1080px high uses a scrollable responsive
arrangement for the populated stack; the existing non-fullscreen breakpoint
remains unchanged. Current telemetry remains on its separate status feed.

See the [Overview History API](../api/endpoints/overview-history.md) for raw and
rolling response shapes and error behavior. Moving window/cadence controls to a
configuration page and per-panel visibility settings are future work, not
current controls. Grafana remains a supported fallback and comparator.

### 6. [System Configuration & Simulation](./system.md)

Environment configuration, REST API documentation, and simulation mode
capabilities (realistic telemetry, route following).

---

## Related Documentation

- [Main README](../../README.md) - Quick start and overview
- [Setup Guide](../setup/README.md) - Installation instructions
- [API Reference](../api/README.md) - Complete API docs
- [Troubleshooting](../troubleshooting/README.md) - Common issues
