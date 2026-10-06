# Native bootstrap must precede scientific imports in each source worker.
"""One offline source per capped container, initialized before native imports."""

from __future__ import annotations

from .native import initialize_native

initialize_native()
import json
import resource
import sys
import time
from pathlib import Path

from .model import file_hash, load_capture


def binding(source, root, descriptor_path):
    descriptor = json.loads(descriptor_path.read_text())
    return {
        "source": source,
        "capture_manifest_sha256": file_hash(
            root / "captures" / source / "capture.json"
        ),
        "descriptor_sha256": file_hash(descriptor_path),
        "times": {
            key: descriptor.get(key)
            for key in (
                "run_at_ms",
                "lead_seconds",
                "valid_at_ms",
                "valid_from_ms",
                "valid_to_ms",
                "scan_start_ms",
                "scan_end_ms",
                "diagnostic_replay_at_ms",
            )
        },
    }


def main():
    mode, source, root_arg = sys.argv[1:]
    root = Path(root_arg)
    start = time.monotonic()
    capture = load_capture(root / "captures" / source / "capture.json")
    destination = root / "products" / source
    if mode == "normalize":
        if source == "gfs":
            from .gfs import normalize_gfs
            from .reference import compare_gfs

            artifact = normalize_gfs(capture, destination)
            controls = compare_gfs(capture, artifact.descriptor_path)
        elif source == "goes19-c13":
            from .reference import compare_satellite
            from .satellite import normalize_satellite

            artifact = normalize_satellite(capture, destination)
            controls = compare_satellite(capture, artifact.descriptor_path)
        else:
            from .advisory import normalize_advisories

            artifact = normalize_advisories(capture, destination)
            controls = {
                "normalized": True,
                "descriptor": json.loads(artifact.descriptor_path.read_text())[
                    "counts"
                ],
            }
        (root / "oracles" / f"{source}-source.json").write_text(
            json.dumps(
                {
                    "binding": binding(source, root, artifact.descriptor_path),
                    "comparisons": controls,
                },
                indent=2,
            )
        )
        if source == "gfs":
            import numpy as np

            from .grid import regional_owner, write_grid

            d = json.loads(artifact.descriptor_path.read_text())
            d["capture_manifest_path"] = str(
                root / "captures" / source / "capture.json"
            )
            d["normalization_version"] = "synthetic-controls-only"
            d["source_id"] = "SYNTHETIC regional interval control"
            d["region_intervals"] = [
                {"region": "A", "scan_start_ms": 0, "scan_end_ms": 1000},
                {"region": "B", "scan_start_ms": 2000, "scan_end_ms": 3000},
            ]
            # This separate fixture is synthetic: no inherited model valid time.
            for key in (
                "valid_at_ms",
                "run_at_ms",
                "lead_seconds",
                "scan_start_ms",
                "scan_end_ms",
            ):
                d[key] = None
            d["components"] = {"t": d["components"]["t"]}
            d["attribution"] = ["SYNTHETIC ownership fixture; no observational claim"]
            values = np.full((361, 720), 250.0)
            mask = np.zeros((361, 720), dtype=np.uint8)
            owners = np.ones((361, 720), dtype=np.uint8)
            # Two competing regions across a seam; overlap prefers the smaller
            # view angle, then newer scan. Both scans retain their own intervals.
            for column in range(720):
                owner = regional_owner(
                    [
                        {
                            "region": "A",
                            "mask": 0,
                            "value": 250,
                            "view_angle": 10 if column < 360 else 30,
                            "scan_end_ms": 1000,
                        },
                        {
                            "region": "B",
                            "mask": 0,
                            "value": 270,
                            "view_angle": 30 if column < 360 else 10,
                            "scan_end_ms": 3000,
                        },
                    ]
                )
                values[:, column] = owner["value"]
                owners[:, column] = 1 if owner["region"] == "A" else 2
            mask[179:182, 359:362] = [[1, 3, 1], [2, 3, 2], [1, 3, 1]]
            owners[179:182, 359:362] = 0
            cases = []
            for i, (name, am, bm, av, bv) in enumerate(
                (
                    ("valid-over-missing", 2, 0, 10, 30),
                    ("valid-over-rejected", 0, 3, 30, 10),
                    ("lower-view-angle", 0, 0, 10, 30),
                    ("newer-scan", 0, 0, 10, 10),
                    ("all-invalid", 2, 3, 10, 10),
                )
            ):
                longitude = -120 + i * 20
                candidates = [
                    {
                        "region": "A",
                        "mask": am,
                        "value": 250,
                        "view_angle": av,
                        "scan_start_ms": 0,
                        "scan_end_ms": 1000,
                    },
                    {
                        "region": "B",
                        "mask": bm,
                        "value": 270,
                        "view_angle": bv,
                        "scan_start_ms": 2000,
                        "scan_end_ms": 3000,
                    },
                ]
                result = regional_owner(candidates)
                row, column = 140, int((longitude + 180) * 2)
                area = np.s_[row - 3 : row + 4, column - 3 : column + 4]
                values[area] = result["value"] or 0
                mask[area] = result["mask"]
                owners[area] = {None: 0, "A": 1, "B": 2}[result["region"]]
                cases.append(
                    {
                        "name": name,
                        "longitude": longitude,
                        "latitude": 20,
                        "candidates": candidates,
                    }
                )
            d["synthetic_controls"] = cases
            artifact = write_grid(
                d, {"t": values}, mask, root / "products" / "synthetic", lineage=owners
            )
            (root / "oracles" / "synthetic-source.json").write_text(
                json.dumps(
                    {
                        "synthetic": True,
                        "descriptor_sha256": file_hash(artifact.descriptor_path),
                        "policy": "valid; lower view angle; newer scan end; stable region ID",
                        "cases": cases,
                        "expected": [
                            {"region": region, "value": value, "mask": flag}
                            for region, value, flag in [
                                ("B", 270, 0),
                                ("A", 250, 0),
                                ("A", 250, 0),
                                ("B", 270, 0),
                                (None, None, 3),
                            ]
                        ],
                        "stable_id_probe": {
                            "candidates": [
                                {
                                    "region": "B",
                                    "mask": 0,
                                    "value": 270,
                                    "view_angle": 10,
                                    "scan_end_ms": 1000,
                                },
                                {
                                    "region": "A",
                                    "mask": 0,
                                    "value": 250,
                                    "view_angle": 10,
                                    "scan_end_ms": 1000,
                                },
                            ],
                            "expected": {"region": "A", "value": 250, "mask": 0},
                        },
                    },
                    indent=2,
                )
            )

    else:
        from .reference import sample_grid

        journey = json.loads((root / "browser" / "journey.json").read_text())
        samples = journey["samples"][source]
        records = [
            sample_grid(
                destination / "descriptor.json",
                s["sampleLongitude"],
                s["sampleLatitude"],
            )
            for s in samples
        ]
        (root / "oracles" / f"{source}-gpu.json").write_text(
            json.dumps(records, indent=2)
        )
    usage = resource.getrusage(resource.RUSAGE_SELF)
    metrics = {
        "source": source,
        "mode": mode,
        "binding": binding(source, root, destination / "descriptor.json"),
        "elapsed_seconds": time.monotonic() - start,
        "cpu_seconds": usage.ru_utime + usage.ru_stime,
        "max_rss_bytes": usage.ru_maxrss * 1024,
        "python": sys.version,
        "limits": {"cpu": 1, "memory_bytes": 1073741824, "seconds": 120},
    }
    peak = Path("/sys/fs/cgroup/memory.peak")
    if peak.exists():
        metrics["cgroup_memory_peak_bytes"] = int(peak.read_text())
    (root / "oracles" / f"{source}-{mode}-metrics.json").write_text(
        json.dumps(metrics, indent=2)
    )


if __name__ == "__main__":
    main()
