"""Pure timed scene inputs, selectively retained from committed #309."""

import json
import math
from datetime import datetime

from .snapshot import LegSnapshot
from .trial_clocks import ensure_utc
from .trial_projection import TrialLeg


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


def build_map_input(
    snapshot_leg: LegSnapshot, trial_leg: TrialLeg
) -> tuple[dict | None, tuple[str, ...]]:
    """Insert exact window starts into the effective timed route; never renumber."""
    if snapshot_leg.leg_id != trial_leg.leg_id:
        raise ValueError("Projection and captured leg identities differ")
    if not snapshot_leg.effective_route_json:
        return None, ("Captured effective route is unavailable",)
    try:
        points = json.loads(snapshot_leg.effective_route_json)["points"]
        if len(points) < 2 or len(points) > 2000 or not trial_leg.utc_bounds:
            raise ValueError("Effective route timing/bounds unavailable")
        timed = {}
        times = []
        for point in points:
            stamp = _utc(point["expected_arrival_time"])
            if times and stamp <= times[-1]:
                raise ValueError("Effective route timing must increase")
            lat, lon = float(point["latitude"]), float(point["longitude"])
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                raise ValueError("Effective route coordinates invalid")
            times.append(stamp)
            timed[stamp] = {
                "latitude": lat,
                "longitude": lon,
                "timestamp": _stamp(stamp),
            }
        if (times[0], times[-1]) != trial_leg.utc_bounds:
            raise ValueError("Effective route timing does not match flight bounds")
        notes = []
        markers = []
        for interval in trial_leg.coordination_rows:
            stamp = interval.start_time
            if stamp < times[0] or stamp > times[-1]:
                notes.append(
                    f"Window {interval.window_number}: route position unavailable"
                )
                continue
            if stamp not in timed:
                index = next(i for i, end in enumerate(times) if end > stamp)
                a, b = points[index - 1], points[index]
                ratio = (stamp - times[index - 1]) / (times[index] - times[index - 1])
                lat, lon = _interpolate(a, b, ratio)
                timed[stamp] = {
                    "latitude": lat,
                    "longitude": lon,
                    "timestamp": _stamp(stamp),
                }
            markers.append((interval.id, str(interval.window_number), stamp))
        if len(markers) > 200 or len(timed) > 2000:
            raise ValueError("Route/marker density exceeds renderer capacity")
        ordered = sorted(timed)
        indices = {stamp: index for index, stamp in enumerate(ordered)}
        return {
            "schemaVersion": 1,
            "framingVersion": "mission-map-v1",
            "legId": trial_leg.leg_id,
            "referenceUtc": _stamp(times[0]),
            "route": [timed[t] for t in ordered],
            "markers": [
                {"id": identity, "label": label, "routeIndex": indices[t]}
                for identity, label, t in markers
            ],
        }, tuple(notes)
    except (ValueError, KeyError, TypeError, StopIteration):
        return None, ("Effective route geometry or timing cannot locate trial windows",)
