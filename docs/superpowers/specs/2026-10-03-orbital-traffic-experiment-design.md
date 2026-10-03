# Orbital traffic visualization — deferred experiment design

## Status, separation, and authority

Draft for review. This is the second, deferred effort, separate from the
[traffic arc and link controls](2026-10-03-overview-traffic-paths-design.md).
The first effort ships independently. Orbital work must not delay it or other
key features, and must not add dependencies or placeholder controls to it.

When the user later requests experimentation, create a dedicated experimental
branch from the then-current `dev`, incorporating the delivered arc and its
independent link switches. Do not branch the first effort from this experiment
or require this branch to merge before the arc. This document does not authorize
creating that branch, an implementation plan, a prototype, or a build. Merging
this documentation after approval does not authorize experimental code to merge
into `dev`.

This is an experimental design baseline. It preserves the earlier orbital idea
and proposed resource limits for later exploration; successful experimentation
is not a prerequisite or release gate for production arc development.

## Intended display and integration boundary

Add an optional `Orbital traffic view` Configuration toggle, disabled by
default, on the experimental branch only. Small unlabeled constellation sprites
and one inferred route replace the direct arc when usable. The path runs
aircraft → plausible access satellite → plausible inter-satellite hops →
plausible egress satellite → existing GEP/PoP. Reverse particles represent
download; forward particles represent upload. Never duplicate measured traffic
on both the arc and the orbital path or multiply throughput by hop count.

The PoP is the existing estimated public internet egress endpoint, not an RF
gateway. Its final ground leg is a visual abstraction; no gateway location is
asserted. Public Starlink elements provide orbital context for the Starshield
account, not knowledge of its serving spacecraft or internal network route.

No satellite names/IDs, estimate badges, confidence percentages, or routing
annotations appear on the globe. Preserve configured X-band satellite labels.
Dots remain subordinate to aircraft, route, traffic and configured satellites at
1920×1080. Do not seize the camera or fit the entire constellation into view.
The collapsible legend adds `Satellites` only when those sprites are rendered.

Reuse the first effort's measured-flow eligibility and data provenance. Respect
both production switches: when `starshield_link_enabled` is false, remove its
orbital path and background dots and stop all orbital work, even if the orbital
preference remains true. X-band visibility, synthetic activity and warning rules
remain wholly independent. Turning off only orbital mode returns to the arc when
the Starshield view is enabled.

Persist the orbital preference with existing service settings conventions. Never
change either production visibility setting when saving it. Setting load/save
failures preserve the last confirmed state, with orbital mode off until an
initial setting is confirmed. Configuration diagnostics may report loading,
catalog freshness and why the arc is being used; add no globe badges.

## Public orbital catalog

Share a backend-cached catalog across viewers rather than making each browser
fetch the provider. The proposed source is CelesTrak Starlink GP JSON at:

```text
https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=JSON
```

Keep the live feed as an endpoint example, not a documentation hyperlink that
link-check jobs repeatedly download outside the provider-refresh policy.
Use OMM-compatible mean elements and string catalog IDs, avoiding legacy TLE
identifier limitations. These are orbital elements, not serving-satellite or
routing data. Consult the provider's
[format documentation](https://celestrak.org/NORAD/documentation/gp-data-formats.php)
and [usage policy](https://celestrak.org/usage-policy.php) before later work.

Catalog results carry acquisition time, per-object epoch and a stable catalog
generation. Validate required elements, duplicates, finite values, supported
propagation and plausible Earth orbits. Reject invalid objects individually;
never replace a good catalog with an empty or corrupt response. Limit accepted
and propagated objects to 16,384. On overflow select a stable subset by catalog
ID and report truncation in Configuration.

Persist the last good catalog and upstream attempt time across service restarts.
Coalesce concurrent requests, and allow at most one upstream attempt per two
hours, including failures. No visible active orbital viewer means no periodic
upstream work. Honor longer retry delays; 403/404 suspends attempts until
operator intervention. Other failures wait until the next permitted attempt. Do
not immediately retry or multiply downloads by viewer count.

Proposed eligibility: element epochs at most 72 hours old and at most ten
minutes in the future. A new download does not make an old epoch fresh. Reuse
eligible cached objects during outages and expire them individually. If none
remain usable, remove orbital geometry and return to the arc. These thresholds
are experimental display policies, not guaranteed accuracy claims.

## Propagation and route selection

Use an SGP4-capable OMM propagator; the candidate is
[satellite.js](https://github.com/shashwatak/satellite-js). Propagate and select
routes in a browser worker. Transform positions into the existing globe's
Earth-fixed convention at the same UTC instant, with correct distance units and
altitude scaling. Reject failures, nonfinite coordinates and below-surface
results. Decorative starfield points remain independent of the constellation.

Propagate eligible objects once per second, with visual interpolation between
snapshots. Do not propagate every satellite every animation frame. Select one
route at most every five seconds using these proposed bounded heuristics:

1. Choose the aircraft endpoint satellite with greatest elevation above a
   ten-degree minimum, and the PoP endpoint the same way. A shared satellite
   produces a single-satellite route. These are plausible access/egress choices,
   not claimed radio gateways or confirmed serving spacecraft.
2. Use a spatial index with at most eight candidate neighbors per satellite,
   within 5,000 km and with straight-line Earth clearance of at least 80 km.
   Candidate edges represent geometric plausibility, not known optical links.
3. Find the shortest geometric route with no repeated nodes, at most eight
   satellite nodes and at most 2,048 search expansions. Break ties by stable
   catalog ID. If disconnected or over budget, use the direct arc; never invent
   a missing hop or draw a segment through Earth.

Keep a valid endpoint until a challenger improves elevation by five degrees for
two consecutive selections. Keep a valid route unless a replacement is ten
percent shorter for two selections. Invalid endpoints or broken clearance bypass
hysteresis immediately. Validate current-path clearance on each one-second
snapshot; fall back to the arc while selecting a replacement.

Draw space segments between propagated positions, with elevated ground legs to
aircraft and PoP. Use actual propagated altitudes, not a uniform invented shell.
Keep one measured particle budget for the whole route. Ordinary orbital movement
preserves normalized progress; handovers restart particles without bursts,
duplicate paths or interpolation between unrelated spacecraft.

## Fallback and lifecycle

| Condition                           | Starshield view                         |
| ----------------------------------- | --------------------------------------- |
| Starshield view disabled            | No arc, orbital layer or orbital work   |
| Orbital setting off/not confirmed   | Direct arc; no orbital work             |
| Enabled; catalog loading            | Direct arc while loading                |
| Eligible catalog and route          | Orbital path replaces arc               |
| Eligible catalog; disconnected path | Arc plus background satellites          |
| No eligible catalog/worker failure  | Arc; release unusable orbital resources |
| Invalid aircraft or PoP             | No traffic path; eligible dots may stay |

Both path choices obey the same production telemetry eligibility. Fallback does
not fabricate traffic, change metrics or X-band state, reset the camera, or
require a page reload. Configuration reports fallback reasons. Worker failure
uses the arc for that mount; retry through an explicit off/on toggle or a later
Overview mount.

Disabled orbital mode creates no worker, catalog subscription, propagation or
search timer, GPU buffers, or upstream-refresh demand. Disable/unmount aborts
requests, terminates workers, disposes resources and invalidates generations so
late responses cannot restore the layer. Apply the same teardown when the
Starshield visibility control is disabled.

Hidden pages suspend orbital work and release their active-viewer demand. On
return, recheck settings and catalog eligibility and refresh UTC snapshots
before resuming. Do not replay missed frames or requests. Reduced motion keeps
static path/dot geometry while disabling particle motion and interpolation;
periodic snapshots can still update positions.

## Experimental resource limits and promotion criteria

Use batched point sprites, reusable typed buffers and GPU interpolation, not a
React component or mesh for each satellite. Cap constellation rendering at two
draw calls and buffer ownership at two snapshots plus one in-flight update.
Reuse production particle budgets: at most 100 particles per direction across
the entire measured path. Render only the selected traffic path, not the
candidate neighbor graph or a full traffic mesh.

The laptop is unknown. Compare orbital off/on at 1920×1080 with the existing
globe, route/history and both data links. Do not raise renderer pixel ratio or
add full-screen effects. Proposed targets are at least 30 sustained frames per
second, a 95th-percentile frame time at or below 33 ms, worker updates below 250
ms and no main-thread task over 50 ms attributable to this layer. These are
goals to investigate, not measured results or a hardware guarantee.

Before considering experimental code for `dev`, verify measured-data ownership,
independent link switches, unlabeled sprites, fallback, epoch expiry, provider
backoff, bounded routing, handover, hidden-page/reduced-motion behavior,
canceled responses and leak-free repeated toggles. Validate performance on the
deployment laptop and obtain a separate user decision about promoting the
experiment. If it proves too expensive or distracts from key features, keep it
isolated; the production arc and its controls remain complete and usable.

No experiment, implementation plan, performance probe or dependency installation
is authorized by this documentation change.
