# Overview traffic arc and independent link controls — design

## Status and authority

Approved by the user on 2026-10-03, based on `dev` commit
`bcf15704bd71b9abb7857b23ce9dfc2a06e58ad5`. This document specifies proposed
behavior, not a shipped feature or an executable implementation plan.

The user authorized merging the approved specs from the docs branch to `dev`.
That approval permits the documentation merge only; do not move on to
implementation planning or build the feature without a subsequent explicit
request.

This is the first, independently deliverable effort. Its eventual feature branch
starts from the then-current `dev`. The separate
[orbital experiment](2026-10-03-orbital-traffic-experiment-design.md) is
deferred to a later experimental branch. Its design, dependencies, performance
work, and review must not block this effort or other key features.

Preserve the responsive layout, metric provenance, planned route, history,
camera controls, configured GEO satellites, and existing X-band warning rules
from the [Overview design](2026-09-30-responsive-overview-design.md) and its
[metric amendment](2026-09-30-overview-metric-provenance-design.md).

## Intent and scope

The customer should see two distinct communications capabilities: measured
Starshield traffic reaching the public internet PoP, and the separately
configured X-band link. Currently, `OverviewPage.tsx` applies `/api/status`
network metrics to the aircraft–X-band satellite animation. Move those metrics
to a curved aircraft–PoP arc and give X-band independent synthetic activity.

Provide separate Configuration switches for each data-link visualization. This
effort includes the arc, corrected traffic attribution, X-band synthetic
activity, and both visibility controls. It adds no orbital catalog, satellite
propagator, constellation sprites, route search, orbital workers, orbital API,
orbital toggle, or dependency needed only by the later experiment. Do not build
speculative extension infrastructure to accommodate that future work.

The GEP already represents an estimated public internet egress/PoP location, not
an RF gateway. Preserve this endpoint and its resolver. No estimate badges,
confidence indicators, or new provenance caveats are required on the globe.

## Customer presentation

- Starshield view: one elevated curved aircraft–GEP/PoP arc carrying measured
  upload and download activity in opposite directions.
- X-band view: preserve the configured aircraft–satellite line and give it
  synthetic bidirectional activity when the planned link is normal.
- X-band warning while its view is enabled: preserve the red line and remove all
  of its particles immediately. Measured Starshield traffic continues
  independently.
- Disabling a view hides that link's complete line and particles, not merely its
  animation. Disabling X-band also hides its warning line; existing warning
  computation and the planned-link status/card remain active.
- Preserve aircraft, GEP and configured satellite markers, labels, route,
  history, metrics, and camera intent regardless of the two switches.
- Add `Traffic path` to the collapsible legend only when the arc is rendered.
  Keep the existing planned satellite-link legend entry only when that line is
  rendered. Do not show a legend entry for an unavailable or disabled link.

Both views should remain readable at 1920×1080 on a television. Do not change
camera framing, add warning banners, or create additional numerical metric cards
for the synthetic X-band preset.

## Configuration contract

Add two independent, service-persisted boolean settings using existing
persisted-settings conventions. They are shared installation state, not
per-browser local-storage preferences.

| Setting                   | Configuration label    | Default |
| ------------------------- | ---------------------- | ------- |
| `starshield_link_enabled` | `Starshield data link` | `true`  |
| `x_band_link_enabled`     | `X-band data link`     | `true`  |

The Starshield control description is `Show aircraft-to-PoP traffic.` The X-band
description is `Show the configured satellite link and its activity.` Both
controls are accessible toggles with visible save feedback.

Missing persisted fields use their documented defaults, including upgrading an
existing installation. Do not overwrite a saved `false` with a default. While
settings are loading or unavailable, use the last confirmed values. With no
confirmed values, hide both link visualizations until settings are resolved; do
not briefly re-enable a previously disabled link during a reload.

A failed save retains the last confirmed pair and shows an error in
Configuration. Saving one toggle preserves the other. Successful saves update
the active Overview view without a reload. Both-on, Starshield-only,
X-band-only, and both-off are supported. A disabled link stops and clears its
particle pool and releases its link-specific rendering resources. These
presentation switches never disable telemetry collection or link-state rules.

## Data ownership and animation semantics

| Layer                | Geometry authority             | Activity authority                      |
| -------------------- | ------------------------------ | --------------------------------------- |
| Starshield arc       | Aircraft position and GEP/PoP  | Valid, fresh `/api/status` network data |
| X-band planned link  | Configured GEO and active link | Synthetic 4 Mbps up/down, 500 ms RTT    |
| Planned flight route | Existing route projection      | Existing route animation                |

Measured upload travels aircraft → PoP; download travels PoP → aircraft. Reuse
amber upload and cyan download particle conventions and the bounded
throughput-to-emission-rate mapping. Counts represent activity, not individual
packets. Arc length must not change the represented throughput.

Use metric availability and observation age consistently with existing metric
readouts. A failed status request or a sample at least ten seconds old stops
measured emissions and clears particles. Unavailable, nonfinite, negative, or
zero throughput disables that direction independently. Missing latency or loss
omits its corresponding appearance modulation rather than inventing a value;
valid throughput can still animate. Do not derive literal packet travel time
from path length.

The X-band preset is steady illustrative activity at 4 Mbps in each direction
with nominal 500 ms round-trip latency. It is not a utilization measurement. Use
no random bandwidth changes or artificial loss events. Its appearance must
remain visible despite the high-latency preset; the existing latency mapping's
dim upper clamp must not make the link effectively disappear.

Start X-band emissions only when its view is enabled, the active configured link
and aircraft geometry are valid, and current planned-link state is `normal`.
Warning, unknown state, unavailable selection, or stale/invalid aircraft
geometry stops and clears them. Resume with fresh particles when normal
eligibility returns. Missing Starshield network metrics alone must not stop
X-band activity. An X-band warning cannot change the measured arc's color,
visibility setting, or activity.

Keep synthetic values local to X-band rendering. They must never enter
`/api/status`, Prometheus, metric history, graph readouts, alert evaluation,
packet-loss statistics, or operational link-state calculations. Configuration
may describe the preset; no simulated numerical metric cards are added.

## Geometry and unavailable data

Construct the arc above the globe, anchored at the aircraft's valid projected
position and the existing GEP surface marker. Preserve valid aircraft altitude
through the existing projection. The curve must not cross Earth, including long
routes, dateline crossings, near-antipodal endpoints, and coincident positions.
Use stable orientation and bounded height rather than a singular cross-product
or an arbitrarily tall loop.

Valid position and valid network metrics are separate conditions. The baseline
status API exposes a shared acquisition timestamp, not an independent GPS
observation timestamp. Use that original timestamp and request-failure state to
age position separately from network metric-availability flags. Absent, invalid,
or stale position omits the current Starshield arc and its activity; missing
network metrics alone do not invalidate position. This feature does not add GPS
provenance or invent a position. Historical position rendering keeps its
existing contract.

If GEP/PoP is absent or invalid, omit the Starshield arc. Never substitute the
X-band satellite or an arbitrary gateway. A valid cached GEP remains usable
under the existing resolver contract. X-band geometry retains its existing
projection and warning contract; stale position additionally suppresses its
synthetic activity. Each link's missing input is independent of the other view.

## Lifecycle and performance

Reuse the existing reusable particle-pool and buffer-rendering approach. Bound
each link to at most 100 particles per direction; do not render particles as
individual React components. Recompute arc geometry when endpoints change, not
every animation frame. Keep geometry and buffers bounded and dispose them on
disable or unmount. A late settings response cannot restore resources for an
unmounted view.

Pause particle animation while the page is hidden. On return, recheck
visibility, telemetry age and link state before starting fresh particles; do not
replay missed frames. Reduced motion preserves enabled line geometry but stops
particle motion. Both-off leaves no link animation or link-specific rendering
work while existing operational data continues updating.

The deployment laptop is unknown. Verify readability and added rendering cost at
1920×1080 with the existing globe layers, route/history, and both links. Do not
raise the existing renderer pixel-ratio cap or add full-screen effects. Default
arc performance does not depend on satisfying any orbital experiment budget or
acquiring public orbital data.

## Acceptance criteria for a later implementation

- The eventual feature branch starts from `dev` and can ship independently of
  the deferred orbital experiment, with no orbital dependencies or controls.
- Both views default to enabled. All four toggle combinations work, survive
  reload/service restart, update without reload, and preserve each other when
  saved. Loading and save errors respect the last confirmed settings.
- Disabling each view removes its geometry and particles immediately. Markers,
  measured metrics, collection, existing warning rules and status/card remain.
- Measured traffic appears only on the aircraft–PoP arc. X-band uses only the
  4/4 Mbps, 500 ms preset and cannot contaminate observed metrics or history.
- Warning clears X-band particles immediately and retains its red line only when
  enabled; measured traffic follows its own eligibility independently.
- Missing one direction, missing latency/loss, stale status, invalid/stale
  position, missing PoP, unknown link state and invalid configured satellite
  produce the specified behavior without fabricated data or Earth crossings.
- Repeated toggles and mounts leave no particle pools, timers or GPU buffers
  behind. Hidden-page and reduced-motion behavior are preserved. Both links
  remain readable at 1080p without regressing route/history or camera controls.

These are product contracts. This documentation change creates no executable
plan, implementation branch, dependency installation, or product code.
