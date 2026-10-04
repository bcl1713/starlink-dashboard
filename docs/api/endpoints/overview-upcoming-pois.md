# Overview Upcoming POIs API

[Back to API endpoints](./README.md)

## GET `/api/overview/upcoming-pois`

Return the active mission's generated operational POIs for the native Overview
map and departure/arrival panel. This is a read-only active-route projection;
manually managed and unrelated generic POIs are excluded.

### Response

```json
{
  "state": "available",
  "calculated_at": "2026-09-22T12:00:00+00:00",
  "flight_phase": "in_flight",
  "scheduled_departure_time": "2026-09-22T10:00:00Z",
  "position_observed_at": "2026-09-22T11:59:59Z",
  "position_state": "fresh",
  "current_route_progress": 10,
  "pois": [
    {
      "poi_id": "arrival-rkso",
      "name": "RKSO",
      "kind": "arrival",
      "latitude": 37.43,
      "longitude": 126.45,
      "projected_route_progress": 100,
      "expected_arrival_time": "2026-09-22T14:00:00+00:00",
      "eta_seconds": 7200,
      "estimated_arrival_time": "2026-09-22T14:00:00+00:00",
      "eta_type": "estimated",
      "flight_phase": "in_flight",
      "upcoming": true,
      "map_retained": true
    }
  ]
}
```

`state` is one of:

- `available` — an active Mission V2 leg has at least one generated POI that is
  upcoming;
- `no_active_mission` — no Mission V2 leg is active. This can coexist with a
  route-only active route; the route alone does not fabricate a mission context;
- `route_unavailable` — the active Mission V2 leg has no resolvable matching
  route;
- `inconsistent_active_mission` — active Mission V2 records are inconsistent;
- `no_generated_pois` — the active Mission V2 leg and route have no generated
  POIs;
- `no_upcoming_pois` — generated records exist but none is upcoming; or
- `unavailable` — required in-flight position provenance or speed is
  unavailable, or position is stale. Generated records remain available for map
  context.

Each POI has a stable `poi_id`, imported/generated `name`, `kind`, coordinates,
route progress when calculable, timing fields, `flight_phase`, and independent
`upcoming` (route eligibility) and `map_retained` (map visibility) flags.
Generated kinds are `departure`, `arrival`, `aar_start`, `aar_end`,
`x_band_transition`, `ka_coverage_exit`, `ka_coverage_entry`, and
`ka_transition`.

### Timing provenance

`expected_arrival_time` is the scheduled mission-plan timestamp when known. It
is provenance, not live telemetry, and does not drive in-flight urgency,
ordering, expiry, or the displayed ETA.

Before departure, `eta_type: "anticipated"` may be schedule/route derived. In
flight, `eta_type: "estimated"` is calculated from the current telemetry
position and speed against active-route geometry. Generated mission events use
their stored route-segment projection, including its interior projected point;
current speed is blended only on the current route portion and planned segment
speeds apply afterward. The remaining current portion starts at the aircraft's
projected position within its segment, so an interior-event ETA decreases as
the aircraft approaches instead of restarting from the nearest waypoint.
There is no direct-coordinate ETA fallback when
projection, route geometry, travel direction, or telemetry is unsafe or
unavailable. `estimated_arrival_time` is `calculated_at + eta_seconds`; it
drives the live urgency cue and table ordering when present. It is a route-aware
model estimate, not telemetry and not a promised schedule. When the estimate
cannot be calculated, timing is null and the UI displays `ETA unavailable`
rather than inventing an ETA. Ordinary estimates display as UTC time alone;
anticipated times retain an explicit `anticipated` label.

### Position and flight provenance

`flight_phase` is `pre_departure`, `in_flight`, `post_arrival`, or null when
active context cannot be resolved. `scheduled_departure_time` comes from the
unique generated departure POI's explicit effective mission schedule, including
configured departure adjustments; it is null when absent or ambiguous. It is
used only for the scheduled-departure display, never as an in-flight ETA.

`position_observed_at` is the UTC collection time of the exact verified
coordinates used for route progress/ETA, or null when unverified. It is not
`calculated_at`, network collection time, or a receiver-provided GPS fix time.
Live missing/invalid coordinate defaults receive no timestamp; zero coordinates
are valid observations. Simulation timestamps generated positions. Cached
observations retain their original timestamp.

`position_state` is `fresh` for age below ten seconds, `stale` at ten seconds or
older, and `unavailable` for missing/invalid coordinates or provenance. Up to
five seconds of future skew is allowed without altering the observation time;
larger offsets and timestamps without timezone provenance are unavailable.
In-flight stale/unavailable position suppresses `eta_seconds` and
`estimated_arrival_time`. Stale valid coordinates may retain last-known route
eligibility; invalid position cannot establish progress. The frontend rechecks
age between polls and suppresses timing on failed/expired refreshes.
Predeparture schedule timing does not depend on position freshness.

In-flight timing also requires an independently fresh, verified speed observation.
The live GPS tracker needs two verified samples with at least 0.1 seconds of
elapsed coverage. Startup, GPS loss and RPC failures reset that coverage; the
first recovered position retains map context but cannot enable timing using a
placeholder zero. Genuine measured stationary zero remains usable. Speed
provenance is internal telemetry metadata; it does not change `/api/status`.

`current_route_progress` is the continuous route progress derived from that
same position projected onto the route, or null when unknown. It does not snap
to the nearest waypoint. A destination is labeled passed only when progress
establishes it; an unknown eligibility state is not evidence of passage.

### Panel and map lifecycle

The response preserves its existing ETA-first ordering, with untimed entries in
route order afterward. The panel independently selects the earliest `upcoming`
non-departure record by route progress and stable ID, including untimed events.
Landing is the unique `kind: arrival` record in the full response, regardless of
its position in the array. Names do not establish identity. Missing/ambiguous or
passed destination stays explicit; only `post_arrival` establishes landed.

Before departure, show one scheduled-departure section, counting down and then
up with red **AGO** text when late. In flight, show next POI plus landing, or
one combined landing section when the destination is next. In-flight countdowns
never become negative. UTC labels include the date across day boundaries, and
full timestamps remain accessible. `expected_arrival_time` never substitutes for
a missing in-flight estimate.

The map uses `map_retained`, not the panel selection. Departure and arrival
remain for the active mission. Other generated operational markers remain while
upcoming and for up to 60 minutes after their current arrival estimate; untimed
markers remain while active route/mission context exists because no truthful
expiry can be calculated.

### Status code

- `200 OK` — the projection returned. Availability is represented by the
  response `state`, not by a fabricated fallback POI or ETA.
