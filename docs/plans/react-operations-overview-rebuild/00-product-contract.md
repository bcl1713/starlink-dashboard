# React Operations Overview Product Contract

This file is binding for every phase of the
[rebuild roadmap](../2026-09-02-react-operations-overview-rebuild.md). It is
self-contained for a session with no chat history.

## Identity and source rules

- Repository: `bcl1713/starlink-dashboard`
- Durable PR: `https://github.com/bcl1713/starlink-dashboard/pull/143`
- Base: `dev`; feature: `feature/react-operations-overview`
- Clean rebuild baseline: `07593c69040ad447000bf526d6453ec5c6faacfa`
- Historical head: `e649ce169cd5adcbdd83d6264290b30d5221599e`
- Expected archive: `archive/pr-143-pre-simplification-e649ce1`
- Oracle owns archive creation and feature-ref publication.

The historical implementation is not an incremental base. Phase 1 begins from
the published Phase 0 docs-only head. Inspect the archive only to deliberately
adopt a reviewed fragment; never merge or cherry-pick it wholesale.

## Operator outcome

Provide a React operations overview that shows current Starlink status, short
local history, operational overlays, controls, and freshness/failure states. The
overview must remain useful when one source is slow or unavailable and must fit
a native fullscreen 1920x1080 display without document scrolling.

Grafana remains running and documented as a fallback. It is not a React data
source, parity oracle, or removal target in these phases. React sends no request
to Grafana, port 3000, datasource-proxy paths, plugins, or dashboard assets.

## Data-lane contract

### Live-stat lane

- Fetch same-origin `GET /api/status` independently.
- Supported cadence choices are exactly `1`, `2`, `5`, `10`, and `30` seconds,
  plus `paused`; default is a product decision resolved in Phase 1 tests.
- Schedule from completion, not dispatch, so a lane never overlaps itself or
  bursts to catch up after delay, tab suspension, resume, or cadence change.
- Manual refresh affects only the requested lane and never starts an overlapping
  request.
- Source observation time, receipt time, loading, stale, and error states remain
  distinguishable. Last valid data stays visible during refresh/failure.

### History lane

- Append accepted live status samples to bounded in-browser ring buffers.
- Bounds apply by sample count and/or explicit time horizon; no unbounded array,
  timer, listener, cache, or retained response body is permitted.
- History rendering is local by default. There is no mandatory exact five-second
  history request. Any server history endpoint requires a separately reviewed,
  allow-listed and bounded need.
- Slow chart rendering or history work cannot block live cards or overlays.

### Overlay lane

- Route, POI, active-link, satellite, mission-event, GEP, and weather data
  refresh independently according to source semantics.
- A slow/failing overlay cannot delay live status, local history, or unrelated
  overlays. Preserve last-good geometry and show source-specific state.
- There is no global `Promise.all` transaction across data sources.

## Display and interaction contract

The page exposes, when data supports them:

- explicit UTC clock plus configured operational clocks;
- current position, heading/speed, latency, throughput, packet loss,
  obstruction, freshness, and connection state;
- bounded latency, throughput, and packet-loss histories;
- position, planned route, recent track, active link, POIs, satellites, mission
  events, GEP label/marker, weather radar, layer controls, fit, zoom, scale,
  attribution, and accessible textual summaries;
- cadence selector with exact values `1/2/5/10/30/paused`, manual refresh, and
  keyboard/touch-operable controls;
- clear loading, empty, stale, partial failure, total failure, recovery, and
  paused states without replacing last-good content with a blank dashboard.

Use IDL-safe route/history geometry and finite-coordinate validation. Density
may adapt outside fullscreen, but data and accessible alternatives do not
silently disappear.

## Fullscreen contract

Phase 2's binding visual target is native browser fullscreen at exactly
`1920x1080`. In that state:

- the entire overview bounding box is within the viewport;
- `scrollWidth <= clientWidth` and `scrollHeight <= clientHeight` for the root
  and document; there is no vertical or horizontal document scroll;
- header, controls, live cards, dominant map, rail, and charts have non-zero,
  non-overlapping bounding boxes inside the viewport;
- content is not merely hidden, clipped, scaled illegibly, or made inaccessible
  to satisfy no-scroll assertions;
- entering/exiting fullscreen preserves state and returns focus sensibly;
- a clear fallback is shown when the fullscreen API rejects.

Other widths receive smoke/accessibility coverage, not the retired six-viewport
release gate.

## Security and privacy boundaries

- Browser requests are origin-relative `/api/...`; no arbitrary PromQL, caller
  upstream URL/host/header, direct Prometheus, RainViewer, Grafana, or internal
  Docker hostname.
- Server-side upstream integrations use exact allow-lists, HTTPS where
  applicable, safe DNS/redirect handling, timeouts, cancellation, bounded
  response bytes/points, finite-value validation, and safe errors.
- History and evidence are bounded and redact payloads. Never expose a Ground
  Entry Point public IP in DTOs, logs, DOM, accessibility text, or artifacts.
- Preserve CSP and security headers. Expand only the minimum exact source needed
  for a reviewed browser resource; retain restrictive `default-src`,
  `connect-src`, `object-src`, `frame-ancestors`, `form-action`, and `base-uri`.
- Render external labels as text, never trusted HTML.

## Acceptance contract

### Deterministic checks

Tests prove independent lane scheduling, all cadence values, no overlap or
burst, slow-lane isolation, bounded ring-buffer eviction, malformed data,
staleness, partial failure, recovery, same-origin URLs, CSP, and no GEP
IP/Grafana request. All code follows RED, GREEN, REFACTOR and passes focused
plus full repository checks declared by its phase.

### Browser/runtime checks

At an immutable clean head, independent Phase 3 acceptance uses real Chromium
through built Nginx against the real simulation stack. It records at least ten
seconds of browser-originated `/api/status` request start/completion evidence.
The selected cadence must be within documented tolerance, with no overlap,
catch-up burst, or coupling to an intentionally slow independent lane.

At native 1920x1080 fullscreen, record bounding boxes, document/root dimensions,
state/focus behavior, request failures, and console/page errors. Prove Grafana
can remain available as fallback while React makes no request to it.

The core gate does **not** require six viewports, a mutation/object-identity
ledger, a generated shadow Compose file, exact five-second history requests, or
Grafana parity/retirement.

## Change and decision policy

A phase may refine implementation detail only if it preserves this contract. Any
product-contract change is written into the plan/handoff, reviewed for spec then
quality, and approved by Brian where it changes user behavior or release scope.
Advisory paths are never authority over inspected code.
