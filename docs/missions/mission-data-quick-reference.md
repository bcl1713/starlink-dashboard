# Mission data quick reference

Mission V2 separates a parent mission from its executable legs:

| Model                | Owns                                                                                     |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `Mission`            | `id`, `name`, ordered `legs`, metadata and timestamps                                    |
| `MissionLeg`         | route binding, transport configuration, adjusted departure and server-managed activation |
| `MissionLegTimeline` | computed leg segments, advisories and statistics                                         |
| `ParsedRoute`        | geometry, named waypoints and optional timing profile                                    |

Fetch geometry through the leg's `route_id`; the parent mission has no flat
`route_id`, transport configuration or activation flag. Timeline and route
objects are separate inputs to map/export generation. Missing timing must stay
explicit rather than being replaced by a fabricated arrival.

Authoritative model definitions are in
[`app/mission/models.py`](../../backend/starlink-location/app/mission/models.py)
and
[`app/models/route.py`](../../backend/starlink-location/app/models/route.py).
See [model references](mission-data-structures.md),
[activation](README.md#mission-v2-activation), and
[export snapshots](planning/outputs.md).
