"""Complete pairwise spherical boundary enumeration on minor great-circle legs."""

import json
from collections.abc import Sequence
from hashlib import sha256
from itertools import combinations, pairwise
from math import atan2, cos, degrees, hypot, pi, radians, sin

from .models import PopCatalog, PopCrossing, RouteVertex

ANGULAR_TOLERANCE = 1e-10
EARTH_RADIUS_METERS = 6371000.0
Vector = tuple[float, float, float]


class PopGeometryError(ValueError):
    """A geographic prediction cannot be resolved without arbitrary choices."""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def _cross(a: Vector, b: Vector) -> Vector:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit(latitude: float, longitude: float) -> Vector:
    lat, lon = radians(latitude), radians(longitude)
    return (cos(lat) * cos(lon), cos(lat) * sin(lon), sin(lat))


def _angle(a: Vector, b: Vector) -> float:
    return atan2(hypot(*_cross(a, b)), _dot(a, b))


def _winner(position: Vector, sites: tuple[tuple[str, Vector], ...], previous_id=None):
    distances = [(site_id, _angle(position, vector)) for site_id, vector in sites]
    minimum = min(distance for _, distance in distances)
    tied = [
        site_id
        for site_id, distance in distances
        if distance - minimum <= ANGULAR_TOLERANCE
    ]
    if previous_id in tied:
        return previous_id
    return tied[0] if len(tied) == 1 else None


def nearest_pop(
    latitude: float,
    longitude: float,
    catalog: PopCatalog,
    previous_id: str | None = None,
) -> str | None:
    """Select a unique nearest site, retaining a tied previous identity only."""
    vertex = RouteVertex(latitude=latitude, longitude=longitude)
    sites = tuple((s.id, _unit(s.latitude, s.longitude)) for s in catalog.sites)
    return _winner(_unit(vertex.latitude, vertex.longitude), sites, previous_id)


def _boundaries(u: Vector, v: Vector, arc: float, sites) -> list[float]:
    roots = [0.0, arc]
    for (_, a), (_, b) in combinations(sites, 2):
        delta = tuple(x - y for x, y in zip(a, b))
        # A*cos(theta)+B*sin(theta)=0. Consecutive roots are pi apart.
        coefficient_a, coefficient_b = _dot(u, delta), _dot(v, delta)
        if hypot(coefficient_a, coefficient_b) < 1e-15:
            continue  # Identically tied along this great circle; intervals decide.
        base = atan2(-coefficient_a, coefficient_b)
        for multiple in range(-1, 3):
            root = base + multiple * pi
            if ANGULAR_TOLERANCE < root < arc - ANGULAR_TOLERANCE:
                roots.append(root)
    unique = []
    for root in sorted(roots):
        if not unique or root - unique[-1] > ANGULAR_TOLERANCE:
            unique.append(root)
    return unique


def find_crossings(
    vertices: Sequence[RouteVertex], catalog: PopCatalog, revision: str
) -> tuple[PopCrossing, ...]:
    """Evaluate every open boundary interval and emit only actual winner changes.

    A crossing on a shared vertex belongs to the following nondegenerate segment
    at fraction zero. Touching a boundary and turning back emits no crossing.
    Distances use the same spherical radius as mission timing's haversine.
    """
    sites = tuple((s.id, _unit(s.latitude, s.longitude)) for s in catalog.sites)
    cities = {site.id: site.city for site in catalog.sites}
    crossings = []
    previous = None
    distance = 0.0
    for index, (start, end) in enumerate(pairwise(vertices)):
        u, destination = _unit(start.latitude, start.longitude), _unit(
            end.latitude, end.longitude
        )
        arc = _angle(u, destination)
        if arc <= ANGULAR_TOLERANCE:
            continue
        if pi - arc <= ANGULAR_TOLERANCE:
            raise PopGeometryError(
                "Antipodal route leg has no unique minor great circle"
            )
        normal = _cross(u, destination)
        magnitude = hypot(*normal)
        v = _cross(tuple(component / magnitude for component in normal), u)
        roots = _boundaries(u, v, arc, sites)
        for left, right in pairwise(roots):
            midpoint = (left + right) / 2
            position = tuple(
                x * cos(midpoint) + y * sin(midpoint) for x, y in zip(u, v)
            )
            winner = _winner(position, sites)
            if winner is None:
                raise PopGeometryError(
                    "Sustained nearest-PoP ambiguity along route leg"
                )
            if previous is not None and winner != previous:
                position = tuple(x * cos(left) + y * sin(left) for x, y in zip(u, v))
                latitude = degrees(atan2(position[2], hypot(position[0], position[1])))
                longitude = degrees(atan2(position[1], position[0]))
                fraction = left / arc
                identity = json.dumps(
                    [revision, catalog.fingerprint, index, fraction, previous, winner]
                )
                crossings.append(
                    PopCrossing(
                        id=sha256(identity.encode()).hexdigest(),
                        from_pop_id=previous,
                        to_pop_id=winner,
                        from_city=cities[previous],
                        to_city=cities[winner],
                        segment_index=index,
                        fraction=fraction,
                        latitude=latitude,
                        longitude=longitude,
                        distance_meters=distance + left * EARTH_RADIUS_METERS,
                    )
                )
            previous = winner
        distance += arc * EARTH_RADIUS_METERS
    return tuple(crossings)
