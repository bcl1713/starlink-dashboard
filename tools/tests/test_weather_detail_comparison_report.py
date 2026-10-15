"""Measurements and comparable actual data are required before recommendations."""

from copy import deepcopy

import pytest
from acceptance.weather_detail_comparison.report import summarize


def evidence():
    rows = []
    for region in ("mrms", "opera"):
        for source in ("rainviewer", region):
            rows.append(
                {
                    "source": source,
                    "region": region,
                    "view": "desktop",
                    "night": False,
                    "level": 6,
                    "opacity": 0.4,
                    "precipitationPresent": True,
                    "renderer": "same native renderer",
                    "camera": [1] * 16,
                    "projection": [1] * 16,
                    "drawingBuffer": [1920, 1080],
                    "viewport": [1920, 1080],
                    "cacheState": "same cache state",
                    "frameMilliseconds": [1.0, 2.0, 3.0],
                    "pngRequests": 48,
                    "pngBytes": 100000,
                    "fetchMilliseconds": 100.0,
                    "decodeMilliseconds": 50.0,
                    "uploadMilliseconds": 25.0,
                    "weatherGPUBytes": 48 * 1024**2,
                    "ownedDecodedPeakBytes": 81 * 1024**2,
                }
            )
    rows = [
        dict(row, view=view, night=night, level=level, opacity=opacity)
        for row in rows
        for view in ("desktop", "fullscreen", "mobile")
        for night in (False, True)
        for level, opacity in (
            [(2, 0.72), (6, 0.4), (5, 0.4), (7, 0.4), (6, 0.35), (6, 0.45)]
            if view == "desktop"
            else [(2, 0.72), (6, 0.4)]
        )
    ]
    return {
        "browser": {
            "sha": "a" * 40,
            "mode": "offline actual-source replay with test-only detail shader",
            "hashValidation": "passed",
            "synthesis": False,
            "records": rows,
            "requests": [{"status": 200}],
        },
        "generation": {
            source: {
                "status": "measured",
                "input_bytes": 1000000,
                "output_bytes": 200000,
                "cold": {
                    "wall_seconds": 1.0,
                    "cpu_seconds": 1.0,
                    "peak_rss_bytes": 640000000,
                },
                "warm": {
                    "wall_seconds": 2.0,
                    "cpu_seconds": 2.0,
                    "peak_rss_bytes": 640000000,
                },
            }
            for source in ("mrms", "opera")
        },
        "comparisons": [
            {"source": source, "delta_seconds": 0} for source in ("mrms", "opera")
        ],
        "cleanup": {"status": "passed"},
        "process_cleanup": {"status": "passed"},
    }


def test_complete_evidence_reports_costs_without_claiming_production_implementation():
    result = summarize(evidence())
    assert result["status"] == "complete"
    assert result["production_refinement_verified"] is False
    assert (
        result["sources"]["mrms"]["generation"]["cold"]["peak_rss_bytes"] == 640000000
    )
    assert result["recommendation"]["source"] == "rainviewer"


@pytest.mark.parametrize("field", ["peak_rss_bytes", "wall_seconds", "cpu_seconds"])
def test_missing_peak_rss_is_inconclusive(field):
    data = evidence()
    del data["generation"]["mrms"]["cold"][field]
    assert summarize(data)["status"] == "inconclusive"


@pytest.mark.parametrize(
    "field",
    ["renderer", "camera", "projection", "cacheState", "drawingBuffer", "viewport"],
)
def test_different_renderer_is_inconclusive(field):
    data = evidence()
    data["browser"]["records"][1][field] = "different"
    assert summarize(data)["status"] == "inconclusive"


def test_failed_cleanup_is_inconclusive():
    data = evidence()
    data["cleanup"]["status"] = "failed"
    assert summarize(data)["status"] == "inconclusive"


def test_clear_capture_cannot_prove_detail():
    data = evidence()
    for row in data["browser"]["records"]:
        row["precipitationPresent"] = False
    assert summarize(data)["status"] == "inconclusive"


def test_mismatched_timestamps_are_inconclusive():
    data = evidence()
    data["comparisons"][0]["delta_seconds"] = 301
    assert summarize(data)["status"] == "inconclusive"


def test_missing_mobile_and_night_samples_are_inconclusive():
    data = evidence()
    data["browser"]["records"] = [
        r
        for r in data["browser"]["records"]
        if r["view"] == "desktop" and not r["night"]
    ]
    assert summarize(data)["status"] == "inconclusive"


def test_null_timestamp_is_inconclusive():
    data = evidence()
    data["comparisons"][0]["delta_seconds"] = None
    assert summarize(data)["status"] == "inconclusive"


@pytest.mark.parametrize(
    "field,value", [("hashValidation", "failed"), ("synthesis", True), ("sha", "dev")]
)
def test_unverified_or_synthetic_data_cannot_claim_provider_quality(field, value):
    data = evidence()
    data["browser"][field] = value
    assert summarize(data)["status"] == "inconclusive"


def test_missing_matching_row_is_inconclusive():
    data = evidence()
    data["browser"]["records"].pop()
    assert summarize(data)["status"] == "inconclusive"


def test_measurements_are_not_mutated():
    data = evidence()
    before = deepcopy(data)
    summarize(data)
    assert data == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("weatherGPUBytes", 49 * 1024**2),
        ("ownedDecodedPeakBytes", 97 * 1024**2),
        ("decodeMilliseconds", float("nan")),
    ],
)
def test_invalid_resources_are_inconclusive(field, value):
    data = evidence()
    data["browser"]["records"][0][field] = value
    assert summarize(data)["status"] == "inconclusive"


def test_failed_shader_restoration_is_inconclusive():
    data = evidence()
    data["browser"]["restoreFailure"] = "disposed material was not restored"
    assert summarize(data)["status"] == "inconclusive"


def test_baseline_only_comparison_is_inconclusive():
    data = evidence()
    data["browser"]["records"] = [
        dict(row, level=2, opacity=0.72) for row in data["browser"]["records"]
    ]
    assert summarize(data)["status"] == "inconclusive"


def test_duplicate_variant_rows_are_inconclusive():
    data = evidence()
    data["browser"]["records"].append(deepcopy(data["browser"]["records"][0]))
    assert summarize(data)["status"] == "inconclusive"
