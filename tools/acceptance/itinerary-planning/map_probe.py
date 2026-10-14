"""Read-only diagnosis of original source/package map eligibility predicates."""

import argparse
import json
import shutil
import sys
from datetime import datetime
from hashlib import sha256
from itertools import pairwise
from pathlib import Path


def input_hashes(root):
    root = Path(root)
    return {
        str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def verify_input_hashes(root, expected):
    if input_hashes(root) != expected:
        raise ValueError("Original input hash mismatch")


def probe_snapshot(captured, projected):
    from app.mission.exporter.map_inputs import build_map_input

    route = (
        json.loads(captured.effective_route_json)
        if captured.effective_route_json
        else {}
    )
    points = route.get("points", [])
    stamps = [
        (
            datetime.fromisoformat(p["expected_arrival_time"].replace("Z", "+00:00"))
            if p.get("expected_arrival_time")
            else None
        )
        for p in points
    ]
    failures = []
    previous = sys.gettrace()

    def trace(frame, event, value):
        if (
            event == "exception"
            and frame.f_code.co_filename == build_map_input.__code__.co_filename
        ):
            exception = value[1]
            if isinstance(exception, (ValueError, TypeError, KeyError, StopIteration)):
                failures.append((str(exception), frame.f_locals.copy()))
        return trace

    try:
        # Observe the actual rejected branch rather than inferring it from counts.
        sys.settrace(trace)
        scene, reasons = build_map_input(captured, projected)
    finally:
        sys.settrace(previous)
    code = None
    if scene is None:
        if not captured.effective_route_json:
            code = "route_missing"
        elif failures:
            message, values = failures[-1]
            if "density exceeds" in message:
                code = (
                    "route_marker_limit"
                    if len(values.get("markers", [])) > 200
                    else "route_point_limit"
                )
            elif "must increase" in message:
                code = "route_timing_non_increasing"
            elif "does not match flight bounds" in message:
                code = "route_bounds_mismatch"
            elif "coordinates invalid" in message:
                code = "route_coordinates_invalid"
            elif "Antipodal" in message:
                code = "route_antipodal_segment"
            elif len(points) > 2000:
                code = "route_point_limit"
            elif any(stamp is None for stamp in stamps):
                code = "route_timing_missing"
            else:
                code = "route_bounds_mismatch"
        else:
            raise ValueError("Omission has no observed failed eligibility predicate")
    return {
        "leg_id": captured.leg_id,
        "point_count": len(points),
        "untimed_points": sum(stamp is None for stamp in stamps),
        "non_increasing_adjacent": sum(
            a >= b for a, b in pairwise(stamps) if a and b
        ),
        "utc_bounds": (
            [stamp.isoformat() for stamp in projected.utc_bounds]
            if projected.utc_bounds
            else None
        ),
        "occurrence_ids": [p.get("occurrence_id") for p in points],
        "window_ids": [row.id for row in projected.coordination_rows],
        "marker_count": len(projected.coordination_rows),
        "scene_available": scene is not None,
        "failed_predicate": code,
        "diagnostics": list(reasons),
        "route_sha256": sha256(captured.effective_route_json or b"").hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--reviewed-package", type=Path, required=True)
    parser.add_argument("--expected-hashes", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = json.loads(args.expected_hashes.read_bytes())
    verify_input_hashes(args.input_root, expected["inputs"])
    package_hash = sha256(args.reviewed_package.read_bytes()).hexdigest()
    if package_hash != expected["package"]:
        raise ValueError("Reviewed package hash mismatch")
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[3] / "backend/starlink-location")
    )
    from map_probe_inputs import package_snapshots

    temporary = args.output.parent / (args.output.stem + "-sources")
    owner_path = args.output.with_suffix(".ownership.json")
    owner = {
        "temporary_root": str(temporary.resolve()),
        "purpose": "read-only map source copies",
        "cleaned": False,
    }
    with owner_path.open("x") as handle:
        json.dump(owner, handle)
    temporary.mkdir(mode=0o700)
    try:
        results = [
            probe_snapshot(captured, projected)
            for captured, projected in package_snapshots(
                args.reviewed_package, temporary, set(expected["inputs"].values())
            )
        ]
        verify_input_hashes(args.input_root, expected["inputs"])
        if sha256(args.reviewed_package.read_bytes()).hexdigest() != package_hash:
            raise ValueError("Reviewed package hash changed during probe")
        report = {
            "package_sha256": package_hash,
            "input_hashes": expected["inputs"],
            "legs": results,
        }
        with args.output.open("x") as handle:
            json.dump(report, handle, indent=2)
        print(
            json.dumps(
                {
                    "legs": [
                        {
                            key: result[key]
                            for key in (
                                "point_count",
                                "marker_count",
                                "scene_available",
                                "failed_predicate",
                            )
                        }
                        for result in results
                    ],
                    "source_hashes_unchanged": True,
                }
            )
        )
    finally:
        shutil.rmtree(temporary)
        owner["cleaned"] = not temporary.exists()
        owner_path.write_text(json.dumps(owner, indent=2))


if __name__ == "__main__":
    main()
