"""UTC precision candidates and immutable primary-route occurrence anchors."""

from datetime import datetime, timedelta

from app.models.route import ParsedRoute
from app.services.kml.geometry import haversine_distance

from .models import ARMatchCandidates, ExpectedLeg, ItineraryAR
from .types import RouteAnchor, utc_timestamp


class RouteAnchorError(ValueError):
    code = "invalid_route_anchor"
    retryable = False


def _baseline_delta(route):
    if (
        route.source_departure_time
        and route.timing_profile
        and route.timing_profile.departure_time
    ):
        return route.timing_profile.departure_time - route.source_departure_time
    return timedelta(0)


def _anchor(route, index, fraction, timestamp, occurrence_id):
    a = route.points[index]
    b = route.points[min(index + 1, len(route.points) - 1)]
    lon_delta = (b.longitude - a.longitude + 180) % 360 - 180
    longitude = (a.longitude + fraction * lon_delta + 180) % 360 - 180
    return RouteAnchor(
        route_id=route.route_id,
        content_hash=route.content_hash,
        segment_index=index,
        fraction=fraction,
        occurrence_id=occurrence_id,
        source_time=timestamp - _baseline_delta(route),
        latitude=a.latitude + fraction * (b.latitude - a.latitude),
        longitude=longitude,
    )


def _candidates(timestamp, precision, route):
    if (
        route.ingestion_profile != "planning_v1"
        or not route.content_hash
        or not route.route_id
    ):
        raise RouteAnchorError("Occurrence matching requires a planning_v1 route")
    timestamp = utc_timestamp(timestamp)
    candidates = []
    delta = _baseline_delta(route)
    for i, point in enumerate(route.points):
        time = point.expected_arrival_time
        if time is None or point.timing_source == "interpolated":
            continue
        source = time - delta
        same = (
            source == timestamp
            if precision == "second"
            else source.replace(second=0, microsecond=0)
            == timestamp.replace(second=0, microsecond=0)
        )
        if same:
            candidates.append(_anchor(route, i, 0, time, point.occurrence_id))
    if candidates:
        return candidates
    # Interpolation is explicit and uses an exact source timestamp; no nearest
    # named AR waypoint is substituted for an absent exit.
    for i, (a, b) in enumerate(zip(route.points, route.points[1:])):
        if a.expected_arrival_time is None or b.expected_arrival_time is None:
            continue
        start, end = a.expected_arrival_time - delta, b.expected_arrival_time - delta
        if start <= timestamp < end:
            fraction = (timestamp - start).total_seconds() / (
                end - start
            ).total_seconds()
            candidates.append(
                _anchor(
                    route,
                    i,
                    fraction,
                    timestamp + delta,
                    f"segment:{i}:{fraction:.12g}",
                )
            )
    return candidates


def ar_match_candidates(
    leg: ExpectedLeg, route: ParsedRoute
) -> list[ARMatchCandidates]:
    """Expose all ordered valid candidate pairs for operator selection."""
    result = []
    for ar in leg.ar_rows:
        start = _candidates(ar.entry_time, ar.source_time_precision, route)
        end = _candidates(ar.exit_time, ar.source_time_precision, route)
        pairs = [
            (a, b)
            for a in start
            for b in end
            if a.source_time < b.source_time
            and a.segment_index + a.fraction < b.segment_index + b.fraction
        ]
        if pairs:
            start = [a for a in start if any(a == p[0] for p in pairs)]
            end = [b for b in end if any(b == p[1] for p in pairs)]
        elif start and end:
            start, end = [], []
        result.append(
            ARMatchCandidates(ar_id=ar.id, start_candidates=start, end_candidates=end)
        )
    return result


def match_ar_windows(leg: ExpectedLeg, route: ParsedRoute) -> list[ItineraryAR]:
    """Return copied AR rows, preserving source values and unresolved evidence."""
    result = []
    for ar, candidates in zip(leg.ar_rows, ar_match_candidates(leg, route)):
        if ar.match_status == "excluded":
            result.append(ar.model_copy(deep=True))
            continue
        start, end = candidates.start_candidates, candidates.end_candidates
        status = (
            "matched"
            if len(start) == len(end) == 1
            else "ambiguous" if start and end else "unresolved"
        )
        result.append(
            ar.model_copy(
                update={
                    "match_status": status,
                    "start_anchor": start[0] if status == "matched" else None,
                    "end_anchor": end[0] if status == "matched" else None,
                    "confirmed": False,
                },
                deep=True,
            )
        )
    return result


def resolve_anchor(
    anchor: RouteAnchor, route: ParsedRoute, adjustment: datetime | None = None
) -> datetime:
    """Resolve source-bound, fixed UTC or elapsed overrides against one baseline."""
    if anchor.route_id != route.route_id or anchor.content_hash != route.content_hash:
        raise RouteAnchorError("Anchor does not belong to this immutable route version")
    if anchor.segment_index >= len(route.points):
        raise RouteAnchorError("Anchor segment is outside this route")
    if anchor.fraction > 0 and anchor.segment_index >= len(route.points) - 1:
        raise RouteAnchorError("Anchor fraction has no route segment")
    point = route.points[anchor.segment_index]
    occurrence = f"segment:{anchor.segment_index}:{anchor.fraction:.12g}"
    valid_occurrences = {occurrence}
    if anchor.fraction == 0:
        valid_occurrences.add(point.occurrence_id)
    if anchor.occurrence_id not in valid_occurrences:
        raise RouteAnchorError("Anchor occurrence is absent from this route")
    if anchor.timing_mode == "route_bound":
        end = route.points[min(anchor.segment_index + 1, len(route.points) - 1)]
        if point.expected_arrival_time is None or end.expected_arrival_time is None:
            raise RouteAnchorError("Anchor segment timing is missing")
        time = (
            point.expected_arrival_time
            + (end.expected_arrival_time - point.expected_arrival_time)
            * anchor.fraction
            - _baseline_delta(route)
        )
        if abs((time - anchor.source_time).total_seconds()) > 0.001:
            raise RouteAnchorError("Anchor source time disagrees with its occurrence")
    expected = _anchor(
        route,
        anchor.segment_index,
        anchor.fraction,
        anchor.source_time + _baseline_delta(route),
        anchor.occurrence_id,
    )
    if (
        haversine_distance(
            expected.latitude, expected.longitude, anchor.latitude, anchor.longitude
        )
        > 1
    ):
        raise RouteAnchorError("Anchor position disagrees with its route occurrence")
    baseline = route.source_departure_time or (
        route.timing_profile.departure_time if route.timing_profile else None
    )
    if baseline is None:
        raise RouteAnchorError("Route departure baseline is missing")
    departure = (
        utc_timestamp(adjustment) if adjustment else baseline + _baseline_delta(route)
    )
    if anchor.timing_mode == "fixed_utc":
        return anchor.source_time
    if anchor.timing_mode == "elapsed":
        return departure + timedelta(seconds=anchor.elapsed_seconds)
    return anchor.source_time + (departure - baseline)
