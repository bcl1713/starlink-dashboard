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

Grafana remains running and documented as a fallback. Its supported Fullscreen
Overview Current Position geomap card is the visual/layer parity authority; it
is not a React runtime data source or removal target. React sends no request to
Grafana, port 3000, datasource-proxy paths, plugins, or dashboard assets.

## Data-lane contract

### Live-stat lane

- Fetch same-origin `GET /api/status` independently.
- Supported cadence choices are exactly `1`, `2`, `5`, `10`, and `30` seconds,
  plus `paused`. One second is unconditionally the default and fastest cadence;
  Phase 1 implements and tests that decision and does not reopen it.
- Use one recursive monotonic timer, scheduled only after the prior bounded
  browser request settles. There is no interval timer, overlap, replay, or
  catch-up burst after delay, tab suspension, resume, or cadence change.
- Each browser request has a bounded timeout. A hidden page pauses polling;
  becoming visible triggers exactly one immediate request, then resumes the
  selected completion-anchored cadence without overlap or replay.
- A cadence change made while a request is in flight takes effect promptly after
  that request settles. At `1s`, starts are 0.8–1.3 seconds apart and there are
  at least four successful responses in five seconds. At `5s`, no request starts
  before 4.5 seconds and one starts by 5.5 seconds. Changing `5s` to `1s` starts
  the next request within 1.3 seconds after settlement. While paused, one manual
  refresh produces exactly one request. In a real ten-second `1s` run, require
  at least eight successes and a median start interval of 0.8–1.3 seconds.
- Manual refresh affects only the requested lane and never starts an overlapping
  request.
- Source observation time, receipt time, loading, stale, and error states remain
  distinguishable. Last valid data stays visible during refresh/failure.

### History lane

- Append accepted live status samples to bounded in-browser ring buffers.
- Bounds apply by sample count and/or explicit time horizon; no unbounded array,
  timer, listener, cache, or retained response body is permitted.
- Call same-origin `GET /api/monitoring/history` once at bootstrap; call it
  again on resume/reconnect only when a gap is detected, and expose explicit
  manual reconciliation. An optional 30–60 second reconciliation cadence may be
  added only when runtime evidence justifies it; there is no mandatory periodic
  history request.
- History responses seed or repair only the bounded 30-minute ring buffers and
  never replace current values. Phase 1 deliberately decides and tests whether
  constant identity becomes a deployment-wide backfill guard or is removed.
- Server queries remain fixed and allow-listed, with explicit point-count and
  response-body bounds, bounded timeout/cancellation, finite-value validation,
  and safe errors. Browser input cannot supply PromQL or an upstream target.
- Slow chart rendering or history work cannot block live cards or overlays.

### Overlay lane

- Data needed for the required position map, top-five applicable POIs, and GEP
  refresh independently according to source semantics.
- A slow/failing overlay cannot delay live status, local history, or unrelated
  overlays. Preserve last-good geometry and show source-specific state.
- There is no global `Promise.all` transaction across data sources.
- The Current Position map preserves ArcGIS imagery, IDL-safe
  route/history/active-link layers, markers, layer visibility controls,
  zoom/scale/measurement controls, and attribution. Weather/radar is
  intentionally deferred by Brian to
  [issue #144](https://github.com/bcl1713/starlink-dashboard/issues/144); no
  weather provider, radar request, control, or loading state is part of this
  candidate.

## Display and interaction contract

At exact native 1920x1080 fullscreen, one screen must show all of this
simultaneously, without scrolling or opening a disclosure:

1. Exactly four clocks.
2. A current-position map.
3. The top five applicable POIs.
4. Current latency plus five-minute minimum, average, and maximum.
5. Current download and upload.
6. GEP.
7. Obstruction.
8. Current, average, and maximum packet loss.
9. The selected refresh interval.
10. The last successful update, or a concise failure when no success is
    available.

The cadence control exposes exactly `1/2/5/10/30/paused`, with `1s` selected by
default, plus keyboard/touch-operable manual refresh. Loading, empty, stale,
partial failure, total failure, recovery, and paused states retain last-good
content. Route, track, active-link, satellites, events, radar, and ancillary
controls may be salvaged, but are optional and cannot block Phase 1 or 2.

Use IDL-safe route/history/active-link geometry and finite-coordinate
validation. Density may adapt outside fullscreen, but data and accessible
alternatives do not silently disappear. A GEP marker may show its safe display
label and coordinates but never its public IP. Weather/radar remains deferred
to issue #144 rather than an optional candidate control.

## Fullscreen contract

Phase 2's binding visual target is native browser fullscreen at exactly
`1920x1080`. In that state:

- `document.fullscreenElement` equals the overview root;
- every exact inventory region above has a non-zero bounding box wholly within
  the viewport, and all inventory is simultaneously visible without scroll or
  disclosure;
- the entire overview bounding box is within the viewport;
- `scrollWidth <= clientWidth` and `scrollHeight <= clientHeight` for the root
  and document; there is no vertical or horizontal document scroll;
- content is not merely hidden, clipped, scaled illegibly, or made inaccessible
  to satisfy no-scroll assertions;
- entering/exiting fullscreen preserves state and returns focus sensibly;
- a clear fallback is shown when the fullscreen API rejects; and
- acceptance retains exactly one viewport screenshot, never a full-page
  screenshot, alongside dimensions and bounding boxes.

Other widths receive smoke/accessibility coverage, not the retired six-viewport
release gate.

## Security and privacy boundaries

- Browser requests are origin-relative `/api/...`; no arbitrary PromQL, caller
  upstream URL/host/header, direct Prometheus, Grafana, weather provider, or
  internal Docker hostname.
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
through built Nginx against the real simulation stack. It retains only bounded
raw results: ten seconds of browser `/api/status` request start/completion/
failure timings, console/page/first-party request errors, dimensions and
bounding boxes, exactly one viewport screenshot, and ordinary concise logs when
useful. No task-owned evidence repository, manifest, checksum, or certification
is created.

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
