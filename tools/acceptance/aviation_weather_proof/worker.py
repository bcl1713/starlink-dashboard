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

from .model import load_capture


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
            json.dumps(controls, indent=2)
        )
        if source == "gfs":
            import numpy as np

            from .grid import write_grid

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
            values = np.full((361, 720), 250.0)
            values[:, 719] = 260
            mask = np.zeros((361, 720), dtype=np.uint8)
            mask[179:182, 359:362] = 3
            write_grid(
                d,
                {
                    "t": values,
                    "u": np.full_like(values, 10),
                    "v": np.zeros_like(values),
                },
                mask,
                root / "products" / "synthetic",
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
