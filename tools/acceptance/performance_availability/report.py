"""Retain strict comparison guards and reject cross-contract comparisons."""

from acceptance.performance.report import compare as strict_compare
from acceptance.performance.report import summarize as strict_summarize

VERSION = "perf390-availability-v2"


def summarize(metadata, rows):
    if metadata.get("availability_contract") != VERSION:
        raise ValueError("Missing availability contract version")
    return strict_summarize(metadata, rows)


def compare(baseline, candidate):
    for item in (baseline, candidate):
        if item["metadata"].get("availability_contract") != VERSION:
            raise ValueError(
                "Incompatible availability contract; strict cohort is separate"
            )
    if not baseline["metadata"].get("harness_files_sha256"):
        raise ValueError("Missing harness sources")
    if baseline["metadata"].get("harness_files_sha256") != candidate["metadata"].get(
        "harness_files_sha256"
    ):
        raise ValueError("Incompatible harness sources")
    return strict_compare(baseline, candidate)
