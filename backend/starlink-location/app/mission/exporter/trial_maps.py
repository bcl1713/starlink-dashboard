"""Offline, request-owned trial maps; never reads or writes mission storage.

One browser child receives every leg and one monotonic deadline. A separately
bounded, offline neutral renderer supplies static fallbacks. Its result can also
be a text card, so map failure can never produce a blank briefing slide.
"""

from __future__ import annotations

import io
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

import psutil
from PIL import Image, ImageDraw

from .snapshot import ExportSnapshot, LegSnapshot
from .snapshot_inputs import canonical_json
from .trial_clocks import ensure_utc
from .trial_projection import TrialLeg

STATIC_LABEL = "Overview map unavailable — static route fallback"
PRIMARY_LABEL = (
    "Planned-time lighting illustration; numbered windows match the leg table"
)
RUNTIME_ROOT = Path("/opt/mission-map/frontend/mission-planner")


@dataclass(frozen=True)
class MapView:
    id: str
    png: bytes


@dataclass(frozen=True)
class LegMapResult:
    leg_id: str
    views: tuple[MapView, ...]
    label: str
    status: Literal["primary", "static", "unavailable"]
    warnings: tuple[str, ...]
    cache_key: str
    endpoints: tuple[str, str]
    reason: str | None = None
    renderer_evidence_json: bytes | None = None


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


def map_cache_key(
    snapshot: ExportSnapshot, leg: TrialLeg, raw: dict | None, runtime_identity: str
) -> str:
    return sha256(
        canonical_json(
            {
                "snapshot": snapshot.fingerprint,
                "leg": {
                    "id": leg.leg_id,
                    "bounds": leg.utc_bounds,
                    "intervals": [asdict(interval) for interval in leg.intervals],
                    "sources": [source.source_digest for source in leg.sources],
                    "basis": leg.planned_departure_basis,
                },
                "map": raw,
                "runtime": runtime_identity,
                "resolution": [1920, 1080],
                "framing": "mission-map-v1",
                "staticVersion": "neutral-route-v1",
            }
        )
    ).hexdigest()


def _runtime_identity() -> str:
    # Packaged compiled assets and dependency/source versions, without a durable cache.
    return sha256((RUNTIME_ROOT / "runtime-manifest.json").read_bytes()).hexdigest()


def _renderer_command(input_path: Path, output: Path) -> list[str]:
    return [
        "node",
        str(RUNTIME_ROOT / "src/mission-export/render.mjs"),
        str(input_path),
        str(output),
        str(RUNTIME_ROOT / "dist-mission-export"),
    ]


def _run_owned(
    command: list[str], root: Path, deadline: float, env: dict | None = None
) -> bool:
    """Stop and reap owned descendants even when the child/browser hangs."""
    if deadline - time.monotonic() <= 0.5:
        return False
    ownership = {
        "command": command,
        "pid": None,
        "pgid": None,
        "temporaryPaths": [str(root)],
        "compose": None,
        "volumes": [],
    }
    record = root / "python-ownership.json"
    record.write_bytes(canonical_json(ownership))
    child = None
    descendants = []
    handlers = {}

    def interrupted(signum, frame):
        previous = handlers.get(signum)
        if callable(previous):
            previous(signum, frame)
        raise InterruptedError("Map owner terminated")

    if threading.current_thread() is threading.main_thread():
        for signum in (signal.SIGTERM, signal.SIGINT):
            handlers[signum] = signal.signal(signum, interrupted)
    try:
        with (root / "child.log").open("wb") as log:
            child = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                env={
                    **(os.environ if env is None else env),
                    "MISSION_MAP_PARENT_PIPE": "1",
                },
                start_new_session=True,
            )
            ownership.update(pid=child.pid, pgid=child.pid)
            record.write_bytes(canonical_json(ownership))
            try:
                child.wait(timeout=max(0.01, deadline - time.monotonic() - 0.5))
            except subprocess.TimeoutExpired:
                return False
            return child.returncode == 0
    except InterruptedError:
        raise
    except OSError:
        return False
    finally:
        if child and child.poll() is None:
            try:
                descendants = psutil.Process(child.pid).children(recursive=True)
            except psutil.NoSuchProcess:
                pass
            ownership["descendants"] = [
                {"pid": p.pid, "created": p.create_time()} for p in descendants
            ]
            record.write_bytes(canonical_json(ownership))
            for process in descendants:
                try:
                    process.terminate()
                except psutil.NoSuchProcess:
                    pass
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=0.2)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=0.2)
            _, alive = psutil.wait_procs(descendants, timeout=0.1)
            for process in alive:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            psutil.wait_procs(alive, timeout=0.1)
        ownership["reaped"] = child is None or child.poll() is not None
        if child and child.stdin:
            child.stdin.close()
        ownership["finishedMonotonic"] = time.monotonic()
        record.write_bytes(canonical_json(ownership))
        for signum, handler in handlers.items():
            signal.signal(signum, handler)


def _png(path: Path, expected_hash: str | None = None) -> bytes:
    value = path.read_bytes()
    if expected_hash and sha256(value).hexdigest() != expected_hash:
        raise ValueError("PNG digest mismatch")
    with Image.open(io.BytesIO(value)) as image:
        image.load()
        if (
            image.format != "PNG"
            or image.size != (1920, 1080)
            or not any(a != b for a, b in image.convert("RGB").getextrema())
        ):
            raise ValueError("Blank or invalid map PNG")
    return value


def _endpoints(leg: LegSnapshot) -> tuple[str, str]:
    raw = json.loads(leg.leg_json)
    route = json.loads(leg.effective_route_json) if leg.effective_route_json else {}
    points = route.get("points") or []
    return tuple(
        str(
            raw.get(key)
            or (
                f'{points[index]["latitude"]:.2f}, {points[index]["longitude"]:.2f}'
                if points
                else raw.get("name") or leg.leg_id
            )
        )
        for key, index in (("departure_airport", 0), ("arrival_airport", -1))
    )


def _static_filename(leg_id: str) -> str:
    return sha256(leg_id.encode()).hexdigest() + ".png"


def render_trial_maps(
    snapshot: ExportSnapshot, legs: tuple[TrialLeg, ...], budget_seconds: float = 60.0
) -> tuple[LegMapResult, ...]:
    deadline = time.monotonic() + max(0.0, min(float(budget_seconds), 60.0))
    captured = {leg.leg_id: leg for leg in snapshot.legs}
    inputs, notes = {}, {}
    for leg in legs:
        if time.monotonic() >= deadline:
            inputs[leg.leg_id], notes[leg.leg_id] = None, (
                "Shared primary map deadline exhausted",
            )
        else:
            inputs[leg.leg_id], notes[leg.leg_id] = build_map_input(
                captured[leg.leg_id], leg
            )
    try:
        runtime_identity = _runtime_identity()
    except OSError:
        runtime_identity = "renderer-unavailable"
    results = {}
    evidence = None
    with tempfile.TemporaryDirectory(prefix="trial-map-") as directory:
        root = Path(directory)
        valid = [inputs[leg.leg_id] for leg in legs if inputs[leg.leg_id] is not None]
        input_path = root / "input.json"
        input_path.write_bytes(canonical_json({"legs": valid}))
        output = root / "primary"
        output.mkdir()
        if valid and deadline - time.monotonic() > 0.5:
            env = {
                **os.environ,
                "MISSION_MAP_BUDGET_SECONDS": str(
                    max(0.01, deadline - time.monotonic() - 0.7)
                ),
            }
            success = _run_owned(
                _renderer_command(input_path, output), output, deadline, env
            )
            try:
                report = json.loads((output / "result.json").read_bytes())
                evidence = canonical_json(report)
                cleanup = report["cleanup"]
                if (
                    not success
                    or report["status"] != "primary"
                    or cleanup["errors"]
                    or not all(
                        cleanup[key]
                        for key in ("browserExited", "contextsClosed", "listenerClosed")
                    )
                ):
                    raise ValueError("Primary map rendering or cleanup failed")
                if report["inputs"] != valid or report["plannedViewIds"] != [
                    view["id"] for view in report["views"]
                ]:
                    raise ValueError("Primary map inputs or planned views mismatch")
                for leg in legs:
                    if inputs[leg.leg_id] is None:
                        continue
                    raw = inputs[leg.leg_id]
                    views = []
                    labels = set()
                    for view in report["views"]:
                        if not view["id"].startswith(leg.leg_id + "/"):
                            continue
                        readiness = view["readiness"]
                        if (
                            readiness["digest"] != view["inputDigest"]
                            or len(view["inputDigest"]) != 64
                            or readiness["viewId"] != view["id"]
                            or readiness["status"] != "ready"
                        ):
                            raise ValueError("Map readiness identity mismatch")
                        labels.update(label["text"] for label in readiness["labels"])
                        path = output / Path(view["path"]).name
                        views.append(MapView(view["id"], _png(path, view["pngHash"])))
                    if not views:
                        raise ValueError("No primary views for leg")
                    if any(marker["label"] not in labels for marker in raw["markers"]):
                        raise ValueError("Primary map lost numbered windows")
                    results[leg.leg_id] = tuple(views)
            except (OSError, ValueError, KeyError, TypeError):
                results.clear()
        if time.monotonic() > deadline:
            results.clear()
        # Static work has a separate shared ten-second limit, including cleanup.
        fallback_deadline = time.monotonic() + 10
        missing = [
            leg
            for leg in legs
            if leg.leg_id not in results and captured[leg.leg_id].effective_route_json
        ]
        fallback = root / "static"
        fallback.mkdir()
        fallback_input = root / "fallback.json"
        fallback_input.write_bytes(
            canonical_json(
                {
                    "legs": [
                        {
                            "legId": leg.leg_id,
                            "route": json.loads(
                                captured[leg.leg_id].effective_route_json
                            ),
                            "input": inputs[leg.leg_id],
                        }
                        for leg in missing
                    ]
                }
            )
        )
        if missing:
            _run_owned(
                [sys.executable, "-m", __name__, str(fallback_input), str(fallback)],
                fallback,
                fallback_deadline,
            )
        final = []
        for leg in legs:
            key = map_cache_key(snapshot, leg, inputs[leg.leg_id], runtime_identity)
            common = {
                "leg_id": leg.leg_id,
                "cache_key": key,
                "endpoints": _endpoints(captured[leg.leg_id]),
                "renderer_evidence_json": evidence,
            }
            if leg.leg_id in results:
                final.append(
                    LegMapResult(
                        views=results[leg.leg_id],
                        status="primary",
                        label=PRIMARY_LABEL,
                        warnings=notes[leg.leg_id],
                        **common,
                    )
                )
                continue
            try:
                png = _png(fallback / _static_filename(leg.leg_id))
                final.append(
                    LegMapResult(
                        views=(MapView(f"{leg.leg_id}/static", png),),
                        status="static",
                        label=STATIC_LABEL,
                        warnings=(*notes[leg.leg_id], STATIC_LABEL),
                        reason="Primary renderer unavailable or shared deadline exhausted",
                        **common,
                    )
                )
            except (OSError, ValueError):
                reason = "Route geometry unavailable or bounded static renderer failed"
                final.append(
                    LegMapResult(
                        views=(),
                        status="unavailable",
                        label="Route map unavailable",
                        warnings=(*notes[leg.leg_id], reason),
                        reason=reason,
                        **common,
                    )
                )
        return tuple(final)


def _static_maps(input_path: Path, output: Path) -> None:
    """Neutral offline route panel; no Cartopy downloads or legacy risk colors."""
    for leg in json.loads(input_path.read_bytes())["legs"]:
        try:
            points = leg["route"]["points"]
            if len(points) < 2:
                continue
            coordinates = []
            longitude = float(points[0]["longitude"])
            previous = longitude
            for point in points:
                current = float(point["longitude"])
                longitude += ((current - previous + 180) % 360) - 180
                coordinates.append((longitude, float(point["latitude"])))
                previous = current
            xs, ys = zip(*coordinates)
            xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
            scale = min(1640 / max(xmax - xmin, 1), 760 / max(ymax - ymin, 1))
            center = ((xmin + xmax) / 2, (ymin + ymax) / 2)
            image = Image.new("RGB", (1920, 1080), "#f5f5f5")
            draw = ImageDraw.Draw(image)
            draw.text((80, 40), STATIC_LABEL, fill="#252525", font_size=32)
            draw.text(
                (80, 100),
                "Neutral route diagram — geographic context unavailable",
                fill="#444444",
                font_size=26,
            )
            positions = [
                (960 + (x - center[0]) * scale, 600 - (y - center[1]) * scale)
                for x, y in coordinates
            ]
            draw.line(positions, fill="#444444", width=6)
            for label, position in (("Start", positions[0]), ("End", positions[-1])):
                x, y = position
                draw.ellipse((x - 9, y - 9, x + 9, y + 9), fill="#444444")
                draw.text((x + 16, y - 30), label, fill="#252525", font_size=26)
            raw = leg["input"]
            if raw:
                for marker in raw["markers"]:
                    point = raw["route"][marker["routeIndex"]]
                    # Unwrap relative to the route's first longitude, avoiding Greenwich.
                    lon = float(points[0]["longitude"])
                    for previous_point, next_point in zip(
                        raw["route"], raw["route"][1 : marker["routeIndex"] + 1]
                    ):
                        lon += (
                            (
                                next_point["longitude"]
                                - previous_point["longitude"]
                                + 180
                            )
                            % 360
                        ) - 180
                    x, y = (
                        960 + (lon - center[0]) * scale,
                        600 - (point["latitude"] - center[1]) * scale,
                    )
                    draw.ellipse((x - 7, y - 7, x + 7, y + 7), fill="#666666")
                    draw.text(
                        (x + 12, y + 12), marker["label"], fill="#252525", font_size=26
                    )
            image.save(output / _static_filename(leg["legId"]))
        except (KeyError, ValueError, TypeError):
            continue


if __name__ == "__main__":
    _static_maps(Path(sys.argv[1]), Path(sys.argv[2]))
