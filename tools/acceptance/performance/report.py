"""Warm-only descriptive statistics and strict like-for-like comparisons."""

import argparse
import json
import math
from itertools import pairwise
from pathlib import Path


def quantiles(values):
    ordered = sorted(values)
    if not ordered:
        return {}
    return {
        f"p{p}_ms": ordered[math.ceil(len(ordered) * p / 100) - 1] for p in (50, 95, 99)
    } | {"samples": len(ordered)}


def summarize(metadata, rows):
    measured = [r for r in rows if r["phase"] == "measured"]
    resources, latency = {}, {}
    for row in measured:
        for subsystem in (
            "backend",
            "prometheus",
            "browser",
            "sqlite",
            "storage",
            "instrumentation",
        ):
            for key, value in row.get(subsystem, {}).items():
                if value is None:
                    continue
                if not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"Nonfinite measurement: {subsystem}.{key}")
                resources.setdefault(f"{subsystem}.{key}", []).append(
                    (row["seconds"], value)
                )
        for endpoint, values in row.get("latency", {}).items():
            if any(not math.isfinite(v) or v < 0 for v in values):
                raise ValueError(f"Invalid latency: {endpoint}")
            latency.setdefault(endpoint, []).extend(values)
    summary = {}
    for name, points in resources.items():
        times, values = zip(*points)
        if name.endswith("cpu_seconds") and any(
            b < a for a, b in pairwise(values)
        ):
            raise ValueError(f"CPU counter reset: {name}; split the run")
        span = times[-1] - times[0]
        tmean, vmean = sum(times) / len(times), sum(values) / len(values)
        denominator = sum((t - tmean) ** 2 for t in times)
        summary[name] = {
            "samples": len(points),
            "first": values[0],
            "last": values[-1],
            "max": max(values),
            "span_seconds": span,
            "slope_per_minute": (
                60 * sum((t - tmean) * (v - vmean) for t, v in points) / denominator
                if denominator
                else None
            ),
        }
        if name.endswith("cpu_seconds") and span > 0:
            summary[name]["cores_used"] = (values[-1] - values[0]) / span
    span = measured[-1]["seconds"] - measured[0]["seconds"] if len(measured) > 1 else 0
    return {
        "metadata": metadata,
        "measured_span_seconds": span,
        "sustained_60_minutes": span >= 3600,
        "resources": summary,
        "latency": {k: quantiles(v) for k, v in latency.items()},
    }


def compare(baseline, candidate):
    for field in (
        "workload",
        "hardware",
        "instrumentation",
        "harness_sha",
        "browser",
        "runtime",
    ):
        if baseline["metadata"].get(field) != candidate["metadata"].get(field):
            raise ValueError(f"Incompatible {field}; no valid comparison")
    if abs(baseline["measured_span_seconds"] - candidate["measured_span_seconds"]) > 10:
        raise ValueError("Incompatible measured duration")
    result = {
        "original_baseline_sha": baseline["metadata"]["candidate_sha"],
        "candidate_sha": candidate["metadata"]["candidate_sha"],
        "resources": {},
        "latency": {},
    }
    for section in ("resources", "latency"):
        if baseline[section].keys() != candidate[section].keys():
            raise ValueError(f"Incompatible measurement coverage: {section}")
    for section, fields in (
        ("resources", ("last", "slope_per_minute", "cores_used")),
        ("latency", ("p50_ms", "p95_ms", "p99_ms")),
    ):
        for key in baseline[section].keys() & candidate[section].keys():
            delta = {}
            for field in fields:
                before, after = baseline[section][key].get(field), candidate[section][
                    key
                ].get(field)
                if before is not None and after is not None:
                    delta[field + "_delta"] = after - before
                    delta[field + "_percent"] = (
                        100 * (after - before) / abs(before) if before else None
                    )
            result[section][key] = delta
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            compare(
                json.loads(args.baseline.read_text()),
                json.loads(args.candidate.read_text()),
            ),
            indent=2,
            allow_nan=False,
        )
    )
