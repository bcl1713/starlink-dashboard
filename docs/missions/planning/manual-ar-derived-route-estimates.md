# Manual AR Derived-Route Estimates

## Purpose

A Manual AR track can be selected as input to an **estimated** replacement of a
portion of a planned route. This feature produces a derived route basis for
planning calculations; it does not report actual aircraft telemetry.

## Source Route and Saved Input

The uploaded source KML remains immutable. The system does not overwrite its
geometry, waypoint timing, or route file.

Manual AR tracks remain separate operator-entered, ordered points. When a
replacement is selected, the saved configuration contains the selected track ID
and may contain splice or speed inputs. Calculated geometry, anchors, timing,
and ETA changes are not persisted as a second route. They are rebuilt from the
source route and selected Manual AR input for each calculation.

The persisted splice model has fields for leave/rejoin anchor and speed inputs.
In the current implementation, the derived-route builder selects anchors and
resolves speed from the source route; it uses the selected track ID and does not
apply those saved anchor or speed values as overrides.

Phase 1 selects one Manual AR track for route replacement. Other saved Manual AR
tracks are not automatically composed into the derived route.

## Feasibility and Route Basis

The system projects the first and last Manual AR points onto the planned route
and only accepts a forward-progress leave/rejoin pair. A feasible estimate
contains:

- planned source-route portions before and after the replacement;
- an entry connector from the planned route to the Manual AR track;
- the Manual AR track in its entered order; and
- an exit connector back to the planned route.

Every calculated point has provenance: `planned`, `entry_connector`,
`manual_track`, or `exit_connector`. The API labels a feasible result as
`route_basis: "derived_estimate"` and includes `estimated: true`; this is an
estimate, not a new planned KML or an actual flown path.

### Connector limit and unavailable result

Each entry or exit connector is limited to 100 nautical miles. If no valid
forward pair can be formed within that limit, the result is unavailable with
`unavailable_reason: "no_feasible_splice"`.

For an unavailable result, the route basis remains `planned`, no partial
connector is created, and the estimate has no points or time delta. A missing
selected track also keeps the planned basis and reports
`unavailable_reason: "selected_track_not_found"`. A source route with fewer than
two points reports `source_route_too_short`.

## Distance, Timing, and Confidence

The response reports planned and derived total distances, the duration of the
replaced planned portion, the derived diversion duration, and `delta_seconds`. A
positive delta is an estimated downstream delay; a negative delta is an
estimated gain.

The estimated speed is resolved in this order:

1. Median of valid positive planned segment-speed values
   (`global_weighted_median`)
2. Planned total distance divided by planned total duration
   (`planned_total_distance_duration`)
3. A labelled 500-knot fallback (`fallback_500kt`)

The selected `speed_knots` and `speed_source` are returned with the estimate.
When the source timestamps around either anchor are absent or not strictly
increasing, the replaced planned duration uses route distance and the selected
speed instead. The response adds a warning describing that fallback.

Confidence is `high` when the selected splice is unambiguous under the current
scoring result. It is `low` when another feasible splice has a similar score; in
that case the response includes a warning that multiple feasible anchors are
similar. Confidence and warnings describe the estimate selection, not aircraft
performance.

## Timeline, Preview, and Export Effects

For a feasible selected track, the timeline builder uses an ephemeral derived
route. It preserves source timing before the leave anchor, times the diversion
at the selected effective speed, and applies `delta_seconds` once to downstream
source-route timing and the final route arrival time. Timeline samples and their
coverage/transport calculations therefore use the selected route basis.

The timeline preview exposes `route_basis` and `derived_route_estimate` next to
its normal timeline data and samples. With no selection, or with an unavailable
estimate, its basis is `planned` and `derived_route_estimate` is respectively
`null` or an unavailable estimate.

Mission package export rebuilds each leg timeline from current leg settings
before generating its per-leg CSV and PowerPoint artifacts. Consequently, a
feasible selected derived route supplies the same recalculated timeline times
used for those artifacts; export does not independently recompute a separate
planned-only timeline. If rebuilding fails, package export can fall back to a
cached timeline, so an export should be checked against the current preview when
the route basis matters operationally.

Current export artifacts consume the rebuilt timeline but do not add a dedicated
`route_basis`, estimate-confidence, speed-source, or warning field. Treat an
export's timing as derived only when its corresponding current timeline was
built from a feasible selected estimate; otherwise it remains planned-basis.

## API Fields

When a Manual AR replacement is selected, preview responses include:

- `route_basis` — `derived_estimate` for a feasible estimate, otherwise
  `planned`
- `derived_route_estimate.available` — whether a derived estimate was built
- `derived_route_estimate.estimated` — always true for this feature
- `derived_route_estimate.unavailable_reason` — populated when unavailable
- `planned_distance_nm`, `derived_distance_nm`, `planned_duration_seconds`,
  `derived_duration_seconds`, and `delta_seconds`
- `speed_knots`, `speed_source`, `confidence`, and `warnings`
- `leave_anchor` and `rejoin_anchor` — the selected planned-route locations
- `points[]` — derived points and their provenance

See the [Timeline Preview API Endpoint](../../api/endpoints/timeline-preview.md)
for the endpoint contract.
