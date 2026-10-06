"""Reject incomplete or incomparable research before proposing source changes."""

import argparse
import json
import math
import re
import statistics
from pathlib import Path

MIB = 1024**2


def number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def finite(value):
    return number(value) and value >= 0


def summarize(evidence: dict) -> dict:
    problems = []
    browser = evidence.get("browser", {})
    if not re.fullmatch("[a-f0-9]{40}", browser.get("sha", "")):
        problems.append("Exact candidate SHA missing")
    if (
        browser.get("hashValidation") != "passed"
        or browser.get("synthesis") is not False
    ):
        problems.append("Actual capture hashes/provenance unverified")
    if not browser.get("mode", "").startswith("offline actual-source replay"):
        problems.append("Actual-source replay label missing")
    if browser.get("restoreFailure"):
        problems.append("Native shader restoration failed")
    for field in ("cleanup", "process_cleanup"):
        if evidence.get(field, {}).get("status") != "passed":
            problems.append(f"{field} failed or unverified")
    comparisons = evidence.get("comparisons", [])
    if {c.get("source") for c in comparisons} != {"mrms", "opera"}:
        problems.append("Both raw source comparisons required")
    if any(
        not number(c.get("delta_seconds")) or abs(c["delta_seconds"]) > 300
        for c in comparisons
    ):
        problems.append("Observation times exceed five-minute matching window")
    sources = {}
    for source in ("mrms", "opera"):
        generation = evidence.get("generation", {}).get(source, {})
        if generation.get("status") != "measured":
            problems.append(f"{source}: generation not measured")
        for phase in ("cold", "warm"):
            values = generation.get(phase, {})
            if any(
                not finite(values.get(field))
                for field in ("wall_seconds", "cpu_seconds", "peak_rss_bytes")
            ):
                problems.append(f"{source}: incomplete {phase} costs")
            elif values["peak_rss_bytes"] > 2 * 1024 * MIB:
                problems.append(f"{source}: research RAM ceiling exceeded")
        sources[source] = {"generation": generation}
    records = browser.get("records", [])
    if not records or not all(
        row.get("precipitationPresent") is True for row in records
    ):
        problems.append("Precipitation-bearing regions missing")
    expected_views = {
        (view, night)
        for view in ("desktop", "fullscreen", "mobile")
        for night in (False, True)
    }
    for region in ("mrms", "opera"):
        actual_views = {
            (r.get("view"), r.get("night"))
            for r in records
            if r.get("region") == region
        }
        if actual_views != expected_views:
            problems.append(
                f"{region}: desktop/fullscreen/mobile day/night coverage incomplete"
            )
    numeric = (
        "pngRequests",
        "pngBytes",
        "fetchMilliseconds",
        "decodeMilliseconds",
        "uploadMilliseconds",
        "weatherGPUBytes",
        "ownedDecodedPeakBytes",
    )
    groups = {}
    for row in records:
        if any(not finite(row.get(field)) for field in numeric):
            problems.append("Browser measurements missing/non-finite")
            continue
        if row["weatherGPUBytes"] > 48 * MIB or row["ownedDecodedPeakBytes"] > 96 * MIB:
            problems.append("Browser weather allocation ceiling exceeded")
        times = row.get("frameMilliseconds", [])
        if not times or not all(finite(v) for v in times):
            problems.append("Native frame samples missing/non-finite")
        key = tuple(
            row.get(field) for field in ("region", "view", "night", "level", "opacity")
        )
        groups.setdefault(key, {})[row.get("source")] = row
    conditions = (
        "renderer",
        "camera",
        "projection",
        "drawingBuffer",
        "viewport",
        "cacheState",
    )
    for key, pair in groups.items():
        region = key[0]
        if set(pair) != {"rainviewer", region}:
            problems.append(f"{region}: matching source row missing")
            continue
        left, right = pair["rainviewer"], pair[region]
        if any(
            left.get(field) is None or left.get(field) != right.get(field)
            for field in conditions
        ):
            problems.append(f"{region}: renderer/camera/viewport/cache differ")
    if not browser.get("requests") or any(
        r.get("status") != 200 for r in browser.get("requests", [])
    ):
        problems.append("Browser asset acquisition incomplete")
    for source in ("rainviewer", "mrms", "opera"):
        rows = [row for row in records if row.get("source") == source]
        samples = [
            t for row in rows for t in row.get("frameMilliseconds", []) if finite(t)
        ]
        sources.setdefault(source, {})["browser"] = {
            "views": len(rows),
            "png_requests": sum(row.get("pngRequests", 0) for row in rows),
            "decoded_png_bytes": sum(row.get("pngBytes", 0) for row in rows),
            "median_manual_frame_ms": statistics.median(samples) if samples else None,
        }
    status = "inconclusive" if problems else "complete"
    return {
        "status": status,
        "problems": sorted(set(problems)),
        "sha": browser.get("sha"),
        "production_refinement_verified": False,
        "sources": sources,
        "recommendation": {
            "source": "rainviewer" if status == "complete" else None,
            "reason": "Preserves international observed coverage without introducing recurring fees or a new ingest service; raw regional generation alone is not a worldwide replacement.",
        },
        "limitations": [
            "Offline test-only shader replay does not verify production scheduling/lifecycle.",
            "Raw RSS is a combined-process high-water mark, not independent per-source RSS.",
            "Observation times may differ by up to five minutes; colors are not equivalent quantitative scales.",
            "Manual frame timings are small samples on the recorded renderer, not user-device benchmarks.",
            "Opacity and added geographic features require inspection of recorded views.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()

    def read(path):
        return json.loads(path.read_text())

    result = summarize(
        {
            "browser": read(args.run / "browser/comparison.json"),
            "generation": read(args.capture / "generation.json"),
            "comparisons": read(args.capture / "capture.json")["metadata"][
                "comparisons"
            ],
            "cleanup": read(args.run / "cleanup.json"),
            "process_cleanup": read(args.run / "process-cleanup.json"),
        }
    )
    (args.run / "source-comparison-report.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))
