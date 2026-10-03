# Overview traffic paths and optional constellation — design

## Status and authority

Draft for user review, based on `dev` commit
`bcf15704bd71b9abb7857b23ce9dfc2a06e58ad5`. This document specifies proposed
behavior and design boundaries. It does not describe a shipped feature.

The authorized work is documentation on a docs branch. Merge this document to
`dev` only after the user approves it. Approval permits that documentation merge
only: do not create an implementation plan, install dependencies, build a
prototype, or implement the feature without a subsequent explicit request.

This design changes traffic attribution in the existing Overview globe. It
preserves the responsive layout, measured metric provenance, planned route,
history, camera controls, configured GEO satellites, and X-band warning logic
from the [Overview design](2026-09-30-responsive-overview-design.md) and its
[metric amendment](2026-09-30-overview-metric-provenance-design.md).

## Intent and selected approach

The customer should see two distinct communications capabilities: measured
Starshield traffic reaching the public internet PoP, and the separately
configured X-band link. Currently, `OverviewPage.tsx` applies `/api/status`
network metrics to the aircraft–X-band satellite animation. That attribution
must change.

Use a curved aircraft–PoP traffic arc by default. An optional Configuration
setting replaces that arc with moving, small constellation sprites and one
inferred orbital route. Retain X-band geometry and give it independent synthetic
activity. This combines the inexpensive direct view with the more expressive
orbital view without making orbital calculations mandatory.

A mandatory full constellation would add resource cost to every display. A
direct arc alone would omit the orbital context the user wants. Neither is the
selected approach.

The GEP already represents an estimated public internet egress/PoP location. It
is not an RF gateway. Preserve that existing endpoint and resolver. The orbital
route's final descent to the PoP is a visual abstraction of the ground segment;
it does not introduce a claimed gateway location. Public Starlink orbital
elements provide context for this Starshield account, not evidence of its
serving spacecraft or actual internal route.

## Customer presentation

- Default view: one elevated curved arc between the aircraft and GEP/PoP,
  carrying measured upload and download activity in opposite directions.
- Orbital view: small unlabeled satellite sprites plus one connected path from
  aircraft through selected satellites to the same PoP. Replace the direct arc
  when this path is usable; never duplicate the same traffic on both paths.
- X-band: preserve the configured satellite marker and aircraft–satellite line,
  with synthetic bidirectional activity when the planned link is normal.
- X-band warning: keep its existing red line and remove all of its particles
  immediately. The measured Starshield path continues independently.
- No estimate badges, confidence indicators, per-satellite names/IDs, routing
  annotations, or repeated provenance caveats on the globe. Preserve existing
  labels for configured X-band satellites; the new constellation has no labels.
- Extend the existing collapsible legend only for layers actually rendered:
  `Traffic path` and `Satellites`. Preserve the route, history, aircraft, GEP,
  and planned satellite-link entries and their current warning styling.

The orbital layer must not seize the camera or fit the whole constellation into
view. Preserve current camera intent and framing. Satellite dots remain
subordinate to the aircraft, traffic, route, and configured X-band markers at
1920×1080, including on a television viewed from across a room.

## Configuration contract

Add one service-persisted boolean setting, `orbital_traffic_enabled`, defaulting
to `false`. Place the accessible `Orbital traffic view` toggle in Configuration
with the description `Show satellites and route traffic through orbit.` Use the
existing persisted-settings conventions; this is shared installation state, not
a per-browser local-storage preference.

Loading or unavailable settings use the direct arc. A failed save retains the
last confirmed setting and shows a save error in Configuration. A successful
save updates the active Overview view without a reload. Disabling the setting
removes the orbital layer and releases its worker and rendering resources.

Configuration diagnostics may show catalog freshness, loading/failure state, and
whether the direct arc is being used as a fallback. They do not add globe
badges. Throughput and latency presets are fixed design values, not additional
customer settings in this feature.

## Data ownership and animation semantics

| Layer                | Geometry authority             | Activity authority                      |
| -------------------- | ------------------------------ | --------------------------------------- |
| Direct traffic arc   | Aircraft position and GEP/PoP  | Valid, fresh `/api/status` network data |
| Orbital traffic path | Same endpoints; public orbits  | The same measured network data          |
| X-band planned link  | Configured GEO and active link | Synthetic 4 Mbps up/down, 500 ms RTT    |
| Planned flight route | Existing route projection      | Existing route animation                |

Measured upload travels aircraft → PoP; download travels PoP → aircraft,
including through all segments of an orbital route. Reuse the existing amber
upload and cyan download particle conventions and bounded throughput-to-rate
mapping. Particle counts represent activity, not individual packets. Changing
the path or number of hops must not multiply the displayed throughput.

Use source availability and observation age consistently with the existing
metric readouts. A failed status request or a sample at least ten seconds old
stops measured emissions and clears their particles. Unavailable, nonfinite,
negative, or zero throughput disables that direction independently. If latency
or packet loss is unavailable, omit its respective modulation rather than
inventing a value; valid throughput can still animate. Real latency and loss may
influence particle appearance, but do not assign end-to-end latency to
individual hops or derive literal packet travel time from line length.

The X-band preset is a steady illustrative 4 Mbps in each direction with nominal
500 ms round-trip latency. Treat 4/4 as the represented activity preset, not a
utilization measurement. Use no random bandwidth changes or artificial loss
events. Its appearance must remain visible at 1080p despite the high latency
preset; the existing latency mapping's dim upper clamp must not make this link
effectively disappear.

Start X-band emissions only when the active configured link, aircraft geometry,
and current planned-link state are valid and the state is `normal`. Warning,
unknown state, unavailable selection, or invalid/stale aircraft geometry stops
and clears them. Resume with fresh particles when normal eligibility returns. Do
not gate this preset on measured Starshield throughput or network freshness. An
X-band warning cannot change the measured traffic path's color or activity.

Keep synthetic values local to the X-band visualization. They must never enter
`/api/status`, Prometheus, metric history, graph readouts, alert evaluation,
packet-loss statistics, or operational link-state calculations. Configuration
may describe the preset; do not add simulated numerical metric cards.

## Endpoint geometry and unavailable data

Construct the direct arc above the globe, anchored at the aircraft's actual
projected altitude and the existing GEP surface marker. The curve must not pass
through Earth, including long routes, dateline crossings, near-antipodal
endpoints, or coincident positions. Use a stable orientation and bounded height
instead of a singular cross-product or an arbitrarily tall loop.

Valid position and valid network metrics are separate conditions. The baseline
status API exposes a shared acquisition timestamp, not an independent GPS
observation timestamp. Use that original timestamp and request-failure state to
age position separately from network metric-availability flags. Absent, invalid,
or stale position omits current traffic geometry and activity; missing network
metrics alone do not invalidate position or stop X-band activity. This feature
does not add GPS provenance or invent a position. Historical position rendering
remains governed by its existing contract.

If GEP/PoP is absent or invalid, omit the measured traffic path. Never
substitute the X-band satellite or an arbitrary gateway. A still-valid cached
GEP remains usable under the existing resolver contract. Orbital background
sprites may remain visible without a traffic path. X-band geometry follows its
existing projection and warning contract; stale position additionally suppresses
its synthetic activity.

## Optional orbital catalog

Use a backend-cached public catalog, shared by all viewers, rather than each
browser fetching the provider. The proposed source is
[CelesTrak Starlink GP JSON](https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=JSON).
Use its OMM-compatible mean elements with catalog IDs preserved as strings;
avoid legacy TLE identifier limitations. These are orbital elements, not live
serving-satellite or network-routing data. See the provider's
[format documentation](https://celestrak.org/NORAD/documentation/gp-data-formats.php)
and [usage policy](https://celestrak.org/usage-policy.php).

Catalog responses include acquisition time, per-object epoch, and a stable
catalog generation. Validate required elements, duplicate IDs, finite values,
supported propagation model, and plausible Earth orbit. Reject malformed objects
individually. Never replace a usable catalog with an empty or corrupt download.
Limit accepted and propagated objects to 16,384; on overflow retain a stable
selection by catalog ID and report truncation in Configuration.

Persist the last good catalog and fetch-attempt time across service restarts.
Coalesce concurrent requests and permit at most one upstream attempt per two
hours, including failures. Do not fetch periodically when orbital mode has no
active visible viewer. Honor longer provider retry delays. A 403/404 suspends
upstream attempts until operator intervention; ordinary network failures wait
until the next permitted attempt. Never run an immediate retry loop.

Proposed freshness policy: use elements whose epochs are at most 72 hours old
and no more than ten minutes in the future. A current successful download does
not make old elements fresh. Reuse eligible cached objects during an upstream
outage; expire each object as its epoch crosses the limit. With no eligible
objects, remove orbital geometry and use the direct arc. These are conservative
display policies to approve, not claims of guaranteed orbit accuracy.

## Orbit propagation and route selection

Use an SGP4-capable propagator with OMM support; the candidate is
[satellite.js](https://github.com/shashwatak/satellite-js). Perform propagation
and route selection in a browser worker. Convert propagated coordinates into the
globe's Earth-fixed coordinate convention at the same UTC instant, with correct
distance units and altitude scaling. Reject propagation failures and
nonfinite/below-surface results. Decorative starfield points are independent.

Propagate the eligible catalog once per second. Interpolate between snapshots
for visual movement; do not propagate every satellite on every animation frame.
Select one route at most every five seconds using these proposed presets:

1. Select the aircraft endpoint satellite with the greatest elevation above a
   ten-degree minimum. Select the PoP endpoint satellite the same way. This
   chooses plausible overhead access and egress satellites, not actual gateway
   infrastructure. A shared endpoint satellite yields a single-satellite path.
2. Connect endpoints through a spatially indexed neighbor graph. Each satellite
   has at most eight candidate neighbors within 5,000 km, with unobstructed
   straight-line clearance above Earth's surface of at least 80 km. Candidate
   edges express geometric plausibility, not known optical links.
3. Find the shortest geometric route with no repeated nodes, at most eight
   satellite nodes, and at most 2,048 search expansions. Use stable catalog-ID
   tie-breaking. Exceeding a bound or finding no connected path uses the direct
   arc; do not draw a line through Earth or invent a disconnected hop.

Keep a current valid endpoint until a challenger improves elevation by at least
five degrees for two consecutive selections. Retain a valid route unless the
replacement is at least ten percent shorter for two selections. Invalid
endpoints or broken clearance bypass this hysteresis immediately. Validate
current-path clearance with each one-second snapshot; suppress invalid orbital
paths and fall back to the arc while selecting a replacement.

Draw space segments between current satellite positions and elevated ground legs
from aircraft/PoP. Satellite dots use propagated altitude; do not put all
objects on an invented uniform shell. Maintain one particle budget across the
whole route. Endpoint handovers restart particles without a burst, duplicate
paths, or interpolation across unrelated spacecraft. Ordinary orbital movement
preserves normalized particle progress along the current path.

## Lifecycle, fallback, and resource budget

| Condition                       | Measured traffic view                  |
| ------------------------------- | -------------------------------------- |
| Setting off or not confirmed    | Direct arc; no orbital work            |
| Enabled; catalog loading        | Direct arc while loading               |
| Eligible catalog and route      | Orbital path replaces direct arc       |
| Eligible catalog; no route      | Direct arc plus background satellites  |
| No eligible catalog/worker lost | Direct arc; release unusable resources |
| No valid aircraft or PoP        | No measured path                       |

Both path choices have the same independent measured-telemetry eligibility.
Fallback must not create fake traffic, change measured values, change X-band
state, reset the camera, or require a page reload. Configuration reports why
orbital routing is unavailable. Worker failure stays in direct mode for that
mount; retry on an explicit off/on toggle or subsequent Overview mount.

Use batched point sprites and reusable typed buffers, not one React component or
mesh per satellite. Keep constellation rendering to at most two draw calls and
interpolation in the GPU shader. Allocate at most two propagated snapshots plus
one in-flight update. Keep route geometry bounded and reuse the existing
particle-pool pattern: at most 100 particles per direction for measured traffic
and 100 per direction for X-band. Draw only the selected communications path,
not the constellation's candidate neighbor graph or a mesh of traffic lines.

When off, create no orbital worker, catalog subscription, propagation timer,
route-search timer, GPU buffers, or provider-refresh demand. Turning off or
unmounting aborts requests, terminates workers, disposes GPU resources, clears
timers, and invalidates generations so late responses cannot restore the layer.
When the page is hidden, suspend its orbital work and particle animation and
release its active-viewer demand. On return, refresh eligibility and UTC
snapshots before resuming; do not replay missed frames or requests. Reduced
motion keeps static path/dot geometry while stopping particle motion and smooth
interpolation; periodic position snapshots can still update.

The deployment laptop is unknown; a 1080p TV does not establish available CPU or
GPU performance. These limits support a conservative design, not a hardware
guarantee. Performance acceptance must compare the same scene with this feature
off and on at 1920×1080. The optional layer must not raise the existing render
pixel-ratio cap or add full-screen effects. Target at least 30 sustained frames
per second, a 95th-percentile frame time at or below 33 ms, worker updates below
250 ms, and no main-thread task over 50 ms attributable to this layer. Validate
on the deployment laptop before calling orbital mode suitable for daily use.

## Acceptance criteria for any later implementation

- Default measured traffic uses aircraft–PoP geometry; X-band activity remains
  independent at the fixed preset, with no synthetic metric leakage.
- Orbital mode has no satellite labels or estimate badges, replaces rather than
  duplicates traffic, and falls back through every state above.
- Warning transitions clear X-band particles immediately and preserve the red
  link, while measured traffic follows its own freshness/availability rules.
- Missing one direction, stale status, stale position, invalid PoP, old catalog,
  disconnected graph, handover, worker failure, and late canceled responses all
  produce the specified behavior without fabricated data or Earth crossings.
- Provider requests respect shared caching, restart persistence, and backoff.
  Repeated toggles/mounts leave no workers, timers, buffers, or subscriptions.
- Default mode has no constellation resource cost. Enabled mode meets the stated
  budgets in a representative 1080p scene, including the existing globe layers,
  two traffic directions, route/history, and normal or warning X-band geometry.

These criteria describe the proposed result. No implementation tasks, delivery
sequence, dependency installation, performance experiment, or build is
authorized by this documentation change.
