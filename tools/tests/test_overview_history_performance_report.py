"""Performance gates must require comparable, complete resource evidence."""

from copy import deepcopy

import pytest
from acceptance.overview_history.report import evaluate_budgets, summarize_phase

MIB = 1024**2
SHA = "a" * 40
BEHAVIORS = ("motion", "provenance", "masking", "shared_subscription", "lifecycle")


def metadata(**changes):
    return {
        "sha": SHA,
        "images": ["sha256:backend", "sha256:frontend", "sha256:prometheus"],
        "hardware": {"host": "forge", "cpu": "test", "logical_cpus": 20},
        "renderer": "SwiftShader",
        "window_seconds": 1800,
        "viewers": 1,
        "cadence_seconds": 1,
        "mode": "incremental",
        "fixture": "seed-v1-and-simulation",
        "gc_mode": "controlled",
        "warmup_seconds": 300,
        "resource_interval_seconds": 5,
        "cleanup": "passed",
        "behavior": {name: "passed" for name in BEHAVIORS},
        "upstream_work": "recorded",
        **changes,
    }


def samples(duration=3600, backend_growth=0, heap_growth=0, cpu_percent=10):
    rows = []
    for seconds in range(0, duration + 1, 5):
        ratio = seconds / duration
        rows.append(
            {
                "kind": "resource",
                "monotonic_seconds": seconds,
                "backend_cpu_seconds": seconds * cpu_percent / 200,
                "prometheus_cpu_seconds": seconds * cpu_percent / 200,
                "backend_rss_bytes": 100 * MIB + backend_growth * ratio,
                "heap_bytes": 100 * MIB + 50 * MIB * ratio,
                "post_gc_heap_bytes": 90 * MIB + heap_growth * ratio,
            }
        )
    if duration % 5:
        rows.append({**rows[-1], "monotonic_seconds": duration})
    for i, latency in enumerate((10, 20, 30, 40, 499)):
        rows.append(
            {
                "kind": "request",
                "started_seconds": 100 + i,
                "completed_seconds": 100 + i + latency / 1000,
                "status": 200,
                "page_id": "one",
                "cold": False,
            }
        )
    return rows


def report(**changes):
    return summarize_phase(samples(**changes), metadata())


def baseline():
    return summarize_phase(
        samples(duration=600, cpu_percent=0), metadata(mode="full", cadence_seconds=5)
    )


def test_nearest_rank_quantiles():
    result = report()
    assert result["request_ms"] == pytest.approx({"p50": 30, "p95": 499, "p99": 499})
    assert result["request_start_spacing_seconds"]["p50"] == 1
    assert result["request_count"] == 5
    assert result["retained_heap_growth_bytes"] == 0
    assert result["ordinary_heap_growth_bytes"] == 50 * MIB


def test_missing_samples_are_incomplete():
    empty = summarize_phase([], metadata())
    assert empty["request_ms"] is None
    assert empty["combined_cpu_percent_one_core"] is None
    assert evaluate_budgets(baseline(), empty)["status"] == "incomplete"


def test_cpu_uses_percentage_of_one_core():
    result = report(cpu_percent=10)
    assert result["combined_cpu_percent_one_core"] == pytest.approx(10)
    assert result["combined_cpu_percent_host"] == pytest.approx(0.5)
    assert evaluate_budgets(baseline(), result)["budgets"]["cpu_increase"][
        "value"
    ] == pytest.approx(10)


def test_exact_budget_boundaries():
    at_limit = report(backend_growth=16 * MIB, heap_growth=16 * MIB)
    assert evaluate_budgets(baseline(), at_limit)["status"] == "passed"
    for field in ("backend_growth", "heap_growth"):
        over = report(**{field: 16 * MIB + 1})
        assert evaluate_budgets(baseline(), over)["status"] == "failed"
    over_cpu = report(cpu_percent=10.001)
    assert (
        evaluate_budgets(baseline(), over_cpu)["budgets"]["cpu_increase"]["status"]
        == "failed"
    )
    rows = samples()
    rows[-1]["completed_seconds"] = rows[-1]["started_seconds"] + 0.5
    assert (
        evaluate_budgets(baseline(), summarize_phase(rows, metadata()))["budgets"][
            "latency"
        ]["status"]
        == "failed"
    )


def test_short_soak_is_incomplete():
    result = report(duration=3599)
    gates = evaluate_budgets(baseline(), result)
    assert gates["budgets"]["sustained_duration"]["status"] == "incomplete"
    assert gates["status"] == "incomplete"


@pytest.mark.parametrize(
    "key,value", [("sha", "b" * 40), ("window_seconds", 300), ("gc_mode", "ordinary")]
)
def test_mixed_phase_provenance_is_rejected(key, value):
    rows = samples()
    rows[1][key] = value
    with pytest.raises(ValueError, match="provenance"):
        summarize_phase(rows, metadata())


@pytest.mark.parametrize(
    "field", ["monotonic_seconds", "backend_cpu_seconds", "prometheus_cpu_seconds"]
)
def test_negative_time_or_cpu_deltas_are_rejected(field):
    rows = samples()
    rows[2][field] = rows[1][field] - 0.01
    with pytest.raises(ValueError, match="monotonic|CPU"):
        summarize_phase(rows, metadata())


@pytest.mark.parametrize(
    "field", ["monotonic_seconds", "backend_cpu_seconds", "heap_bytes"]
)
def test_nonfinite_resource_measurements_are_rejected(field):
    rows = samples()
    rows[0][field] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        summarize_phase(rows, metadata())


@pytest.mark.parametrize(
    "field", ["hardware", "fixture", "window_seconds", "viewers", "renderer", "gc_mode"]
)
def test_incomparable_baseline_is_incomplete(field):
    reference = deepcopy(baseline())
    reference["metadata"][field] = "different"
    gates = evaluate_budgets(reference, report())
    assert gates["budgets"]["cpu_increase"]["status"] == "incomplete"
    assert gates["status"] == "incomplete"


@pytest.mark.parametrize(
    "key", ["images", "hardware", "sha", "behavior", "cleanup", "upstream_work"]
)
def test_missing_provenance_or_control_cannot_pass(key):
    meta = metadata()
    del meta[key]
    result = summarize_phase(samples(), meta)
    assert evaluate_budgets(baseline(), result)["status"] == "incomplete"


def test_failed_cleanup_or_behavior_is_failed():
    result = summarize_phase(samples(), metadata(cleanup="failed"))
    assert evaluate_budgets(baseline(), result)["status"] == "failed"
    behaviors = {name: "passed" for name in BEHAVIORS}
    behaviors["motion"] = "failed"
    result = summarize_phase(samples(), metadata(behavior=behaviors))
    assert evaluate_budgets(baseline(), result)["status"] == "failed"


def test_missing_gc_or_sampling_gap_is_incomplete():
    rows = samples()
    for row in rows:
        row.pop("post_gc_heap_bytes", None)
    assert (
        evaluate_budgets(baseline(), summarize_phase(rows, metadata()))["status"]
        == "incomplete"
    )
    rows = [
        row for row in samples() if row.get("monotonic_seconds") not in range(10, 100)
    ]
    assert (
        evaluate_budgets(baseline(), summarize_phase(rows, metadata()))["status"]
        == "incomplete"
    )


def test_errors_and_negative_request_duration_are_not_healthy():
    rows = samples()
    rows[-1]["status"] = 503
    assert (
        evaluate_budgets(baseline(), summarize_phase(rows, metadata()))["status"]
        == "failed"
    )
    rows[-1]["completed_seconds"] = rows[-1]["started_seconds"] - 1
    with pytest.raises(ValueError, match="request"):
        summarize_phase(rows, metadata())


def test_cold_requests_do_not_enter_warm_quantiles():
    rows = samples()
    rows.append(
        {
            "kind": "request",
            "started_seconds": 1,
            "completed_seconds": 3,
            "status": 200,
            "page_id": "one",
            "cold": True,
        }
    )
    assert summarize_phase(rows, metadata())["request_ms"]["p95"] == pytest.approx(499)
