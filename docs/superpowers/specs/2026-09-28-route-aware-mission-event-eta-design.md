# Route-Aware Mission-Event ETA Design

## Purpose

Issue #177 corrects the active Overview upcoming-POI projection for generated
Mission V2 events. In flight, an event may be geographically off the route but
still occur at a defined projected location along it. When usable current or
simulated telemetry exists, Overview must calculate the event's ETA along the
planned route to that projected location.

The result is an operational estimate for situational awareness. It is not
telemetry, a schedule guarantee, or an authorization to fabricate an ETA when
required inputs are unsafe or unavailable.

## Current behavior and root cause

`POIManager` creates generated mission-event POIs through the established route
projection flow. Its persisted projection record includes an interior projected
latitude/longitude, a route progress value, and the corresponding route segment
index.

`ETACalculator._calculate_off_route_eta_with_projection_estimated()` currently
receives that record but independently re-discovers the segment by applying a
second distance-to-segment tolerance. A valid interior projection can fail the
second approximation. The route-aware call then returns no ETA, leaving
`eta_seconds` and `estimated_arrival_time` null even though the stored
projection and in-flight simulation telemetry are usable.

This is a contract-boundary defect: the projection producer and ETA consumer
are not using the same established route-projection result.

## Decision

### Stored projection is the ETA input contract

For an off-route generated mission event, the estimated route-aware path will
consume the projection record stored on the POI as one validated tuple:

- `projected_latitude` and `projected_longitude` identify the route position at
  which the event occurs;
- `projected_waypoint_index` identifies the active-route segment containing
  that point; and
- `projected_route_progress` establishes its ordered position along the route.

The ETA calculator must not re-project the event or use a tolerance-based
second segment search. It must validate that all tuple fields are finite, the
coordinates and progress are in range, the segment index is valid for the
active route, and the route has usable timing information.

The projection must be ahead of the aircraft's route position. If the nearest
current route point is after the stored projection segment, the event is not a
future destination for this calculation and the estimated ETA is unavailable.

### Segment-aware in-flight estimate

For a valid projected event ahead of the aircraft, the calculation walks route
segments from the nearest current route point to the stored projected point:

1. On the first remaining segment, blend current/simulated speed with the
   segment's planned speed, following the existing estimated ETA policy.
2. On later segments, use each segment's planned speed, or the established
   valid speed fallback where the segment has no plan.
3. For the destination segment, measure only from that segment's start to the
   stored projected coordinate.
4. Sum segment travel times. A positive finite result becomes `eta_seconds`;
   `estimated_arrival_time` remains `calculated_at + eta_seconds`.

This deliberately preserves route semantics. The direct great-circle distance
from aircraft coordinates to an off-route event coordinate is not an ETA
fallback for Overview mission events.

### Failure behavior

Return unavailable timing (`eta_seconds: null` and
`estimated_arrival_time: null`) when any required input is absent or unsafe,
including:

- missing, non-finite, or out-of-range telemetry coordinates or speed;
- absent/invalid stored projection fields;
- invalid route geometry, segment index, or route timing;
- invalid/non-positive segment speed;
- a stored projection that is behind the current route position; or
- a non-positive/non-finite calculated duration.

No direct-distance fallback, default endpoint coordinate, inferred current
position, or fabricated schedule-derived in-flight estimate is permitted.

Pre-departure anticipated behavior remains schedule/route based and is outside
this defect correction except where tests prove it is unchanged.

## API and user experience

The `/api/overview/upcoming-pois` response shape remains unchanged.

- In flight, `eta_type` remains `estimated`. A valid route-aware result carries
  positive `eta_seconds` and a calculated `estimated_arrival_time`.
- When unavailable, both timing values remain null and Overview renders `ETA
  unavailable`.
- `expected_arrival_time` remains mission-plan provenance; it does not override
  an in-flight estimate.
- The Overview table header remains `ETA`. Ordinary estimates display UTC time
  without redundantly appending `estimated`; anticipated values retain the
  explicit `anticipated` qualifier. This distinguishes the schedule-oriented
  state where it adds value without implying telemetry.

## Interfaces and ownership

The implementation is intentionally confined to the existing ETA projection
consumer and its callers:

- `app.services.eta.projection.ETAProjection` owns validation and segment-walk
  ETA calculation for off-route projected events.
- `POIManager` and the mission timeline generator remain projection producers;
  their persisted model schema and projection algorithm are not changed.
- `app.services.overview_upcoming_pois` remains the endpoint-specific adapter
  that passes only actual/simulated telemetry and preserves null results.
- `UpcomingPoisPanel` owns the presentation distinction between ordinary
  estimated and anticipated labels.

No route format, Mission V2 persistence schema, public endpoint field, Docker
configuration, or CI workflow changes are in scope.

## Test strategy and acceptance evidence

Strict TDD must use independent vertical slices. Each new behavior starts with
an endpoint or helper regression test that fails against the pre-fix path, then
receives the smallest implementation that makes it pass.

Required coverage:

1. A generated mission event located off-route with a valid interior stored
   projection and deterministic in-flight simulation telemetry receives a
   positive ETA and calculated arrival time. Its expected value follows the
   projected route point and is distinguishable from a direct-coordinate ETA.
2. A multi-segment route proves current-speed blending on the first remaining
   segment and planned speeds later in the route.
3. Missing, malformed, out-of-range, and behind-aircraft projections preserve
   null timing rather than selecting any direct-distance fallback.
4. The endpoint functions with deterministic simulation telemetry and without a
   physical-aircraft data source.
5. Existing endpoint, anticipated-mode, active-leg filtering, and no-telemetry
   behavior remain valid.
6. Frontend unit and 1920x1080 browser coverage prove ordinary estimates omit
   the redundant label while anticipated timing retains it.

The implementation report must record each RED command/output, corresponding
GREEN result, changed-file scope, static/type/lint results, and fresh browser
acceptance evidence if table wording changes.

## Documentation impact

Update the Upcoming POIs endpoint reference and Overview feature documentation
to state that generated mission events use their stored route projection, that
in-flight timing is a route-aware estimate rather than telemetry, and that
unsafe inputs produce an unavailable ETA. No release note or operator runbook
change is required because the endpoint contract and operating procedure do not
change.

## Non-goals

- No generic straight-line or default-speed fallback for in-flight Overview
  mission events.
- No change to physical telemetry ingestion or simulation mechanics.
- No re-projection, migration, or persistence rewrite for existing POIs.
- No change to Grafana, route editing, mission timeline scheduling, or manual
  AAR estimates.
- No claim that the estimate is live telemetry or schedule truth.
