"""Independent conservative ID joins and evidence-layer classification."""

import itertools
import math
from collections import defaultdict
from itertools import pairwise

from .model import validate

PAIRS = {
    "producer_queue": ("producer.dispatch", "producer.start"),
    "producer_acquisition": ("producer.start", "producer.collected"),
    "producer_publication": ("producer.collected", "producer.published"),
    "producer_tick": ("producer.start", "producer.end"),
    "producer_completion": ("producer.end", "producer.returned"),
    "worker_queue": ("worker.dispatch", "worker.start"),
    "worker_service": ("worker.start", "worker.end"),
    "worker_completion": ("worker.end", "worker.returned"),
    "asgi": ("asgi.entry", "asgi.end"),
    "observer_wake": ("observer.scheduled", "observer.wake"),
    "observer_send": ("observer.wake", "observer.send"),
    "observer_http": ("observer.send", "observer.received"),
    "observer_parse": ("observer.received", "observer.parsed"),
    "observer_write": ("observer.parsed", "observer.written"),
    "refresh": ("refresh.start", "refresh.end"),
    "browser_http": ("browser.request", "browser.end"),
    "browser_body_delivery": ("browser.end", "browser.body"),
}


def duration(rows, start, end):
    a = [r for r in rows if r["data"]["name"] == start]
    b = [r for r in rows if r["data"]["name"] == end]
    reason = None
    if len(a) != 1 or len(b) != 1:
        reason = "missing_boundary" if not a or not b else "ambiguous_boundary"
    elif a[0]["clock_id"] != b[0]["clock_id"]:
        reason = "clock_domain_mismatch"
    elif int(b[0]["mono_ns"]) < int(a[0]["mono_ns"]):
        reason = "negative_duration"
    return {
        "value_ns": None if reason else int(b[0]["mono_ns"]) - int(a[0]["mono_ns"]),
        "reason": reason,
        "clock_id": None if reason else a[0]["clock_id"],
        "thread_cpu_ns": (
            int(b[0]["thread_cpu_ns"]) - int(a[0]["thread_cpu_ns"])
            if not reason
            and a[0]["pid"] == b[0]["pid"]
            and a[0]["tid"] == b[0]["tid"]
            and a[0]["thread_cpu_ns"] is not None
            and b[0]["thread_cpu_ns"] is not None
            and int(b[0]["thread_cpu_ns"]) >= int(a[0]["thread_cpu_ns"])
            else None
        ),
    }


def distribution(values):
    if not values:
        return {"count": 0, "p50": None, "p95": None, "p99": None, "max": None}
    values = sorted(values)
    return {
        "count": len(values),
        **{
            name: values[math.ceil(len(values) * p) - 1]
            for name, p in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1)]
        },
    }


def projection(bundle, metric):
    raw = dict(bundle["series"].get(metric, []))
    rollup = bundle.get("rolling_5m", {}).get(metric, {})
    maps = {"observed": raw}
    for name in ("min", "avg", "max"):
        maps[name] = (
            dict(rollup.get(name, [])) if rollup.get("state") == "available" else {}
        )
    times = sorted({t for values in maps.values() for t in values})
    grid = []
    for t in times:
        if grid and t - grid[-1] > bundle["step"] * 1.5:
            grid.append((t + grid[-1]) / 2)
        grid.append(t)
    return grid, {
        k: [v.get(t) if t in raw else None for t in grid] for k, v in maps.items()
    }


def gap_intervals(times, values, viewport):
    # A null sample breaks both adjacent segments with spanGaps:false.
    result = []
    for i in range(1, len(times)):
        if values[i - 1] is None or values[i] is None:
            lo, hi = max(times[i - 1], viewport[0]), min(times[i], viewport[1])
            if hi > lo:
                if result and result[-1][1] == lo:
                    result[-1][1] = hi
                else:
                    result.append([lo, hi])
    return result


def analyze(rows):
    for row in rows:
        validate(row)
    run_ids = {r["run_id"] for r in rows}
    if len(run_ids) > 1:
        raise ValueError("analyze one run at a time; IDs are run scoped")
    seen = set()
    issues = []
    for row in rows:
        key = row["stream_id"], row["seq"]
        if key in seen:
            issues.append("duplicate_stream_sequence")
        seen.add(key)
    boundaries = defaultdict(list)
    for row in rows:
        if row["kind"] == "boundary" and row["op_id"]:
            boundaries[row["op_id"]].append(row)
    operations = {
        op: {k: duration(events, *pair) for k, pair in PAIRS.items()}
        for op, events in boundaries.items()
    }
    admissions = []
    for op, events in boundaries.items():
        spans = {
            e["span_id"]
            for e in events
            if e["data"]["name"].startswith("repo.") and e["span_id"]
        }
        for span in sorted(spans):
            selected = [e for e in events if e["span_id"] == span]
            admissions.append(
                {
                    "op_id": op,
                    "span_id": span,
                    "wait": duration(selected, "repo.wait", "repo.acquired"),
                    "hold": duration(selected, "repo.acquired", "repo.released"),
                }
            )
    anchors = defaultdict(list)
    for row in rows:
        if row["kind"] == "anchor":
            anchors[row["clock_id"]].append(row)
    adjustments = []
    for clock, events in anchors.items():
        ordered = sorted(events, key=lambda e: int(e["mono_ns"]))
        for a, b in itertools.pairwise(ordered):
            delta = (
                int(b["data"]["utc_ns"])
                - int(a["data"]["utc_ns"])
                - (int(b["mono_ns"]) - int(a["mono_ns"]))
            )
            adjustments.append(
                {
                    "clock_id": clock,
                    "offset_change_ns": delta,
                    "uncertainty_ns": int(a["data"].get("uncertainty_ns", "0"))
                    + int(b["data"].get("uncertainty_ns", "0")),
                }
            )
    histories = defaultdict(list)
    scrapes = defaultdict(list)
    evaluations = defaultdict(list)
    for row in rows:
        data = row["data"]
        if row["kind"] == "history":
            histories[
                (data["viewer"], data["request_id"], data["bundle_id"], data["segment"])
            ].append(data)
        if row["kind"] == "scrape":
            scrapes[(data["series"], data["segment"])].append(data)
        if row["kind"] == "evaluation":
            evaluations[(data["series"], data["segment"])].append(data)
    charts, unique_missing = [], set()
    viewer_end = {}
    for row in rows:
        if row["kind"] != "chart":
            continue
        c = row["data"]
        metric, segment = c["series"], c["segment"]
        matches = histories[
            (c["viewer"], c["request_id"], c["bundle_id"], c["segment"])
        ]
        entry = {
            "viewer": c["viewer"],
            "request_id": c["request_id"],
            "bundle_id": c["bundle_id"],
            "series": metric,
            "segment": segment,
            "classification": "unknown",
            "unavailable": [],
            "findings": [],
        }
        charts.append(entry)
        if len(matches) != 1:
            entry["unavailable"].append("missing_or_ambiguous_response_body")
            continue
        h = matches[0]
        if (
            h["step"] <= 0
            or h["end"] < h["start"]
            or (h["end"] - h["start"]) / h["step"] > 100000
        ):
            raise ValueError("invalid or excessive history grid")
        samples = h["series"].get(metric, [])
        stamps = [t for t, v in samples]
        grid = [
            h["start"] + i * h["step"]
            for i in range(round((h["end"] - h["start"]) / h["step"]) + 1)
        ]
        missing = sorted(set(grid) - set(stamps))
        for t in missing:
            unique_missing.add((metric, segment, t))
        entry["api_missing_slots"] = missing
        longest = current = 0
        missing_set = set(missing)
        for coordinate in grid:
            current = current + 1 if coordinate in missing_set else 0
            longest = max(longest, current)
        entry["longest_api_missing_seconds"] = longest * h["step"]
        entry["rollup_state"] = (
            h.get("rolling_5m", {}).get(metric, {}).get("state", "unavailable")
        )
        entry["duplicate_timestamps"] = len(stamps) - len(set(stamps))
        entry["shifted_timestamps"] = sorted(set(stamps) - set(grid))
        entry["timestamp_errors_seconds"] = [
            b - a - h["step"] for a, b in itertools.pairwise(stamps)
        ]
        projection_input = c.get("projection_input", h)
        can_compare_plot = c.get("input_stage") != "plot" or "projection_input" in c
        if not can_compare_plot:
            entry["unavailable"].append("retained_projection_input")
        expected_times, expected_traces = projection(projection_input, metric)
        if c.get("input_stage") == "plot" and c.get("log_floor") is not None:
            expected_traces = {
                k: [None if v is None else max(c["log_floor"], v) for v in values]
                for k, values in expected_traces.items()
            }
        entry["null_gaps"] = {
            k: gap_intervals(c["times"], v, c["viewport"])
            for k, v in c["traces"].items()
        }
        entry["visible_gap_seconds"] = (
            None
            if c["visible_gaps"] is None
            else sum(
                max(0, min(hi, c["viewport"][1]) - max(lo, c["viewport"][0]))
                for lo, hi in c["visible_gaps"]
            )
        )
        entry["visible_fraction"] = (
            None
            if entry["visible_gap_seconds"] is None
            or c["viewport"][1] <= c["viewport"][0]
            else entry["visible_gap_seconds"] / (c["viewport"][1] - c["viewport"][0])
        )
        key = c["viewer"], metric, segment
        previous = viewer_end.get(key)
        stale = previous is not None and h["end"] < previous
        viewer_end[key] = max(previous or h["end"], h["end"])
        source_id = h.get("source_id")
        all_store = [
            s
            for s in scrapes[(metric, segment)]
            if source_id and s.get("source_id") == source_id
        ]
        store = [s for s in all_store if h["start"] <= s["timestamp"] <= h["end"]]
        stored_times = sorted({s["timestamp"] for s in store})
        actual_gap = any(s["state"] != "finite" for s in store)
        entry["stored_timing_gaps_seconds"] = [
            b - a for a, b in itertools.pairwise(stored_times) if b - a > 1.25
        ]
        if not store:
            entry["unavailable"].append("stored_sample_provenance")
        if not source_id:
            entry["unavailable"].append("source_identity")
        stored_coverage = (
            bool(store)
            and stored_times[0] <= h["start"] + 1.25
            and stored_times[-1] >= h["end"] - 1.25
            and not entry["stored_timing_gaps_seconds"]
            and len(stored_times) >= max(1, math.floor(h["end"] - h["start"]) - 1)
        )
        if not stored_coverage:
            entry["unavailable"].append("stored_window_coverage")
        ev = [
            e
            for e in evaluations[(metric, segment)]
            if e["start"] == h["start"]
            and e["end"] == h["end"]
            and e["step"] == h["step"]
            and source_id
            and e.get("source_id") == source_id
            and h.get("evaluation_id")
            and e.get("evaluation_id") == h["evaluation_id"]
            and e.get("viewer") == h["viewer"]
            and e.get("request_id") == h["request_id"]
            and e.get("bundle_id") == h["bundle_id"]
        ]
        api_defect = False
        if len(ev) == 1:
            finite = [
                [t, v] for t, v in zip(ev[0]["times"], ev[0]["values"]) if v is not None
            ]
            api_defect = finite != samples
            by_stamp = {s["timestamp"]: s for s in all_store}
            provenance = all(
                v is None
                or (
                    sample is not None
                    and t - 1.25 <= sample <= t
                    and sample in by_stamp
                    and by_stamp[sample]["state"] == "finite"
                    and by_stamp[sample]["value"] == v
                )
                for t, v, sample in zip(
                    ev[0]["times"], ev[0]["values"], ev[0]["sample_timestamps"]
                )
            )
            if not provenance:
                entry["unavailable"].append("evaluation_sample_provenance")
        else:
            entry["unavailable"].append("exact_evaluation_grid")
        if not c["module_hashes"]:
            entry["unavailable"].append("plot_module_hashes")
        if c["visible_gaps"] is None or not c["paint_evidence"]:
            entry["unavailable"].append("paint")
        if stale:
            entry["classification"] = "out_of_order_bundle"
        elif api_defect:
            entry["classification"] = "history_projection_gap"
        elif entry["duplicate_timestamps"] or entry["shifted_timestamps"]:
            entry["classification"] = "history_timestamp_defect"
        elif can_compare_plot and (
            expected_times != c["times"] or expected_traces != c["traces"]
        ):
            entry["classification"] = "frontend_data_path_gap"
        elif missing or actual_gap:
            entry["classification"] = (
                "network_data_gap" if actual_gap else "upstream_gap_unknown_origin"
            )
        elif c["visible_gaps"] and not entry["unavailable"]:
            entry["classification"] = "frontend_rendering_gap"
        elif not entry["unavailable"]:
            entry["classification"] = "complete"
        entry["findings"] = [s["state"] for s in store if s["state"] != "finite"]
        if actual_gap and not missing:
            entry["findings"].append("finite_query_values_do_not_prove_fresh_scrapes")
    resource_deltas = []
    previous_resources = {}
    for row in rows:
        if row["kind"] != "resource":
            continue
        for path, measurement in row["data"]["files"].items():
            if not path.endswith("cpu.stat") or measurement["value"] is None:
                continue
            try:
                counters = {
                    k: int(v)
                    for k, v in (
                        line.split() for line in measurement["value"].splitlines()
                    )
                }
            except (ValueError, TypeError):
                continue
            key = row["clock_id"], path
            previous = previous_resources.get(key)
            if previous:
                ns, old = previous
                delta = {k: v - old[k] for k, v in counters.items() if k in old}
                reason = (
                    "counter_reset_or_nonmonotonic_sample"
                    if int(row["mono_ns"]) <= ns or any(v < 0 for v in delta.values())
                    else None
                )
                resource_deltas.append(
                    {
                        "clock_id": row["clock_id"],
                        "path": path,
                        "interval_ns": int(row["mono_ns"]) - ns,
                        "delta": None if reason else delta,
                        "reason": reason,
                    }
                )
            previous_resources[key] = int(row["mono_ns"]), counters
    scrape_timing = {}
    for (metric, segment), events in scrapes.items():
        stamps = sorted({r["timestamp"] for r in events})
        intervals = [b - a for a, b in itertools.pairwise(stamps)]
        scrape_timing[metric + "/" + segment] = {
            "count": len(stamps),
            "interval_seconds": distribution(intervals),
            "signed_error_seconds": distribution([v - 1 for v in intervals]),
            "absolute_error_seconds": distribution([abs(v - 1) for v in intervals]),
            "over_1_25_seconds": sum(v > 1.25 for v in intervals),
            "unavailable_samples": sum(e["state"] != "finite" for e in events),
        }
    drops = sum(
        r["data"]["dropped_events"] + r["data"]["dropped_bodies"]
        for r in rows
        if r["kind"] == "summary"
    )
    streams = {r["stream_id"] for r in rows}
    summarized = {r["stream_id"] for r in rows if r["kind"] == "summary"}
    missing_summaries = sorted(streams - summarized)
    if missing_summaries or not rows:
        issues.append("missing_stream_summary")
    for stream in summarized:
        selected = [r for r in rows if r["stream_id"] == stream]
        if (
            len([r for r in selected if r["kind"] == "summary"]) != 1
            or max(selected, key=lambda r: r["seq"])["kind"] != "summary"
        ):
            issues.append("invalid_stream_summary")
    for stream in streams:
        selected = [r for r in rows if r["stream_id"] == stream]
        sequences = sorted({r["seq"] for r in selected})
        holes = max(0, sequences[0] - 1) + sum(
            b - a - 1 for a, b in pairwise(sequences)
        )
        declared = sum(
            r["data"]["dropped_events"] for r in selected if r["kind"] == "summary"
        )
        if holes > declared:
            issues.append("unaccounted_sequence_gap")
    if drops:
        issues.append("collection_loss")
    return {
        "schema": "perf391-network-evidence-analysis-v1",
        "acceptance": "not_evaluated",
        "issues": sorted(set(issues)),
        "dropped": (
            None
            if missing_summaries
            or not rows
            or "unaccounted_sequence_gap" in issues
            or "invalid_stream_summary" in issues
            else drops
        ),
        "observed_dropped": drops,
        "missing_stream_summaries": missing_summaries,
        "operations": operations,
        "admissions": admissions,
        "clock_adjustments": adjustments,
        "charts": charts,
        "unique_api_missing_slots": len(unique_missing),
        "resource_deltas": resource_deltas,
        "scrape_timing": scrape_timing,
        "coverage": [r["data"] for r in rows if r["kind"] == "coverage"],
        "summary_present": any(r["kind"] == "summary" for r in rows),
        "timing_distributions_ns": {
            k: distribution(
                [
                    op[k]["value_ns"]
                    for op in operations.values()
                    if op[k]["value_ns"] is not None
                ]
            )
            for k in PAIRS
        },
    }


def human(result):
    lines = [
        "perf391-network-evidence-v1 supplemental analysis",
        "Frozen acceptance: not evaluated",
        f"Collection loss: {result['dropped'] if result['dropped'] is not None else 'unknown'} (observed drops {result['observed_dropped']}); issues: {', '.join(result['issues']) or 'none'}",
        f"Operations: {len(result['operations'])}; chart observations: {len(result['charts'])}",
    ]
    for op, values in result["operations"].items():
        lines.append(
            op
            + ": "
            + ", ".join(
                (
                    f"{k}={v['value_ns']} ns"
                    if v["value_ns"] is not None
                    else f"{k}=unavailable ({v['reason']})"
                )
                for k, v in values.items()
            )
        )
    for chart in result["charts"]:
        lines.append(
            f"{chart['viewer']}/{chart['series']}/{chart['bundle_id']}: {chart['classification']}; unavailable={','.join(chart['unavailable']) or 'none'}"
        )
    return "\n".join(lines) + "\n"
