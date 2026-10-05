"""Comparable resource summaries and explicit performance acceptance gates."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from itertools import pairwise

MIB = 1024**2
BEHAVIORS = ("motion", "provenance", "masking", "shared_subscription", "lifecycle")
COMPARABLE_FIELDS = (
    "hardware",
    "renderer",
    "window_seconds",
    "viewers",
    "fixture",
    "gc_mode",
)
PROVENANCE_FIELDS = ("sha", "window_seconds", "viewers", "gc_mode", "fixture")


def quantiles(values: list[float]) -> dict[str, float] | None:
    """Nearest-rank quantiles; an empty sample is missing evidence."""
    if not values:
        return None
    ordered = sorted(values)
    return {
        f"p{p}": round(ordered[math.ceil(len(ordered) * p / 100) - 1], 6)
        for p in (50, 95, 99)
    }


def number(value: object, label: str) -> float:
    """Reject malformed/nonfinite measurements rather than passing NaN budgets."""
    if (
        isinstance(value, bool)
        or not isinstance(value, (float, int))
        or not math.isfinite(value)
    ):
        raise ValueError(f"{label} must be a finite number")
    if value < 0:
        raise ValueError(f"{label} must be nonnegative")
    return float(value)


def _growth(rows: list[dict], key: str) -> float | None:
    selected = [row for row in rows if key in row]
    if len(selected) < 2:
        return None
    return selected[-1][key] - selected[0][key]


def _late_trend(rows: list[dict], key: str) -> dict | None:
    selected = [row for row in rows if key in row]
    if len(selected) < 2:
        return None
    cutoff = selected[-1]["monotonic_seconds"] - 1200
    selected = [row for row in selected if row["monotonic_seconds"] >= cutoff]
    times = [row["monotonic_seconds"] for row in selected]
    values = [row[key] for row in selected]
    mean_time, mean_value = sum(times) / len(times), sum(values) / len(values)
    denominator = sum((t - mean_time) ** 2 for t in times)
    return {
        "duration_seconds": times[-1] - times[0],
        "range_bytes": max(values) - min(values),
        "slope_bytes_per_minute": (
            60
            * sum((t - mean_time) * (v - mean_value) for t, v in zip(times, values))
            / denominator
            if denominator
            else None
        ),
    }


def summarize_phase(samples: list[dict], metadata: dict) -> dict:
    """Summarize warm measurements; do not manufacture absent resource evidence."""
    resources, requests = [], []
    for row in samples:
        for field in PROVENANCE_FIELDS:
            if field in row and row[field] != metadata.get(field):
                raise ValueError(f"Mixed phase provenance: {field}")
        if row.get("kind") == "resource":
            for field in (
                "monotonic_seconds",
                "backend_cpu_seconds",
                "prometheus_cpu_seconds",
                "backend_rss_bytes",
                "heap_bytes",
                "post_gc_heap_bytes",
            ):
                if field in row:
                    number(row[field], field)
            number(row.get("monotonic_seconds"), "monotonic_seconds")
            resources.append(row)
        elif row.get("kind") == "request":
            start = number(row.get("started_seconds"), "request start")
            end = number(row.get("completed_seconds"), "request completion")
            if end < start:
                raise ValueError("Negative request duration")
            requests.append(row)
        else:
            raise ValueError("Unknown performance sample kind")
    intervals = []
    for before, after in pairwise(resources):
        elapsed = after["monotonic_seconds"] - before["monotonic_seconds"]
        if elapsed <= 0:
            raise ValueError("Resource monotonic times must strictly increase")
        intervals.append(elapsed)
        for field in ("backend_cpu_seconds", "prometheus_cpu_seconds"):
            if field in before and field in after and after[field] < before[field]:
                raise ValueError("CPU counters must not move backwards")
    duration = sum(intervals)
    cpu = None
    if duration and all(
        all(key in row for key in ("backend_cpu_seconds", "prometheus_cpu_seconds"))
        for row in resources
    ):
        cpu = (
            100
            * sum(
                resources[-1][key] - resources[0][key]
                for key in ("backend_cpu_seconds", "prometheus_cpu_seconds")
            )
            / duration
        )
    logical = (
        metadata.get("hardware", {}).get("logical_cpus")
        if isinstance(metadata.get("hardware"), dict)
        else None
    )
    warm = [row for row in requests if not row.get("cold", False)]
    starts: dict[str, list[float]] = defaultdict(list)
    for row in warm:
        starts[str(row.get("page_id", "unknown"))].append(row["started_seconds"])
    spacing = []
    for times in starts.values():
        times.sort()
        spacing.extend(b - a for a, b in pairwise(times))
    return {
        "metadata": dict(metadata),
        "measured_duration_seconds": duration,
        "max_resource_gap_seconds": max(intervals) if intervals else None,
        "resource_count": len(resources),
        "request_count": len(warm),
        "request_errors": sum(
            not isinstance(row.get("status"), int) or not 200 <= row["status"] < 300
            for row in requests
        ),
        "request_ms": quantiles(
            [(row["completed_seconds"] - row["started_seconds"]) * 1000 for row in warm]
        ),
        "request_start_spacing_seconds": quantiles(spacing),
        "observed_viewers": len(starts),
        "combined_cpu_percent_one_core": cpu,
        "combined_cpu_percent_host": (
            cpu / logical
            if cpu is not None and isinstance(logical, int) and logical > 0
            else None
        ),
        "backend_rss_growth_bytes": _growth(resources, "backend_rss_bytes"),
        "ordinary_heap_growth_bytes": _growth(resources, "heap_bytes"),
        "retained_heap_growth_bytes": _growth(resources, "post_gc_heap_bytes"),
        "retained_heap_late_trend": _late_trend(resources, "post_gc_heap_bytes"),
    }


def _gate(value: object, unit: str, passed: bool | None, reason: str) -> dict:
    return {
        "status": "incomplete" if passed is None else "passed" if passed else "failed",
        "value": value,
        "unit": unit,
        "reason": reason,
    }


def evaluate_budgets(baseline: dict, candidate: dict) -> dict:
    """Apply declared budgets while retaining missing provenance/coverage gates."""
    meta, base_meta = candidate.get("metadata", {}), baseline.get("metadata", {})
    phase_status = meta.get("phase", {}).get("status")
    phase_errors = meta.get("errors")
    phase_ok = (
        False
        if phase_status == "failed" or phase_errors
        else True if phase_status == "measured" and phase_errors == [] else None
    )
    request_ms = candidate.get("request_ms")
    p95 = request_ms.get("p95") if request_ms else None
    budgets = {
        "latency": _gate(
            p95,
            "ms",
            p95 < 500 if p95 is not None else None,
            "Healthy warm p95 must be below 500 ms",
        )
    }
    budgets["browser_phase"] = _gate(
        phase_status,
        "outcome",
        phase_ok,
        "Completed browser phase and zero captured errors required",
    )
    comparable = all(
        field in meta and field in base_meta and meta[field] == base_meta[field]
        for field in COMPARABLE_FIELDS
    )
    candidate_cpu, baseline_cpu = candidate.get(
        "combined_cpu_percent_one_core"
    ), baseline.get("combined_cpu_percent_one_core")
    increase = (
        candidate_cpu - baseline_cpu
        if comparable and candidate_cpu is not None and baseline_cpu is not None
        else None
    )
    budgets["cpu_increase"] = _gate(
        increase,
        "percentage points of one core",
        increase <= 10 if increase is not None else None,
        "Comparable baseline required; combined CPU increase must be <=10",
    )
    for name, key in (
        ("backend_rss_growth", "backend_rss_growth_bytes"),
        ("retained_heap_growth", "retained_heap_growth_bytes"),
    ):
        value = candidate.get(key)
        budgets[name] = _gate(
            value,
            "bytes",
            value <= 16 * MIB if value is not None else None,
            "After-warm-up growth must be <=16 MiB",
        )
    duration = candidate.get("measured_duration_seconds", 0)
    budgets["sustained_duration"] = _gate(
        duration,
        "seconds",
        True if duration >= 3600 else None,
        "At least 3600 measured seconds after warm-up required",
    )
    gap = candidate.get("max_resource_gap_seconds")
    interval = meta.get("resource_interval_seconds")
    sampling = (
        True
        if gap is not None
        and isinstance(interval, (int, float))
        and 0 < interval <= 5
        and gap <= 2 * interval
        else None
    )
    budgets["resource_coverage"] = _gate(
        gap,
        "seconds",
        sampling,
        "No resource sampling gap over twice the <=5s interval",
    )
    required = (
        "sha",
        "images",
        "hardware",
        "renderer",
        "window_seconds",
        "viewers",
        "cadence_seconds",
        "mode",
        "fixture",
        "gc_mode",
        "warmup_seconds",
    )
    provenance = (
        all(meta.get(key) for key in required)
        and bool(re.fullmatch(r"[0-9a-f]{40}", str(meta.get("sha", ""))))
        and meta.get("warmup_seconds", 0) >= 300
    )
    budgets["metadata_provenance"] = _gate(
        None,
        "coverage",
        True if provenance else None,
        "Complete candidate/host/source/build provenance and >=300s warm-up required",
    )
    observed = candidate.get("observed_viewers", 0)
    budgets["viewers"] = _gate(
        observed,
        "viewers",
        True if observed == meta.get("viewers") and observed in (1, 2) else None,
        "Measure each requested viewer directly",
    )
    errors = candidate.get("request_errors", 0)
    budgets["http_errors"] = _gate(
        errors, "errors", errors == 0, "No healthy-path request errors"
    )
    behavior = meta.get("behavior", {})
    for key in (*BEHAVIORS, "cleanup"):
        status = meta.get("cleanup") if key == "cleanup" else behavior.get(key)
        budgets[key] = _gate(
            status,
            "control",
            True if status == "passed" else False if status == "failed" else None,
            "Required behavior and owned-resource cleanup evidence",
        )
    budgets["upstream_work"] = _gate(
        meta.get("upstream_work"),
        "coverage",
        True if meta.get("upstream_work") == "recorded" else None,
        "Query spans/evaluation work must be recorded",
    )
    states = {gate["status"] for gate in budgets.values()}
    return {
        "status": (
            "failed"
            if "failed" in states
            else "incomplete" if "incomplete" in states else "passed"
        ),
        "budgets": budgets,
    }
