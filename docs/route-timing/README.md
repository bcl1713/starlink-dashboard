# Route timing

Timed KML routes provide expected waypoint arrivals and segment speeds for
planning, route-aware ETAs and simulation. Missing timing falls back to
position/speed estimates where supported; it does not establish a planned UTC
arrival.

- [Concepts](concepts.md): timing profiles, flight phases and ETA modes
- [KML and API examples](implementation.md): valid waypoint descriptions
- [Troubleshooting](troubleshooting.md): missing timing and unavailable
  estimates
- [Navigation](../features/navigation.md): route and POI operator workflow
- [Weather](../features/overview-weather.md#sigmet-crossing-timing): live SIGMET
  crossing estimates and simulation clock behavior

Mission operators activate a leg through Missions. Standalone route activation
is available for route testing but does not establish mission context. See the
[V2 activation contract](../missions/v2-mission-retirement-acceptance.md).

Timing endpoints are described in the
[route API reference](../api/endpoints/routes.md). Network and position displays
use the native [Overview](../features/overview.md). Performance depends on route
size, timing coverage and deployment resources; old test totals and example
cache hit rates are not service guarantees.
