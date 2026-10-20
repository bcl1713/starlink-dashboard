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
        if name.endswith("cpu_seconds") and any(b < a for a, b in pairwise(values)):
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


def latency_coverage(endpoint, baseline, candidate):
    """Conservative coverage gates; these do not establish quantile precision."""
    viewers = max(1, baseline["metadata"]["workload"].get("viewers", 1))
    polling = {
        "/api/overview-history",
        "/api/status",
        "/api/active-x-link",
        "/api/simulation/run",
    }
    periodic = {
        "backend_tick_wall_ms",
        "backend_tick_thread_cpu_ms",
        "backend_metrics_prepare_wall_ms",
        "backend_metrics_prepare_thread_cpu_ms",
        "backend_event_loop_delay_ms",
        "backend_/metrics",
    }
    if endpoint in {"observer_status", "observer_operator_read"}:
        category, minimum, floor = "observer", 5, 0.8 / 5
    elif endpoint.removeprefix("backend_") in polling:
        # Same five-second liveness floor as the existing browser polling guard.
        category, minimum, floor = "polling", 20, viewers / 5
    elif endpoint in periodic:
        category, minimum, floor = "periodic", 20, 1 / 5
    elif endpoint in {"frame", "observer_delivery_error_ms"}:
        category, minimum, floor = "diagnostic", 20, 0
    else:
        # Settings/Operator/event requests do not have a one-second contract.
        category, minimum, floor = "infrequent", 5, 0
    counts, rates, spans = [], [], []
    for label, run in (("baseline", baseline), ("candidate", candidate)):
        count = run["latency"][endpoint].get("samples")
        span = run["measured_span_seconds"]
        if type(count) is not int or count < minimum:
            raise ValueError(
                f"Incompatible latency coverage: {endpoint} ({category}, {label}); "
                f"requires at least {minimum} samples, got {count}"
            )
        rate = count / span
        # One completion at a window boundary is ordinary count jitter.
        if count + 1 < floor * span:
            raise ValueError(
                f"Incompatible latency coverage: {endpoint} ({category}, {label}); "
                f"completion rate {rate:.3f}/s is below {floor:.3f}/s"
            )
        counts.append(count)
        rates.append(rate)
        spans.append(span)
    # Symmetric 20% rate tolerance, plus one boundary completion. Normalize by
    # each measured span: equal counts need not mean equal completion rates.
    tolerance = max(rates) * 0.2 + 1 / min(spans)
    if abs(rates[0] - rates[1]) > tolerance:
        raise ValueError(
            f"Incompatible latency completion rate: {endpoint} ({category}); "
            f"{counts[0]} vs {counts[1]} samples, {rates[0]:.3f} vs {rates[1]:.3f}/s"
        )
    return {
        "coverage_class": category,
        "samples_before": counts[0],
        "samples_after": counts[1],
        "completions_per_second_before": rates[0],
        "completions_per_second_after": rates[1],
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
    for run in (baseline, candidate):
        span = run["measured_span_seconds"]
        if not math.isfinite(span) or span <= 0:
            raise ValueError(
                "Incompatible measured duration: positive finite span required"
            )
        outcomes = run["metadata"].get("request_outcomes", {})
        if outcomes.get("unexpected_failures") != 0:
            raise ValueError(
                "Incompatible request coverage: failed requests or missing outcomes"
            )
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
    for name, before in baseline["resources"].items():
        after = candidate["resources"][name]
        if (
            before["samples"] < 2
            or after["samples"] < 2
            or abs(before["samples"] - after["samples"]) > 1
            or abs(before["span_seconds"] - after["span_seconds"]) > 10
        ):
            raise ValueError(f"Incompatible resource coverage: {name}")
    coverage = {
        endpoint: latency_coverage(endpoint, baseline, candidate)
        for endpoint in baseline["latency"]
    }
    for section, fields in (
        ("resources", ("last", "slope_per_minute", "cores_used")),
        ("latency", ("p50_ms", "p95_ms", "p99_ms")),
    ):
        for key in baseline[section].keys() & candidate[section].keys():
            delta = coverage[key].copy() if section == "latency" else {}
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
