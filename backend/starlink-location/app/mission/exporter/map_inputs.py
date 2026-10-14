"""Pure timed scene inputs, selectively retained from committed #309."""

import json
import math
from dataclasses import dataclass
from datetime import datetime
from itertools import pairwise

from .briefing_clocks import ensure_utc
from .customer_projection import BriefingLeg
from .snapshot import LegSnapshot


def _utc(raw: str | datetime) -> datetime:
    if not isinstance(raw, (str, datetime)):
        raise TypeError("Route timing unavailable")
    return ensure_utc(
        datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if isinstance(raw, str)
        else raw
    )


def _stamp(value: datetime) -> str:
    return _utc(value).isoformat().replace("+00:00", "Z")


def _interpolate(a: dict, b: dict, ratio: float) -> tuple[float, float]:
    """Spherical interpolation follows the scene's shortest great-circle arc."""

    def vector(point):
        lat, lon = math.radians(point["latitude"]), math.radians(point["longitude"])
        return (
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        )

    av, bv = vector(a), vector(b)
    angle = math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(av, bv)))))
    if angle > math.pi - 1e-6:
        raise ValueError("Antipodal route segment has ambiguous geometry")
    if angle < 1e-8:
        return a["latitude"], a["longitude"]
    left, right = math.sin((1 - ratio) * angle), math.sin(ratio * angle)
    x, y, z = (left * x + right * y for x, y in zip(av, bv))
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


@dataclass(frozen=True)
class MapInputDiagnostic:
    code: str
    message: str
    window_id: str | None = None
    severity: str = "error"


@dataclass(frozen=True)
class MapInputResult:
    scene: dict | None
    diagnostics: tuple[MapInputDiagnostic, ...]


class _Rejected(ValueError):
    def __init__(self, code, message, window_id=None):
        super().__init__(message)
        self.diagnostic = MapInputDiagnostic(code, message, window_id)


def prepare_map_input(
    snapshot_leg: LegSnapshot, projected_leg: BriefingLeg, *, include_markers=True
) -> MapInputResult:
    """Preserve canonical anchors; capacity applies to the requested display."""
    if snapshot_leg.leg_id != projected_leg.leg_id:
        raise ValueError("Projection and captured leg identities differ")
    notes = []
    try:
        if not snapshot_leg.effective_route_json:
            raise _Rejected(
                "route_missing",
                "Captured effective route is unavailable; review the route binding",
            )
        try:
            captured_points = json.loads(snapshot_leg.effective_route_json)["points"]
        except (ValueError, KeyError, TypeError) as exc:
            raise _Rejected(
                "route_missing",
                "Captured route points are unavailable; review the route binding",
            ) from exc
        if len(captured_points) < 2:
            raise _Rejected(
                "route_missing", "A customer map requires at least two route points"
            )
        if len(captured_points) > 2000:
            raise _Rejected(
                "route_point_limit",
                "Customer map exceeds the 2000 route point limit; review the route sampling",
            )
        try:
            start, end = map(_utc, projected_leg.utc_bounds)
        except (ValueError, TypeError) as exc:
            raise _Rejected(
                "route_bounds_mismatch",
                "Flight timing is unavailable; review departure and arrival bounds",
            ) from exc
        timed, times, points = {}, [], []
        coincident = 0
        for point in captured_points:
            try:
                stamp = _utc(point["expected_arrival_time"])
            except (ValueError, KeyError, TypeError) as exc:
                raise _Rejected(
                    "route_timing_missing",
                    "Route point timing is missing or invalid; review the timed source route",
                ) from exc
            try:
                lat, lon = float(point["latitude"]), float(point["longitude"])
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError()
            except (ValueError, KeyError, TypeError) as exc:
                raise _Rejected(
                    "route_coordinates_invalid",
                    "Route coordinates are invalid; review the source route",
                ) from exc
            if times and stamp <= times[-1]:
                prior = timed[times[-1]]
                if stamp == times[-1] and (lat, lon) == (
                    prior["latitude"],
                    prior["longitude"],
                ):
                    coincident += 1
                    continue
                raise _Rejected(
                    "route_timing_non_increasing",
                    "Route times must increase; review conflicting or backward occurrences",
                )
            position = {"latitude": lat, "longitude": lon, "timestamp": _stamp(stamp)}
            points.append(position)
            times.append(stamp)
            timed[stamp] = position
        if len(times) < 2 or (times[0], times[-1]) != (start, end):
            raise _Rejected(
                "route_bounds_mismatch",
                "Route timing does not match flight bounds; review the departure and arrival times",
            )
        for a, b in pairwise(points):
            try:
                _interpolate(a, b, 0.5)
            except ValueError as exc:
                raise _Rejected(
                    "route_antipodal_segment",
                    "An antipodal route segment has ambiguous geometry; review the source route",
                ) from exc
        if coincident:
            notes.append(
                MapInputDiagnostic(
                    "route_coincident_join",
                    f"{coincident} coincident timed route joins represented as one map position",
                    severity="info",
                )
            )
        markers = []
        for interval in projected_leg.coordination_rows:
            try:
                stamp = _utc(interval.start_time)
            except (ValueError, TypeError) as exc:
                raise _Rejected(
                    "window_position_unavailable",
                    "A briefing window has invalid timing; review its source boundary",
                    interval.id,
                ) from exc
            if not start <= stamp <= end:
                raise _Rejected(
                    "window_position_unavailable",
                    f"Window {interval.window_number} is outside the effective route bounds; review its source boundary",
                    interval.id,
                )
            if stamp not in timed:
                index = next(i for i, endpoint in enumerate(times) if endpoint > stamp)
                ratio = (stamp - times[index - 1]) / (times[index] - times[index - 1])
                lat, lon = _interpolate(points[index - 1], points[index], ratio)
                timed[stamp] = {
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": _stamp(stamp),
                }
            if include_markers:
                markers.append((interval.id, str(interval.window_number), stamp))
        if len(markers) > 200:
            raise _Rejected(
                "route_marker_limit",
                "Requested window markers exceed the 200 marker limit; use the customer route overview",
            )
        if len(timed) > 2000:
            raise _Rejected(
                "route_point_limit",
                "Route and exact window anchors exceed the 2000 point limit; review route sampling",
            )
        ordered = sorted(timed)
        indices = {stamp: index for index, stamp in enumerate(ordered)}
        return MapInputResult(
            {
                "schemaVersion": 1,
                "framingVersion": "mission-map-v1",
                "legId": projected_leg.leg_id,
                "referenceUtc": _stamp(start),
                "route": [timed[t] for t in ordered],
                "markers": [
                    {"id": identity, "label": label, "routeIndex": indices[t]}
                    for identity, label, t in markers
                ],
            },
            tuple(notes),
        )
    except _Rejected as exc:
        return MapInputResult(None, (exc.diagnostic, *notes))


def build_map_input(
    snapshot_leg: LegSnapshot, projected_leg: BriefingLeg, *, include_markers=True
) -> tuple[dict | None, tuple[str, ...]]:
    """Compatibility adapter; structured diagnoses are available to review."""
    result = prepare_map_input(
        snapshot_leg, projected_leg, include_markers=include_markers
    )
    return result.scene, tuple(item.message for item in result.diagnostics)
