"""Pure, immutable Manual AR route-splice estimation.

The source KML route is never modified.  This module builds an ephemeral route
basis used by preview/timeline callers and keeps every calculated point marked
with its provenance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from math import asin, atan2, cos, degrees, radians, sin, sqrt
from statistics import median

from app.mission.models import ManualAARTrack
from app.models.route import ParsedRoute, RoutePoint

EARTH_RADIUS_NM = 3440.065
MAX_ANCHOR_CONNECTOR_NM = 100.0
MIN_PROGRESS_SEPARATION_NM = 0.01
MAX_CANDIDATES = 8


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


def _interpolate(left: RoutePoint, right: RoutePoint, fraction: float) -> tuple[float, float, float | None]:
    longitude = _normalise_longitude(
        left.longitude + _wrapped_delta_longitude(left.longitude, right.longitude) * fraction
    )
    altitude = None
    if left.altitude is not None and right.altitude is not None:
        altitude = left.altitude + (right.altitude - left.altitude) * fraction
    return (left.latitude + (right.latitude - left.latitude) * fraction, longitude, altitude)


def _project_to_segment(point: tuple[float, float], start: RoutePoint, end: RoutePoint) -> tuple[float, float, float, float | None]:
    """Project in a local unwrapped tangent plane; valid for route segments."""
    reference_latitude = radians((start.latitude + end.latitude + point[0]) / 3)
    x_end = radians(_wrapped_delta_longitude(start.longitude, end.longitude)) * cos(reference_latitude)
    y_end = radians(end.latitude - start.latitude)
    x_point = radians(_wrapped_delta_longitude(start.longitude, point[1])) * cos(reference_latitude)
    y_point = radians(point[0] - start.latitude)
    denominator = x_end * x_end + y_end * y_end
    if denominator <= 1e-18:
        return 0.0, start.latitude, start.longitude, start.altitude
    fraction = max(0.0, min(1.0, (x_point * x_end + y_point * y_end) / denominator))
    return (fraction, *_interpolate(start, end, fraction))


def _candidate_anchors(route: ParsedRoute, point: tuple[float, float]) -> list[SpliceAnchor]:
    cumulative = 0.0
    anchors: list[SpliceAnchor] = []
    for index, (start, end) in enumerate(zip(route.points, route.points[1:])):
        segment_nm = distance_nm((start.latitude, start.longitude), (end.latitude, end.longitude))
        if segment_nm <= 1e-9:
            continue
        fraction, latitude, longitude, _ = _project_to_segment(point, start, end)
        connector = distance_nm(point, (latitude, longitude))
        if connector <= MAX_ANCHOR_CONNECTOR_NM:
            anchors.append(SpliceAnchor(index, fraction, cumulative + segment_nm * fraction, latitude, longitude, connector))
        cumulative += segment_nm
    return sorted(anchors, key=lambda item: (item.connector_nm, item.segment_index, item.fraction))[:MAX_CANDIDATES]


def _route_distance(points: list[DerivedRoutePoint]) -> float:
    return sum(distance_nm((left.latitude, left.longitude), (right.latitude, right.longitude)) for left, right in zip(points, points[1:]))


def _speed(route: ParsedRoute) -> tuple[float, str]:
    valid = [point.expected_segment_speed_knots for point in route.points if point.expected_segment_speed_knots and point.expected_segment_speed_knots > 0]
    if valid:
        return float(median(valid)), "global_weighted_median"
    profile = route.timing_profile
    duration = profile.get_total_duration() if profile else None
    if duration is not None and duration > 0:
        total = sum(distance_nm((left.latitude, left.longitude), (right.latitude, right.longitude)) for left, right in zip(route.points, route.points[1:]))
        if total > 0:
            return total / (duration / 3600.0), "planned_total_distance_duration"
    return 500.0, "fallback_500kt"


def _anchor_timestamp(route: ParsedRoute, anchor: SpliceAnchor) -> datetime | None:
    left, right = route.points[anchor.segment_index : anchor.segment_index + 2]
    if not left.expected_arrival_time or not right.expected_arrival_time or right.expected_arrival_time <= left.expected_arrival_time:
        return None
    return left.expected_arrival_time + (right.expected_arrival_time - left.expected_arrival_time) * anchor.fraction


def derived_route_for_estimate(
    source_route: ParsedRoute, estimate: DerivedRouteEstimate
) -> ParsedRoute:
    """Return an ephemeral, time-adjusted route basis for a feasible estimate.

    The cached parsed KML is never modified. Upstream source timestamps remain
    unchanged, the diversion is timed with the selected effective speed, and
    downstream source points receive exactly one splice delta.
    """
    if not estimate.available or not estimate.leave_anchor or not estimate.rejoin_anchor:
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
            elapsed += distance_nm(
                (prior.latitude, prior.longitude), (point.latitude, point.longitude)
            ) / diversion_distance * estimate.derived_duration_seconds
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


def build_derived_route_estimate(route: ParsedRoute, track: ManualAARTrack) -> DerivedRouteEstimate:
    """Build one selected track splice or an explicit planned-route fallback."""
    if len(route.points) < 2:
        return DerivedRouteEstimate(False, unavailable_reason="source_route_too_short")
    entry_candidates = _candidate_anchors(route, (track.points[0].latitude, track.points[0].longitude))
    exit_candidates = _candidate_anchors(route, (track.points[-1].latitude, track.points[-1].longitude))
    pairs = [(entry, exit_anchor) for entry in entry_candidates for exit_anchor in exit_candidates if entry.progress_nm + MIN_PROGRESS_SEPARATION_NM < exit_anchor.progress_nm]
    if not pairs:
        return DerivedRouteEstimate(False, unavailable_reason="no_feasible_splice")

    speed_knots, speed_source = _speed(route)
    manual_points = [DerivedRoutePoint(point.latitude, point.longitude, None, "manual_track") for point in track.points]
    scored: list[tuple[float, SpliceAnchor, SpliceAnchor, list[DerivedRoutePoint]]] = []
    for leave, rejoin in pairs:
        points = [
            *[DerivedRoutePoint(point.latitude, point.longitude, point.altitude, "planned", index) for index, point in enumerate(route.points[: leave.segment_index + 1])],
            DerivedRoutePoint(leave.latitude, leave.longitude, None, "entry_connector"),
            *manual_points,
            DerivedRoutePoint(rejoin.latitude, rejoin.longitude, None, "exit_connector"),
            *[DerivedRoutePoint(point.latitude, point.longitude, point.altitude, "planned", index) for index, point in enumerate(route.points[rejoin.segment_index + 1 :], start=rejoin.segment_index + 1)],
        ]
        new_distance = _route_distance(points)
        replaced = rejoin.progress_nm - leave.progress_nm
        score = 0.35 * (leave.connector_nm + rejoin.connector_nm) / 100 + 0.35 * max(0.0, new_distance - (route.get_total_distance() / 1852.0)) / 100
        scored.append((score, leave, rejoin, points))
    scored.sort(key=lambda candidate: (candidate[0], candidate[1].connector_nm + candidate[2].connector_nm, candidate[1].segment_index, candidate[1].fraction, candidate[2].segment_index, candidate[2].fraction))
    _, leave, rejoin, points = scored[0]
    planned_distance = route.get_total_distance() / 1852.0
    derived_distance = _route_distance(points)
    leave_time, rejoin_time = _anchor_timestamp(route, leave), _anchor_timestamp(route, rejoin)
    planned_duration = (rejoin_time - leave_time).total_seconds() if leave_time and rejoin_time else (rejoin.progress_nm - leave.progress_nm) / speed_knots * 3600
    derived_duration = (derived_distance - (planned_distance - (rejoin.progress_nm - leave.progress_nm))) / speed_knots * 3600
    confidence = "high" if len(scored) == 1 or scored[1][0] - scored[0][0] > 0.05 else "low"
    warnings = [] if confidence == "high" else ["Multiple feasible splice anchors have similar scores."]
    if leave_time is None or rejoin_time is None:
        warnings.append("Replaced planned duration uses distance/speed because source timestamps are not monotonic.")
    return DerivedRouteEstimate(True, points=points, leave_anchor=leave, rejoin_anchor=rejoin, planned_distance_nm=planned_distance, derived_distance_nm=derived_distance, planned_duration_seconds=planned_duration, derived_duration_seconds=derived_duration, delta_seconds=derived_duration - planned_duration, speed_knots=speed_knots, speed_source=speed_source, confidence=confidence, warnings=warnings)
