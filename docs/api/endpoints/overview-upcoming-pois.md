# Overview Upcoming POIs API

[Back to API endpoints](./README.md)

## GET `/api/overview/upcoming-pois`

Return the active mission's generated operational POIs for the native Overview
map and quick-reference table. This is a read-only active-route projection;
manually managed and unrelated generic POIs are excluded.

### Response

```json
{
  "state": "available",
  "calculated_at": "2026-09-22T12:00:00+00:00",
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
- `unavailable` — required in-flight telemetry is unavailable.

Each POI has a stable `poi_id`, imported/generated `name`, `kind`, coordinates,
route progress when calculable, timing fields, `flight_phase`, and independent
`upcoming` (table eligibility) and `map_retained` (map visibility) flags.
Generated kinds are `departure`, `arrival`, `aar_start`, `aar_end`,
`x_band_transition`, `ka_coverage_exit`, `ka_coverage_entry`, and
`ka_transition`.

### Timing provenance

`expected_arrival_time` is the scheduled mission-plan timestamp when known. It
is provenance, not live telemetry, and does not drive in-flight urgency,
ordering, expiry, or the displayed ETA.

Before departure, `eta_type: "anticipated"` may be schedule/route derived. In
flight, `eta_type: "estimated"` is calculated from the current telemetry
position and speed against active-route geometry. `estimated_arrival_time` is
`calculated_at + eta_seconds`; it drives the live urgency cue and table ordering
when present. It is a route-aware model estimate, not telemetry and not a
promised schedule. When the estimate cannot be calculated, timing is null and
the UI displays `ETA unavailable` rather than inventing an ETA.

### Table and map lifecycle

The Overview table includes only `upcoming` POIs, preserves the endpoint's
ordered result, and displays at most five rows. Timed records are ordered by
live estimate; untimed records follow in route order.

The map uses `map_retained`, not the table filter. Departure and arrival remain
for the active mission. Other generated operational markers remain while
upcoming and for up to 60 minutes after their current arrival estimate; untimed
markers remain while active route/mission context exists because no truthful
expiry can be calculated.

### Status code

- `200 OK` — the projection returned. Availability is represented by the
  response `state`, not by a fabricated fallback POI or ETA.
