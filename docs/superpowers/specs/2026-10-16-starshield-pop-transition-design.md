# Starshield PoP transition advisories

## Purpose and agreed scope

Issue: [#348](https://github.com/bcl1713/starlink-dashboard/issues/348).

Predict potential Starshield point-of-presence (PoP) transitions along mission
routes so operators can anticipate brief interruptions to calls. Integrate the
forecast into mission planning alongside X and Ka, simulated routes, live
flight, and the customer briefing PDF. Enable it automatically whenever
Starshield is enabled, without a separate prediction toggle.

A public egress IP change can interrupt a secure call and require the call to be
reestablished. Show every predicted transition, but classify its full 10-minute
window as a planned communications outage only where Starshield is the sole
usable call transport. This supersedes the initial advisory-only outage rule.
Preserve measured transport telemetry and independent real outages; the planning
outage describes call continuity, not ten minutes of disconnected RF. Keep the
normal Starshield preference without automatically switching services.

Use geography for predictions and existing public-IP geolocation for observed
PoPs. Geography does not prove the active PoP or guarantee an IP change. Each
planning window is fixed at estimated crossing time minus five minutes through
plus five minutes. The ten-minute span is a planning tolerance, not a
statistical confidence interval. Window narrowing and calibration are outside
this work.

This document records the interview-approved design for review. Implementation
requires approval of this written spec and a subsequent implementation plan.

## Architecture and existing integration points

Use one backend geographic forecast shared by planning, live presentation,
simulation, and exports. Keep four responsibilities separate:

1. A configurable, validated PoP catalog supplies stable identities and
   locations.
2. A pure geometry/timing service produces route crossing records.
3. A live observation evaluator reconciles those crossings with the observed
   PoP.
4. A shared call-continuity projection classifies transition impact using other
   usable transports; presentation adapters retain measured service states.

Existing integration points include:

- `app/services/ground_entry_point.py`: public-IP discovery, per-IP geolocation
  cache, and observed GEP/PoP metrics.
- `app/mission/planning/` and `app/mission/timeline_builder/`: effective route,
  existing timing model, and mission timeline generation.
- `app/simulation/coordinator.py`, `run_replay.py`, and related simulation
  services: current simulated aircraft position and replay clock.
- `app/mission/slide_cache/` and `app/mission/exporter/`: captured inputs,
  preparation invalidation, customer projection, and cached PDF production.
- Frontend mission timeline components and Overview projections, plus
  `src/mission-export/briefing/{timeline,document}.mjs`: timeline and PDF
  display.

Keep new geographic logic in focused modules; adapters should consume its
records instead of independently calculating their own crossings. Exact module
and API changes belong in the implementation plan after interface inspection.

## PoP catalog

Seed exactly these six cities: Los Angeles, Ashburn, Dallas, Sydney, Frankfurt,
and Tokyo. The source is the operator's email from Starshield, which supplies
city names and IP ranges. Do not fabricate the actual ranges or require that
email's private contents in the repository. Production IP-range matching is
unnecessary for this MVP because observed identification continues using IP
geolocation.

Each configured entry has a stable ID, display city, country, city-center
latitude/longitude, and source reference. Document the city-center coordinate
source separately from the Starshield email establishing the site's identity.
City-center positions are sufficient; no approximation notice is required in the
UI. Support configuration updates rather than embedding an immutable list in
forecast code. Validate identities, finite coordinates, coordinate bounds, and
duplicates. Invalid configuration must not silently drop sites and produce a
misleading forecast from a partial catalog.

Include a deterministic catalog fingerprint in forecast inputs and cached export
preparation identity. Catalog changes invalidate affected forecasts and briefing
pages through the existing preparation lifecycle. No PoP management UI or
automatic catalog mutation is included.

## Geographic forecast and timing

Consume the effective route used by existing mission planning, including route
edits and supported route modifications. Measure geodesic/great-circle distance
from route positions to each configured city. Determine nearest-PoP regions,
locate changes along each route leg, and refine crossing locations on the route.
Do not interpolate latitude/longitude naively across the anti-meridian.

Sampling must not miss a short intervening nearest-PoP region merely because two
coarse samples have the same winner. Use boundary-aware refinement or an
equivalent algorithm with explicit numerical tolerance; test multiple crossings
within a route leg. A tie at an isolated boundary is expected and resolved by
the adjacent unique assignments. Sustained ambiguity, duplicate locations, or a
tangent that never changes the winning region must not create an arbitrary
transition. Report an indeterminate result where a crossing cannot be resolved.

Map route crossing distance to UTC using the dashboard's existing route timing,
live progress, speed, and ETA model. Do not introduce a second constant-speed
model. Before departure, use planned route timing and assume the nearest PoP at
the route start. Live forecasts cover upcoming route crossings using current
progress and ETA. Recalculate after position/progress, effective route, timing,
or catalog changes; reject results belonging to superseded input revisions.

Each transition record contains a stable route/revision-scoped identity, source
and destination PoP IDs, crossing position and distance, estimated crossing UTC,
and exact UTC window bounds at T−300 seconds and T+300 seconds. Retain the full
bounds in canonical data; clip only the displayed marker to flight/page bounds.
Preserve overlapping transitions as distinct records with their own details.

No route, invalid location, missing catalog, unavailable timing, or stale
aircraft telemetry must not fabricate a current forecast. Reuse existing
telemetry freshness criteria rather than inventing a PoP-specific timeout.
Distinguish unavailable prediction inputs from a valid route with no upcoming
crossing. An aircraft can still have an observed PoP without a route forecast.

## Conditional planned outage and X-band fallback

Evaluate the entire T−5 to T+5 interval against transport capability, splitting
at independent service/constraint changes. Keep all transition markers visible.

| Other usable call transport              | Transition classification                                          |
| ---------------------------------------- | ------------------------------------------------------------------ |
| Ka available                             | Advisory; no transition-related outage.                            |
| X available independently                | Advisory; no transition-related outage.                            |
| X blocked only by Starshield concurrency | Planned X fallback; no transition-related outage.                  |
| Neither Ka nor X usable                  | Full overlapping window counts as a planned communications outage. |

X is a fallback only if removing the Starshield concurrency restriction would
make it usable. Independent aerial-refueling, geometry/elevation, swap, manual,
or other hard constraints still disqualify X. Do not remove those restrictions
or automatically bring X up. The operator would coordinate a fallback only for a
scheduled call; the planning calculation does not require a call schedule or
infer that a switch occurred. Unknown capability remains unresolved rather than
fabricating confirmed availability or a confirmed all-service outage.

Intersect windows with flight and capability bounds and union overlapping
outages; do not double-count simultaneous windows or existing outages. Keep
X-specific optimizer costs distinct from overall planned communications outage
metrics. Use one projection for planning, simulation, dashboard, and export.
Live completion clears active vulnerability as already specified; persistent
mismatch/overdue advice must not invent an unbounded saved planning outage.

## Live observations and advisory lifecycle

Continue using public-IP geolocation for the observed PoP; do not substitute the
nearest configured city as if it were measured. Associate a geolocated city with
a configured ID using normalized city/country identities and explicit aliases
where needed. An unrecognized observed city remains visible as observed and
outside the catalog; it is not silently assigned to the nearest known city.

An unchanged public IP retains its geolocation without an age-based expiry.
After an IP change, resolve the new location using existing caching/retry
mechanisms. If that lookup fails, the current PoP is unknown until it succeeds.
The previous location may remain explicitly last-known but cannot complete a
transition or establish current stability. Discovery failures alone do not
establish a service outage; retain existing service-health determination.

For each route transition A → B, use the observed PoP and route progress:

| Situation                                                        | Live behavior                                                                             |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| On expected A before the window                                  | No active transition advisory yet; show the upcoming window.                              |
| Window begins without observed completion                        | Activate the possible-transition advisory.                                                |
| Observed switch to anticipated B early                           | Mark that transition complete and clear its active advisory.                              |
| Still on A after crossing/window end                             | Keep the advisory active until observation catches up.                                    |
| Observed PoP is neither the nearest nor anticipated next PoP     | Persist an advisory that transition is possible at any time and calls may be interrupted. |
| Unexpected observation later matches nearest or anticipated next | Clear the mismatch advisory; evaluate remaining route transitions normally.               |
| Current PoP unknown                                              | Keep valid geographic predictions; do not assert observed completion or stability.        |

“Anticipated next” means the destination of the first upcoming geographic
boundary along the remaining route. An overdue transition retains its own A/B
identity so it is not lost when the nearest-region assignment advances. When
there is no next crossing, only the nearest PoP is a normal match. Unknown
observation is distinct from a known unexpected PoP.

Associate completion with a specific crossing occurrence, not a permanently
completed city pair: a route can re-enter a previous region. Rebase lifecycle
state when the effective route changes or simulation resets/seeks; do not carry
an obsolete completion into a new route revision. Persistent live advisories may
outlast the fixed planning band; never silently widen saved planning windows.

## Simulation

Simulation must model a connection, not merely draw predicted windows. At each
current simulated aircraft position, select the geographically nearest
configured PoP independently of planned transition timestamps. This applies to
ordinary simulation without an activated/planned route and to mission route
replay.

Assign a deterministic synthetic IPv4 address to each of the six catalog IDs,
using documentation-only address space. Pair it with a simulation-only
geolocation mapping to the city's coordinates and display identity. A simulated
PoP change changes the simulated public IP; unchanged PoPs retain their IPs.
These addresses are never sent to an external geolocation service.

Feed simulated IP changes and matching geolocation through the normal observed
PoP/advisory consumer contract. Keep simulated and production resolver/cache
state isolated, including reset and mode switching; do not replace real egress
discovery with the host machine's location during simulation.

At a numerical tie retain the previous tied PoP; when initializing directly on a
tie, use a deterministic catalog-ID order. Switch once a unique next region is
entered. No hysteresis should shift the modeled geographic boundary. Route
replay uses the same geometry and mission clock as the forecast: its transition
occurs at the predicted center, within geometry tolerance and simulation update
resolution. Speed changes and seek/reset recompute from position and clock.

Without a route, simulated current PoP still follows aircraft position, but no
route-based crossing windows are invented. A simulated transition does not
inject measured packet loss or RF downtime. Its planned call-outage projection
uses the same conditional window rule as planning.

## Planning, Overview, and PDF presentation

Mission planning shows predicted windows, two cities, estimated UTC crossing,
and the ten-minute interval. Every transition stays visible; only no-alternative
portions become planned communications outages. Overview is a customer-facing
10-foot map: show entry/exit POIs and a brief themed active advisory, without
PoP/IP readouts, forecast lists, totals, or planning controls. Estimates require
no uncertainty or gap acknowledgment. Assume Starshield up unless explicitly
disabled/down; missing PoP information is not a service outage.

Timeline rows contain no added text labels for transition windows. Use an
outlined advisory marker aligned with Starshield, distinguishable from existing
unavailable-service shading; put its meaning in the surrounding legend/details.
Keep measured transport lanes intact. Reflect conditional planned call outages
in the overall posture band, and expose planned X fallback in details. Provide
an accessible description without text inside a timeline row.

The customer PDF retains its existing timeline and Coordination windows table.
Use unlabeled timeline markers and Eastern-time table bounds consistent with the
present PDF. Per the subsequent user copy revision, the event text is exactly
“Starshield Transition Window” and the outlined legend reads exactly “Starshield
Transition”. Keep the existing one-line event cells. Preserve exact UTC bounds
in canonical evidence. City names and center timestamps are available in planner
details rather than required in the customer table.

The PDF posture and Remaining comms describe call continuity: no-alternative
portions show Communications unavailable with no usable secure-call transport;
concurrency-only X fallback prevents an outage and is identified as planned.
Preserve physical transport evidence separately, plus independent outage/SOF
impacts, exact event/legend copy, one-line cells, pagination, and fit checks.

The explanatory note must distinguish possible call drops/reestablishment from
physical transport downtime and explain conditional outage/fallback planning.
Forecast-only exports use captured route/timing/catalog inputs; they must not
inherit unrelated current aircraft mismatch advisories. PDF preparation and
evidence must capture the same forecast revision that is rendered.

## Verification and acceptance

Implementation verification must cover:

- Great-circle nearest assignments, crossing interpolation/refinement,
  anti-meridian routes, multiple boundaries in one leg, region re-entry,
  isolated ties, sustained ambiguity, and routes with no crossing.
- Exact T−300/T+300 bounds; clipping without changing canonical bounds;
  overlapping windows; changes to departure, ETA, route, and catalog inputs.
- Invalid/missing inputs and stale aircraft telemetry, distinguished from a
  valid forecast with no upcoming transitions.
- Same-IP cache retention, failed lookup after IP change, retry success,
  unknown/unrecognized PoPs, early completion, overdue transitions, mismatch
  persistence/clearance, and reset/revision behavior.
- Simulated nearest-PoP/IP/geolocation consistency with and without a route,
  replay centers, anti-meridian motion, timing changes, seeks, and mode
  isolation.
- Unchanged measured transport decisions and default Starshield preference;
  conditional full-window planned outage totals, concurrency-only X fallback,
  independent AR/geometry blocks, partial overlap, and union/no double-counting.
- Rendered planner/Overview and actual customer PDF examples proving unlabeled
  timeline markers, correct ET table bounds, conditional posture/remaining
  comms, overlapping events, and continuation-page readability.
- Catalog-driven cache invalidation and consistent captured export evidence.

Use focused unit/contract tests plus the repository-required isolated production
and browser/PDF acceptance for implementation. All runtime-owning checks must
have wall-clock limits, task-specific resource ownership, cleanup, and verified
teardown. Earlier advisory-only acceptance is insufficient for the revised
conditional-outage behavior; rerun its affected integration/production checks.

## Deferred work

- A PoP management interface modeled after the satellite interface: add/edit
  cities, coordinates, and associated IP ranges.
- Detecting unfamiliar observed PoPs and offering operator-approved catalog
  addition, coordinated with that management interface.
- Historical calibration, window narrowing, configurable window duration,
  Prometheus analysis, or learning from previous Starlink transitions.
- RF satellite/gateway prediction, automatic routing/bandwidth changes, and
  assertions about Starshield's proprietary handover algorithm.

The initial catalog remains configurable through existing configuration
mechanisms. None of these deferred features is required to use the MVP.
