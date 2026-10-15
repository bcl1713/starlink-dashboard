"""Retain a route-bound occurrence only when independent geometry identifies it."""

from app.mission.planning.match import _anchor
from app.services.kml.geometry import haversine_distance


def rebind(anchor, old, new):
    if anchor is None:
        return None
    matches = [
        (i, p)
        for i, p in enumerate(new.points)
        if p.expected_arrival_time is not None
        and haversine_distance(
            anchor.latitude, anchor.longitude, p.latitude, p.longitude
        )
        <= 1
    ]
    if len(matches) != 1:
        raise ValueError(
            "Route replacement needs review: an AR or handover occurrence cannot be uniquely remapped"
        )
    i, p = matches[0]
    result = _anchor(new, i, 0, p.expected_arrival_time, p.occurrence_id)
    if anchor.timing_mode != "route_bound":
        result = result.model_copy(
            update={
                "timing_mode": anchor.timing_mode,
                "source_time": anchor.source_time,
                "elapsed_seconds": anchor.elapsed_seconds,
            }
        )
    return result


def rebind_leg(leg, old, new):
    for window in leg.transports.aar_windows:
        window.start_anchor = rebind(window.start_anchor, old, new)
        window.end_anchor = rebind(window.end_anchor, old, new)
    for swap in leg.transports.x_transitions:
        swap.anchor = rebind(swap.anchor, old, new)
        if swap.anchor:
            swap.latitude = swap.anchor.latitude
            swap.longitude = swap.anchor.longitude
