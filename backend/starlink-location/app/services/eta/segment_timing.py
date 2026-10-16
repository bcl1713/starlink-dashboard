"""Shared speed rule for POIs and route hazard crossings."""


def segment_speed(measured: float, planned: float | None, first: bool) -> float:
    expected = planned or measured
    return (measured + expected) / 2.0 if first else expected


def has_route_timing(route) -> bool:
    """Timed route points remain usable when optional summary metadata is absent."""
    if route.timing_profile and route.timing_profile.has_timing_data:
        return True
    for start, end in zip(route.points, route.points[1:]):
        a, b = start.expected_arrival_time, end.expected_arrival_time
        if (
            a is not None
            and b is not None
            and a.utcoffset() is not None
            and b.utcoffset() is not None
            and a < b
        ):
            return True
    return False
