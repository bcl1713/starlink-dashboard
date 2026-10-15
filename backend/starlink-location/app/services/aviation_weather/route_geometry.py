"""Conservative adaptive curve/polygon classification; execute in a worker."""

import math
from itertools import pairwise

from shapely.geometry import Point, box, shape
from shapely.prepared import prep

from app.models.route_sigmets import (
    MAX_ADVISORIES,
    MAX_ROUTE_POINTS,
    MAX_SPANS,
    GeometryMatch,
    GeometryResult,
    IntersectionSpan,
    UnresolvedFeature,
)

from .route_arcs import TERMINAL_M, GreatCircleArc

MAX_VERTICES = 100_000
MAX_INTERVAL_VISITS = 1_000_000
MAX_DEPTH = 52


class GeometryLimit(ValueError):
    pass


def _positions(value):
    if not isinstance(value, list):
        raise TypeError("invalid coordinates")
    if len(value) == 2 and all(
        isinstance(x, (int, float)) and not isinstance(x, bool) for x in value
    ):
        lon, lat = value
        if (
            not math.isfinite(lon)
            or not math.isfinite(lat)
            or not -180 <= lon <= 180
            or not -90 <= lat <= 90
        ):
            raise ValueError("invalid coordinates")
        yield value
    else:
        for child in value:
            yield from _positions(child)


def validate_input(points, features):
    if not isinstance(points, list) or len(points) > MAX_ROUTE_POINTS:
        raise GeometryLimit("route point limit")
    for point in points:
        if len(list(_positions(point))) != 1 or len(point) != 2:
            raise ValueError("invalid route point")
    if not isinstance(features, list) or len(features) > MAX_ADVISORIES:
        raise GeometryLimit("advisory limit")
    ids, vertices = set(), 0
    for feature in features:
        identity = feature.get("id")
        if (
            not isinstance(identity, str)
            or not 1 <= len(identity) <= 256
            or identity in ids
        ):
            raise ValueError("invalid or duplicate feature identity")
        ids.add(identity)
        geometry = feature.get("geometry")
        if geometry is not None:
            if geometry.get("type") not in ("Polygon", "MultiPolygon"):
                continue
            for _ in _positions(geometry.get("coordinates")):
                vertices += 1
                if vertices > MAX_VERTICES:
                    raise GeometryLimit("polygon vertex limit")


def _covered(polygon, position):
    if polygon.covers(Point(position)):
        return True
    if abs(position[0]) == 180:
        return polygon.covers(Point([-position[0], position[1]]))
    return False


def _intervals(arc, polygon, visits):
    prepared = prep(polygon)
    stack = [(0.0, 1.0, 0)]
    pieces, uncertain = [], False
    while stack:
        left, right, depth = stack.pop()
        visits[0] += 1
        if visits[0] > MAX_INTERVAL_VISITS:
            raise GeometryLimit("interval visit limit")
        rectangles = [box(*bounds) for bounds in arc.enclosures(left, right)]
        if all(prepared.disjoint(rectangle) for rectangle in rectangles):
            continue
        if all(prepared.covers(rectangle) for rectangle in rectangles):
            pieces.append((left, right, 0.0))
            continue
        middle = (left + right) / 2
        length = (right - left) * arc.length_m
        if length <= TERMINAL_M:
            witnesses = [
                f for f in (left, middle, right) if _covered(prepared, arc.point(f))
            ]
            if not witnesses:
                uncertain = True
            else:
                pieces.append((witnesses[0], witnesses[0], length))
                for first, last in pairwise(witnesses):
                    # Point witnesses prove contact, not the intervening curve.
                    # Certify that curve before joining them: even a sub-tolerance
                    # hole or unresolved interior gap must remain separate.
                    if all(
                        prepared.covers(box(*bounds))
                        for bounds in arc.enclosures(first, last)
                    ):
                        pieces.append((first, last, length))
                    else:
                        uncertain = True
                        pieces.append((last, last, length))
            continue
        if depth >= MAX_DEPTH:
            raise GeometryLimit("interval depth limit")
        stack.append((middle, right, depth + 1))
        stack.append((left, middle, depth + 1))
    merged = []
    for left, right, error in pieces:
        if merged and merged[-1][1] == left:
            old_left, _, old_error = merged[-1]
            merged[-1] = (old_left, right, max(error, old_error))
        else:
            merged.append((left, right, error))
    return merged, uncertain


def intersect_route(points, features) -> GeometryResult:
    validate_input(points, features)
    arcs, invalid = [], False
    for index, (start, end) in enumerate(pairwise(points)):
        try:
            arc = GreatCircleArc(start, end)
        except ValueError:
            invalid = True
            continue
        if arc.length_m:
            arcs.append((index, arc))
    if not arcs:
        invalid = True
    matches, unresolved, visits = [], {}, [0]
    exhausted, total = False, 0
    for feature in features:
        identity = feature["id"]
        if invalid:
            unresolved[identity] = "invalid-route"
        if exhausted:
            unresolved[identity] = "limit"
            continue
        geometry = feature.get("geometry")
        try:
            polygon = shape(geometry) if geometry else None
            if (
                polygon is None
                or polygon.is_empty
                or not polygon.is_valid
                or polygon.geom_type not in ("Polygon", "MultiPolygon")
            ):
                unresolved[identity] = "unlocated"
                continue
        except (ValueError, TypeError, KeyError):
            unresolved[identity] = "unlocated"
            continue
        spans = []
        for index, arc in arcs:
            try:
                intervals, uncertain = _intervals(arc, polygon, visits)
                if uncertain and identity not in unresolved:
                    unresolved[identity] = "boundary-uncertain"
                for left, right, error in intervals:
                    total += 1
                    if total > MAX_SPANS:
                        raise GeometryLimit("span limit")
                    spans.append(
                        IntersectionSpan(
                            segment_index=index,
                            start_fraction=left,
                            end_fraction=right,
                            entry=arc.point(left),
                            exit=arc.point(right),
                            boundary_error_m=error,
                        )
                    )
            except GeometryLimit:
                unresolved[identity] = "limit"
                exhausted = True
                break
        if spans:
            matches.append(GeometryMatch(feature_id=identity, spans=spans))
    incomplete = invalid or bool(unresolved) or exhausted
    return GeometryResult(
        matches=matches,
        unresolved=[
            UnresolvedFeature(feature_id=k, reason=v) for k, v in unresolved.items()
        ],
        complete=not incomplete,
        reason=(
            "limit"
            if exhausted
            else (
                "invalid-route"
                if invalid
                else "unresolved geometry" if unresolved else None
            )
        ),
    )
