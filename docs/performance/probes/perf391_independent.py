"""Independent read-only evidence analysis and disposable component profiling.

Never imports or changes either frozen harness. Run under an external timeout.
The component mode uses private storage and no application lifespan or services.
"""

import argparse
import hashlib
import itertools
import json
import math
import os
import pstats
import statistics
import sys
import time
from pathlib import Path


def distribution(values):
    values = sorted(values)
    return (
        {
            "count": len(values),
            "mean": statistics.mean(values),
            **{
                p: values[math.ceil(len(values) * q) - 1]
                for p, q in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1)]
            },
        }
        if values
        else {}
    )


def read_lines(path):
    return [json.loads(line) for line in path.open()]


def profile_rows(path):
    stats = pstats.Stats(str(path))
    rows = []
    for (filename, line, name), (
        primitive,
        calls,
        own,
        cumulative,
        callers,
    ) in stats.stats.items():
        rows.append(
            {
                "file": filename,
                "line": line,
                "name": name,
                "calls": calls,
                "primitive_calls": primitive,
                "self_ms": own * 1000,
                "cumulative_ms": cumulative * 1000,
            }
        )
    return sorted(rows, key=lambda x: x["cumulative_ms"], reverse=True)


def retained(root, manifest_path):
    manifest = json.loads(manifest_path.read_text())
    mismatches, checked, total_bytes = [], 0, 0
    for name, expected in manifest["files"].items():
        path = root / name
        digest = hashlib.sha256()
        if not path.is_file():
            mismatches.append({"path": name, "reason": "missing"})
            continue
        with path.open("rb") as stream:
            while block := stream.read(1024 * 1024):
                digest.update(block)
                total_bytes += len(block)
        checked += 1
        if digest.hexdigest() != expected:
            mismatches.append({"path": name, "reason": "hash mismatch"})
    result = {
        "manifest_checked": checked,
        "manifest_bytes": total_bytes,
        "manifest_mismatches": mismatches,
        "soaks": {},
        "profiles": {},
    }
    for role in ["original", "candidate", "candidate-repeat1"]:
        name = "v2-soak-off-" + role
        run = root / "runs" / name
        bounds = json.loads((run / "availability-boundaries.json").read_text())
        rows = [
            x
            for x in read_lines(run / "availability-observations.jsonl")
            if x["at"] >= bounds["start"]
            and (bounds["end"] is None or x["at"] <= bounds["end"])
        ]
        gaps = [b["at"] - a["at"] for a, b in itertools.pairwise(rows)]
        worst = max(
            range(1, len(rows)), key=lambda i: rows[i]["at"] - rows[i - 1]["at"]
        )
        host = read_lines(root / (name + "-host.jsonl"))
        at = rows[worst]["at"]
        nearby_host = [x for x in host if abs(x["timestamp"] - at) < 31]
        cpu_intervals = []
        for a, b in itertools.pairwise(nearby_host):
            av, bv = [list(map(int, x["cpu_stat"].split()[1:])) for x in [a, b]]
            delta = [y - x for x, y in zip(av, bv)]
            total = sum(delta[:8])
            cpu_intervals.append(
                {
                    "start": a["timestamp"],
                    "end": b["timestamp"],
                    "busy_fraction": 1 - (delta[3] + delta[4]) / total,
                    "iowait_fraction": delta[4] / total,
                    "steal_fraction": delta[7] / total,
                }
            )
        distinct = []
        for x in rows:
            stamp = x["source"]["acquired_at"]
            if stamp is not None and (not distinct or stamp != distinct[-1]):
                distinct.append(stamp)
        result["soaks"][role] = {
            "capture_gap_seconds": distribution(gaps),
            "gaps_over_1_5": sum(x > 1.5 for x in gaps),
            "capture_wall_ms": distribution([x["capture_wall_ms"] for x in rows]),
            "acquisition_age_seconds": distribution(
                [
                    x["acquisition_age_seconds"]
                    for x in rows
                    if x["acquisition_age_seconds"] is not None
                ]
            ),
            "sampled_distinct_acquisitions": len(distinct),
            "sampled_acquisition_jumps_seconds": distribution(
                [b - a for a, b in itertools.pairwise(distinct)]
            ),
            "worst_neighborhood": rows[max(0, worst - 3) : worst + 4],
            "nearby_host": nearby_host,
            "nearby_cpu_intervals": cpu_intervals,
        }
    for role in ["original", "dev", "candidate"]:
        for repetition in range(1, 4):
            name = f"v2-counters-r{repetition}-{role}"
            for kind in ["tick", "metrics"]:
                path = root / "runs" / name / (kind + ".prof")
                if path.exists():
                    result["profiles"][name + "/" + kind] = profile_rows(path)
    return result


def measure(operation, n):
    for _ in range(5):
        operation()
    cpu, wall = [], []
    for _ in range(n):
        began, start_cpu = time.perf_counter(), time.thread_time()
        operation()
        cpu.append((time.thread_time() - start_cpu) * 1000)
        wall.append((time.perf_counter() - began) * 1000)
    return {"cpu_ms": distribution(cpu), "wall_ms": distribution(wall)}


if __name__ == "__main__":
    from perf391_independent_component import component

    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["retained", "component", "timing"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / (args.mode + "-owner.json")).write_text(
        json.dumps(
            {
                "pid": os.getpid(),
                "pgid": os.getpgid(0),
                "command": sys.argv,
                "compose_project": None,
                "volumes": [],
                "listeners": (
                    ["task-owned ephemeral loopback socket; see timing-listener.json"]
                    if args.mode == "timing"
                    else []
                ),
                "temporary_paths": (
                    [str(args.output / "storage")]
                    if args.mode in {"component", "timing"}
                    else []
                ),
            },
            indent=2,
        )
    )
    result = (
        retained(args.root, args.manifest)
        if args.mode == "retained"
        else component(args.root.resolve(), args.output, timing=args.mode == "timing")
    )
    (args.output / (args.mode + ".json")).write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {"mode": args.mode, "output": str(args.output), "status": "finished"}
        )
    )
