"""Pure, immutable Manual AR route-splice estimation.

The source KML route is never modified.  This module builds an ephemeral route
basis used by preview/timeline callers and keeps every calculated point marked
with its provenance.
"""

# FR-004: This cohesive pure geometry/timing contract is intentionally kept in
# one module so anchor selection and diversion timing cannot drift apart.

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import asin, atan2, cos, degrees, isfinite, radians, sin, sqrt

from app.mission.models import ManualAARTrack, ManualRouteSplice
from app.models.route import ParsedRoute, RoutePoint

EARTH_RADIUS_NM = 3440.065
MAX_ANCHOR_CONNECTOR_NM = 100.0
MIN_PROGRESS_SEPARATION_NM = 0.01
MAX_CANDIDATES = 8
AR_DIVERSION_ASSUMED_SPEED_KTAS = 400.0


@dataclass(frozen=True)
class DerivedRoutePoint:
    latitude: float
    longitude: float
    altitude: float | None
    provenance: str
    source_index: int | None = None


@dataclass(frozen=True)
class SpliceAnchor:
    segment_index: int
    fraction: float
    progress_nm: float
    latitude: float
    longitude: float
    connector_nm: float


@dataclass
class DerivedRouteEstimate:
    available: bool
    estimated: bool = True
    unavailable_reason: str | None = None
    points: list[DerivedRoutePoint] = field(default_factory=list)
    leave_anchor: SpliceAnchor | None = None
    rejoin_anchor: SpliceAnchor | None = None
    planned_distance_nm: float = 0.0
    derived_distance_nm: float = 0.0
    planned_duration_seconds: float = 0.0
    derived_duration_seconds: float = 0.0
    delta_seconds: float = 0.0
    speed_knots: float | None = None
    speed_source: str | None = None
    confidence: str = "unavailable"
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        """Return an API-safe, explicitly estimated representation."""
        return {
            "available": self.available,
            "estimated": self.estimated,
            "unavailable_reason": self.unavailable_reason,
            "planned_distance_nm": self.planned_distance_nm,
            "derived_distance_nm": self.derived_distance_nm,
            "planned_duration_seconds": self.planned_duration_seconds,
            "derived_duration_seconds": self.derived_duration_seconds,
            "delta_seconds": self.delta_seconds,
            "speed_knots": self.speed_knots,
            "speed_source": self.speed_source,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "leave_anchor": _anchor_dict(self.leave_anchor),
            "rejoin_anchor": _anchor_dict(self.rejoin_anchor),
            "points": [point.__dict__ for point in self.points],
        }


def _anchor_dict(anchor: SpliceAnchor | None) -> dict | None:
    return anchor.__dict__ if anchor else None


def _wrapped_delta_longitude(left: float, right: float) -> float:
    return (right - left + 540.0) % 360.0 - 180.0


def _normalise_longitude(value: float) -> float:
    return (value + 540.0) % 360.0 - 180.0


def distance_nm(left: tuple[float, float], right: tuple[float, float]) -> float:
    """Great-circle distance, including across the antimeridian."""
    lat1, lon1, lat2, lon2 = map(radians, (*left, *right))
    dlat = lat2 - lat1
    dlon = radians(_wrapped_delta_longitude(degrees(lon1), degrees(lon2)))
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_NM * asin(min(1.0, sqrt(value)))


def _interpolate(
    left: RoutePoint, right: RoutePoint, fraction: float
) -> tuple[float, float, float | None]:
    longitude = _normalise_longitude(
        left.longitude
        + _wrapped_delta_longitude(left.longitude, right.longitude) * fraction
    )
    altitude = None
    if left.altitude is not None and right.altitude is not None:
        altitude = left.altitude + (right.altitude - left.altitude) * fraction
    return (
        left.latitude + (right.latitude - left.latitude) * fraction,
        longitude,
        altitude,
    )


def _project_to_segment(
    point: tuple[float, float], start: RoutePoint, end: RoutePoint
) -> tuple[float, float, float, float | None]:
    """Project in a local unwrapped tangent plane; valid for route segments."""
    reference_latitude = radians((start.latitude + end.latitude + point[0]) / 3)
    x_end = radians(_wrapped_delta_longitude(start.longitude, end.longitude)) * cos(
        reference_latitude
    )
    y_end = radians(end.latitude - start.latitude)
    x_point = radians(_wrapped_delta_longitude(start.longitude, point[1])) * cos(
        reference_latitude
    )
    y_point = radians(point[0] - start.latitude)
    denominator = x_end * x_end + y_end * y_end
    if denominator <= 1e-18:
        return 0.0, start.latitude, start.longitude, start.altitude
    fraction = max(0.0, min(1.0, (x_point * x_end + y_point * y_end) / denominator))
    return (fraction, *_interpolate(start, end, fraction))


def _candidate_anchors(
    route: ParsedRoute, point: tuple[float, float]
) -> list[SpliceAnchor]:
    cumulative = 0.0
    anchors: list[SpliceAnchor] = []
    for index, (start, end) in enumerate(zip(route.points, route.points[1:])):
        segment_nm = distance_nm(
            (start.latitude, start.longitude), (end.latitude, end.longitude)
        )
        if segment_nm <= 1e-9:
            continue
        fraction, latitude, longitude, _ = _project_to_segment(point, start, end)
        connector = distance_nm(point, (latitude, longitude))
        if connector <= MAX_ANCHOR_CONNECTOR_NM:
            anchors.append(
                SpliceAnchor(
                    index,
                    fraction,
                    cumulative + segment_nm * fraction,
                    latitude,
                    longitude,
                    connector,
                )
            )
        cumulative += segment_nm
    return sorted(
        anchors, key=lambda item: (item.connector_nm, item.segment_index, item.fraction)
    )[:MAX_CANDIDATES]


def _route_distance(points: list[DerivedRoutePoint]) -> float:
    return sum(
        distance_nm((left.latitude, left.longitude), (right.latitude, right.longitude))
        for left, right in itertools.pairwise(points)
    )


def _segment_lengths(route: ParsedRoute) -> list[float]:
    return [
        distance_nm((start.latitude, start.longitude), (end.latitude, end.longitude))
        for start, end in zip(route.points, route.points[1:])
    ]


def _weighted_median(values: list[tuple[float, float]]) -> float | None:
    valid = sorted(
        (value, weight)
        for value, weight in values
        if isfinite(value) and value > 0 and isfinite(weight) and weight > 0
    )
    if not valid:
        return None
    midpoint = sum(weight for _, weight in valid) / 2
    running = 0.0
    for value, weight in valid:
        running += weight
        if running >= midpoint:
            return value
    return valid[-1][0]


def _speed(
    route: ParsedRoute, leave_progress: float, rejoin_progress: float
) -> tuple[float, str]:
    lengths = _segment_lengths(route)
    total = sum(lengths)
    local_limit = total * 0.1
    cumulative = 0.0
    local: list[tuple[float, float]] = []
    global_values: list[tuple[float, float]] = []
    for index, length in enumerate(lengths):
        cumulative += length
        speed = route.points[index + 1].expected_segment_speed_knots
        if speed is None or not isfinite(speed) or speed <= 0 or length <= 0:
            continue
        global_values.append((speed, length))
        if (
            abs(cumulative - leave_progress) <= local_limit
            or abs(cumulative - rejoin_progress) <= local_limit
        ):
            local.append((speed, length))
    local_speed = _weighted_median(local)
    if local_speed is not None:
        return local_speed, "local_weighted_median"
    global_speed = _weighted_median(global_values)
    if global_speed is not None:
        return global_speed, "global_weighted_median"
    profile = route.timing_profile
    duration = profile.get_total_duration() if profile else None
    if duration is not None and duration > 0:
        total = sum(
            distance_nm(
                (left.latitude, left.longitude), (right.latitude, right.longitude)
            )
            for left, right in zip(route.points, route.points[1:])
        )
        if total > 0:
            return total / (duration / 3600.0), "planned_total_distance_duration"
    return AR_DIVERSION_ASSUMED_SPEED_KTAS, "assumed_400_ktas"


def _local_speed(route: ParsedRoute, progress: float) -> float | None:
    lengths = _segment_lengths(route)
    limit = sum(lengths) * 0.1
    cumulative = 0.0
    values: list[tuple[float, float]] = []
    for index, length in enumerate(lengths):
        cumulative += length
        speed = route.points[index + 1].expected_segment_speed_knots
        if speed is not None and abs(cumulative - progress) <= limit:
            values.append((speed, length))
    return _weighted_median(values)


def _bearing(left: tuple[float, float], right: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*left, *right))
    delta_lon = radians(_wrapped_delta_longitude(degrees(lon1), degrees(lon2)))
    return (
        degrees(
            atan2(
                sin(delta_lon) * cos(lat2),
                cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon),
            )
        )
        + 360
    ) % 360


def _turn_angle(
    first: tuple[float, float], vertex: tuple[float, float], last: tuple[float, float]
) -> float:
    return abs((_bearing(first, vertex) - _bearing(vertex, last) + 180) % 360 - 180)


def _anchor_timestamp(route: ParsedRoute, anchor: SpliceAnchor) -> datetime | None:
    left, right = route.points[anchor.segment_index : anchor.segment_index + 2]
    if (
        not left.expected_arrival_time
        or not right.expected_arrival_time
        or right.expected_arrival_time <= left.expected_arrival_time
    ):
        return None
    return (
        left.expected_arrival_time
        + (right.expected_arrival_time - left.expected_arrival_time) * anchor.fraction
    )


def derived_route_for_estimate(
    source_route: ParsedRoute, estimate: DerivedRouteEstimate
) -> ParsedRoute:
    """Return an ephemeral, time-adjusted route basis for a feasible estimate.

    The cached parsed KML is never modified. Upstream source timestamps remain
    unchanged, the diversion is timed with the selected effective speed, and
    downstream source points receive exactly one splice delta.
    """
    if (
        not estimate.available
        or not estimate.leave_anchor
        or not estimate.rejoin_anchor
    ):
        return source_route

    leave_time = _anchor_timestamp(source_route, estimate.leave_anchor)
    if leave_time is None:
        return source_route

    diversion_indices = [
        index
        for index, point in enumerate(estimate.points)
        if point.provenance != "planned" or point.source_index is None
    ]
    if not diversion_indices:
        return source_route
    first_diversion, last_diversion = diversion_indices[0], diversion_indices[-1]
    diversion_distance = max(
        _route_distance(estimate.points[first_diversion : last_diversion + 1]), 1e-9
    )
    elapsed = 0.0
    rebuilt_points: list[RoutePoint] = []
    for sequence, point in enumerate(estimate.points):
        if first_diversion < sequence <= last_diversion:
            prior = estimate.points[sequence - 1]
            elapsed += (
                distance_nm(
                    (prior.latitude, prior.longitude), (point.latitude, point.longitude)
                )
                / diversion_distance
                * estimate.derived_duration_seconds
            )
        timestamp: datetime | None = None
        if point.provenance == "planned" and point.source_index is not None:
            timestamp = source_route.points[point.source_index].expected_arrival_time
            if timestamp and point.source_index > estimate.rejoin_anchor.segment_index:
                timestamp += timedelta(seconds=estimate.delta_seconds)
        elif sequence == first_diversion:
            timestamp = leave_time
        else:
            timestamp = leave_time + timedelta(seconds=elapsed)
        rebuilt_points.append(
            RoutePoint(
                latitude=point.latitude,
                longitude=point.longitude,
                altitude=point.altitude,
                sequence=sequence,
                expected_arrival_time=timestamp,
                expected_segment_speed_knots=estimate.speed_knots,
            )
        )

    derived = source_route.model_copy(deep=True)
    derived.points = rebuilt_points
    derived.metadata.point_count = len(rebuilt_points)
    if derived.timing_profile and derived.timing_profile.arrival_time:
        derived.timing_profile.arrival_time += timedelta(seconds=estimate.delta_seconds)
    return derived


def _override_anchor(
    route: ParsedRoute,
    point: tuple[float, float],
    segment_index: int | None,
    fraction: float | None,
) -> SpliceAnchor | None:
    if (
        segment_index is None
        or fraction is None
        or segment_index >= len(route.points) - 1
    ):
        return None
    start, end = route.points[segment_index : segment_index + 2]
    segment_nm = distance_nm(
        (start.latitude, start.longitude), (end.latitude, end.longitude)
    )
    if segment_nm <= 1e-9:
        return None
    latitude, longitude, _ = _interpolate(start, end, fraction)
    progress = sum(_segment_lengths(route)[:segment_index]) + segment_nm * fraction
    connector = distance_nm(point, (latitude, longitude))
    if connector > MAX_ANCHOR_CONNECTOR_NM:
        return None
    return SpliceAnchor(
        segment_index, fraction, progress, latitude, longitude, connector
    )


def _splice_points(
    route: ParsedRoute, track: ManualAARTrack, leave: SpliceAnchor, rejoin: SpliceAnchor
) -> list[DerivedRoutePoint]:
    return [
        *[
            DerivedRoutePoint(
                point.latitude, point.longitude, point.altitude, "planned", index
            )
            for index, point in enumerate(route.points[: leave.segment_index + 1])
        ],
        DerivedRoutePoint(leave.latitude, leave.longitude, None, "entry_connector"),
        *[
            DerivedRoutePoint(point.latitude, point.longitude, None, "manual_track")
            for point in track.points
        ],
        DerivedRoutePoint(rejoin.latitude, rejoin.longitude, None, "exit_connector"),
        *[
            DerivedRoutePoint(
                point.latitude, point.longitude, point.altitude, "planned", index
            )
            for index, point in enumerate(
                route.points[rejoin.segment_index + 1 :], start=rejoin.segment_index + 1
            )
        ],
    ]


def _diversion_distance(points: list[DerivedRoutePoint]) -> float:
    start = next(
        index
        for index, point in enumerate(points)
        if point.provenance == "entry_connector"
    )
    end = next(
        index
        for index, point in enumerate(points)
        if point.provenance == "exit_connector"
    )
    return _route_distance(points[start : end + 1])


def build_derived_route_estimate(
    route: ParsedRoute, track: ManualAARTrack, override: ManualRouteSplice | None = None
) -> DerivedRouteEstimate:
    """Build one deterministic, source-immutable splice estimate.

    An explicit anchor override is accepted only when it satisfies the same
    connector and forward-progress constraints as inferred anchors.
    """
    if len(route.points) < 2:
        return DerivedRouteEstimate(False, unavailable_reason="source_route_too_short")
    entry_point = (track.points[0].latitude, track.points[0].longitude)
    exit_point = (track.points[-1].latitude, track.points[-1].longitude)
    if override and any(
        value is not None
        for value in (
            override.leave_segment_index,
            override.leave_fraction,
            override.rejoin_segment_index,
            override.rejoin_fraction,
        )
    ):
        leave = _override_anchor(
            route, entry_point, override.leave_segment_index, override.leave_fraction
        )
        rejoin = _override_anchor(
            route, exit_point, override.rejoin_segment_index, override.rejoin_fraction
        )
        pairs = [(leave, rejoin)] if leave and rejoin else []
        invalid_override = not pairs
    else:
        entries = _candidate_anchors(route, entry_point)
        exits = _candidate_anchors(route, exit_point)
        pairs = [(entry, exit_anchor) for entry in entries for exit_anchor in exits]
        invalid_override = False
    pairs = [
        (leave, rejoin)
        for leave, rejoin in pairs
        if leave.progress_nm + MIN_PROGRESS_SEPARATION_NM < rejoin.progress_nm
    ]
    if not pairs:
        return DerivedRouteEstimate(
            False,
            unavailable_reason=(
                "invalid_splice_override" if invalid_override else "no_feasible_splice"
            ),
        )

    planned_total = route.get_total_distance() / 1852.0
    scored: list[
        tuple[
            float,
            SpliceAnchor,
            SpliceAnchor,
            list[DerivedRoutePoint],
            float,
            float,
            str,
        ]
    ] = []
    for leave, rejoin in pairs:
        speed, source = _speed(route, leave.progress_nm, rejoin.progress_nm)
        points = _splice_points(route, track, leave, rejoin)
        diversion = _diversion_distance(points)
        replaced = rejoin.progress_nm - leave.progress_nm
        inbound = route.points[leave.segment_index]
        outbound = route.points[rejoin.segment_index + 1]
        entry_turn = _turn_angle(
            (inbound.latitude, inbound.longitude),
            (leave.latitude, leave.longitude),
            entry_point,
        )
        exit_turn = _turn_angle(
            exit_point,
            (rejoin.latitude, rejoin.longitude),
            (outbound.latitude, outbound.longitude),
        )
        delay = (diversion - replaced) / speed * 3600
        leave_speed = _local_speed(route, leave.progress_nm)
        rejoin_speed = _local_speed(route, rejoin.progress_nm)
        speed_disagreement = (
            min(abs(leave_speed - rejoin_speed) / max(leave_speed, rejoin_speed), 1.0)
            if leave_speed is not None and rejoin_speed is not None
            else 1.0
        )
        score = (
            0.35 * (leave.connector_nm + rejoin.connector_nm) / 100
            + 0.35 * max(0.0, diversion - replaced) / 100
            + 0.15 * (entry_turn + exit_turn) / 360
            + 0.10 * min(abs(delay) / 1800, 1.0)
            + 0.05 * speed_disagreement
        )
        scored.append((score, leave, rejoin, points, diversion, speed, source))
    scored.sort(
        key=lambda candidate: (
            candidate[0],
            candidate[1].connector_nm + candidate[2].connector_nm,
            candidate[1].segment_index,
            candidate[1].fraction,
            candidate[2].segment_index,
            candidate[2].fraction,
        )
    )
    _, leave, rejoin, points, diversion, inferred_speed, speed_source = scored[0]
    speed = (
        override.speed_knots if override and override.speed_knots else inferred_speed
    )
    leave_time, rejoin_time = _anchor_timestamp(route, leave), _anchor_timestamp(
        route, rejoin
    )
    replaced = rejoin.progress_nm - leave.progress_nm
    planned_duration = (
        (rejoin_time - leave_time).total_seconds()
        if leave_time and rejoin_time
        else replaced / speed * 3600
    )
    derived_duration = diversion / speed * 3600
    confidence = (
        "high" if len(scored) == 1 or scored[1][0] - scored[0][0] > 0.05 else "low"
    )
    warnings = (
        []
        if confidence == "high"
        else ["Multiple feasible splice anchors have similar scores."]
    )
    if leave_time is None or rejoin_time is None:
        warnings.append(
            "Replaced planned duration uses distance/speed because source timestamps are not monotonic."
        )
    if override and override.speed_knots:
        speed_source = "operator_override"
    return DerivedRouteEstimate(
        True,
        points=points,
        leave_anchor=leave,
        rejoin_anchor=rejoin,
        planned_distance_nm=planned_total,
        derived_distance_nm=_route_distance(points),
        planned_duration_seconds=planned_duration,
        derived_duration_seconds=derived_duration,
        delta_seconds=derived_duration - planned_duration,
        speed_knots=speed,
        speed_source=speed_source,
        confidence=confidence,
        warnings=warnings,
    )
