
# Overview Upcoming POIs Design

**Issue:** #149

## Purpose

Extend the native React `/overview` globe with route-aware operational points
of interest (POIs). The globe supplies retained spatial context; a compact
Top 5 table supplies the immediate operational queue. Grafana remains the
supported fallback and parity comparator; this slice neither changes nor
retires it.

## Scope

The active mission produces and exposes these generated POI kinds:

<!-- markdownlint-disable MD060 -->
| Kind | Source |
| --- | --- |
| `departure` | Identified departure waypoint or route endpoint fallback |
| `arrival` | Identified arrival waypoint or route endpoint fallback |
| `aar_start` / `aar_end` | Resolved AAR window boundaries |
| `x_band_transition` | X-band transition schedule |
| `ka_coverage_exit` / `ka_coverage_entry` | Ka coverage gaps |
| `ka_transition` | Ka satellite swaps |
<!-- markdownlint-enable MD060 -->

The existing KML parser supplies the identified departure and arrival
waypoints. Their imported waypoint names are the endpoint POI labels, normally
the airfield ICAO code. A coordinate-only route endpoint is a fallback only
when no suitable named semantic waypoint exists.

Manually managed or unrelated generic POIs are not added to the Overview
operational view.

## Data Model and API

Add an optional, structured generated-POI `kind` to the persisted POI model.
It must be carried through create/read responses without using display-name
prefixes as a classifier. Existing POI JSON remains loadable without this
field. Regenerating a mission replaces its generated POIs with the complete
current typed set, including departure and arrival.

Add a read-only active-route Overview POI response at:

```text
GET /api/overview/upcoming-pois
```

The response describes the active mission's generated POIs. Every record
contains its stable POI ID, label, `kind`, latitude, longitude, projected route
progress, and scheduled-arrival timestamp when known. It also carries the
current ETA result: `eta_seconds`, `estimated_arrival_time`, ETA mode
(`anticipated` or `estimated`), flight phase, and computed states for
`upcoming` and map-retention. The response carries a calculation timestamp so
the client can update the countdown between endpoint refreshes.

Before departure, `anticipated` ETA may use the imported schedule. Once the
existing flight-status transition marks the mission in flight, `estimated` ETA
must be recalculated from the current telemetry position and speed against the
active route using the existing route-aware ETA service. It must not be derived
by subtracting the wall clock from a scheduled arrival. A changed active-route
geometry (for example, a weather diversion) must therefore feed the same
calculation. `estimated_arrival_time` is `calculated_at + eta_seconds`; it is a
model estimate, not telemetry or a promised schedule.

The top-level response explicitly distinguishes `available`, `no_active_route`,
`no_generated_pois`, `no_upcoming_pois`, and `unavailable`. It must never use
fallback coordinates, default speeds, or synthetic expected-arrival times to
make data look complete.

## Lifecycle and Filtering

The API owns the active mission and route-aware classification.

### Table: upcoming only

- Pre-departure: include departure and all later generated POIs.
- In flight: include only generated POIs ahead of current route progress.
- Post-arrival: include none.

The table displays at most five rows. POIs with a current ETA are ordered by
ascending `estimated_arrival_time`; untimed/uncalculable POIs follow in route
order and show `ETA unavailable` rather than an invented value. In anticipated
mode, the schedule-derived ETA remains explicitly labelled anticipated.

### Globe: retained operational context

The map does not share the table's immediate-disappearance rule.

- Departure and arrival remain rendered for the entire active mission.
- AAR, X-band, and Ka operational POIs render while upcoming and until 60
  minutes after their current calculated arrival. Before departure that is the
  anticipated schedule-derived arrival; in flight it is the route-aware
  estimated arrival.
- An untimed operational POI remains while its active route/mission context
  remains, because a truthful expiry cannot be calculated.
- No active route or mission means no Overview POI marker; existing aircraft,
  GEP, route, history, and satellite context continue to follow their current
  contracts.

Departure and arrival replace the existing standalone first/last route-point
stars on Overview. They are rendered exactly once from the generated POI
projection and labelled with their imported POI names.

## Overview UI

Render each retained generated POI using the existing shared occluded
`StarMarker` and globe label primitive. Do not add a second marker renderer or
global bloom.

Add an unscrollable `Upcoming POIs` overlay panel with a fixed maximum of five
rows. Its visual columns are:

<!-- markdownlint-disable MD060 -->
|  | POI | Type | ETA |
| --- | --- | --- | --- |
| colour swatch only | imported/generated label | generated kind label | UTC estimated or anticipated arrival plus timing mode, or `ETA unavailable` |
<!-- markdownlint-enable MD060 -->

The first column deliberately has no header and contains only a compact visual
swatch. ETA conveys the textual operational information.

The panel must animate size changes smoothly when its number of visible rows or
state changes. CSS that establishes the table body's height/maximum height,
padding, opacity, or border/background state includes transitions so a change
between empty, partial, and five-row states does not jump starkly. The maximum
of five rows keeps the panel bounded and removes the need for a scrollbar.

Panel states are compact and explicit: loading, unavailable, no active route,
no generated POIs, and no upcoming POIs. They do not replace or obscure the
rest of the Overview.

## Timing Colour Projection

Use one shared frontend urgency projection for globe marker colour and table
swatch colour. It derives remaining time from the API's dynamic
`estimated_arrival_time` and the local one-second Overview clock:

- 60 minutes or more: green;
- 30 to 60 minutes: linear interpolation from yellow to green;
- 0 to 30 minutes: linear interpolation from red to yellow;
- overdue but map-retained: red;
- unavailable or invalid timing: neutral slate.

The colour calculation is a UI cue only. The API's ETA/timing mode remains the
source for actual displayed operational timing. `expected_arrival_time` is
scheduled provenance and must not drive in-flight colour, ordering, expiry, or
the displayed ETA.

## Failure Handling

The endpoint and client fail closed. Invalid coordinates cannot render markers.
Missing route, mission, timing, or telemetry cannot become invented POIs or
ETAs. A request error displays the unavailable state while preserving unrelated
Overview layers. Endpoint refreshes and the local countdown must not create
overlapping polling requests.

## Verification

1. Backend tests cover imported endpoint labels, all generated kinds,
   idempotent replacement on mission refresh, active route/mission scoping,
   pre-departure/in-flight/post-arrival table filtering, top-five ordering,
   untimed route-order fallback, and the 60-minute map-retention boundary.
   They prove that a 30-minute-late in-flight departure and a changed active
   route calculate their POI ETA from current position/speed and active-route
   geometry rather than from a scheduled clock.
2. Frontend unit tests cover every urgency-colour boundary, overdue and
   unavailable values, shared marker/swatch colour use, table limit/order/state,
   endpoint marker deduplication, retention projection, and the smooth-size CSS
   contract.
3. The exact-head Playwright Overview suite runs at 1920x1080 with mocked
   active mission POIs. It proves imported departure/arrival labels, retained
   passed operational markers, five non-scrollable table rows, table/map colour
   consistency, and rendered screenshot evidence.
4. Completion requires fresh frontend lint/build/unit tests with `NODE_ENV=test`,
   focused and full backend tests, independent implementation review, and
   independent final review.

## Documentation Impact

Update the Overview feature documentation and API endpoint reference in the
same PR. No Grafana dashboard modification, retirement, operator runbook, or
release documentation change is currently in scope.

## Non-Goals

- Rendering all manually managed POIs on Overview.
- A scrollable POI table or a table larger than five rows.
- Claiming generated estimated data is telemetry.
- Changing Grafana, weather/radar scope, global marker lighting, or the native
  fullscreen navigation contract.
