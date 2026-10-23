"""Deterministic fictional fixtures. Never import the analyzer as an oracle."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parent
METRIC = "starlink_network_latency_ms_current"


def ev(kind, data, ns=0, op=None, span=None):
    return {
        "schema": "perf391-network-evidence-v1",
        "version": 1,
        "kind": kind,
        "run_id": "fictional-fixture",
        "stream_id": "fixture",
        "seq": 0,
        "clock_id": "fictional-process",
        "mono_ns": str(ns),
        "pid": 0,
        "tid": 0,
        "thread_cpu_ns": None,
        "op_id": op,
        "span_id": span,
        "data": data,
    }


def chart_case(name, missing=None, values=None):
    times = [100, 101, 102, 103]
    values = values or [0, 2, 9, 1]
    pairs = [[t, v] for t, v in zip(times, values) if t != missing]
    shown = [t for t, v in pairs]
    if missing == 101:
        shown.insert(1, 101)
    raw = [dict(pairs).get(t) for t in shown]
    traces = {
        "observed": raw,
        "min": [None] * len(raw),
        "avg": [None] * len(raw),
        "max": [None] * len(raw),
    }
    history = ev(
        "history",
        {
            "viewer": "overview-1",
            "request_id": "poll-1",
            "bundle_id": "b1",
            "start": 100,
            "end": 103,
            "step": 1,
            "series": {METRIC: pairs},
            "segment": "measured",
        },
    )
    chart = ev(
        "chart",
        {
            "viewer": "overview-1",
            "request_id": "poll-1",
            "bundle_id": "b1",
            "series": METRIC,
            "segment": "measured",
            "times": shown,
            "traces": traces,
            "viewport": [100, 103],
            "visible_gaps": [] if missing is None else [[100, 102]],
            "module_hashes": {"plot": "fictional-module-sha256"},
            "paint_evidence": "fictional-paint-attestation",
        },
    )
    evaluation = ev(
        "evaluation",
        {
            "series": METRIC,
            "segment": "measured",
            "start": 100,
            "end": 103,
            "step": 1,
            "times": times,
            "values": [v if t != missing else None for t, v in zip(times, values)],
            "sample_timestamps": [t if t != missing else None for t in times],
        },
    )
    scrapes = [
        ev(
            "scrape",
            {
                "series": METRIC,
                "timestamp": t,
                "value": None if t == missing else v,
                "state": "missing" if t == missing else "finite",
                "segment": "measured",
                "up": 0 if t == missing else 1,
                "sample_count": None if t == missing else 11,
                "scrape_duration_seconds": None if t == missing else 0.001,
            },
        )
        for t, v in zip(times, values)
    ]
    history["data"].update(source_id="fictional-source", evaluation_id="eval-poll1")
    evaluation["data"].update(
        source_id="fictional-source",
        evaluation_id="eval-poll1",
        viewer="overview-1",
        request_id="poll-1",
        bundle_id="b1",
    )
    for r in scrapes:
        r["data"]["source_id"] = "fictional-source"
    return {
        "name": name,
        "events": [history, evaluation, *scrapes, chart],
        "expected": ["complete"],
    }


cases = []
cases.append(chart_case("complete_zero_spike"))
c = chart_case("missing_scrape", 101)
c["expected"] = ["network_data_gap"]
cases.append(c)
c = copy.deepcopy(c)
c["name"] = "explicit_nan"
c["events"][3]["data"]["state"] = "nan"
cases.append(c)
c = chart_case("api_deletion", 101)
c["events"][1]["data"]["values"] = [0, 2, 9, 1]
c["expected"] = ["history_projection_gap"]
cases.append(c)
c = chart_case("timestamp_shift")
c["events"][0]["data"]["series"][METRIC][1][0] = 101.2
c["events"] = [r for r in c["events"] if r["kind"] != "evaluation"]
c["expected"] = ["history_timestamp_defect"]
cases.append(c)
c = chart_case("frontend_only_rendering_gap")
c["events"][-1]["data"]["visible_gaps"] = [[101, 102]]
c["expected"] = ["frontend_rendering_gap"]
cases.append(c)
c = chart_case("frontend_only_input_gap")
c["events"][-1]["data"]["traces"]["observed"][1] = None
c["expected"] = ["frontend_data_path_gap"]
cases.append(c)
c = chart_case("missing_paint")
c["events"][-1]["data"]["visible_gaps"] = None
c["events"][-1]["data"]["paint_evidence"] = None
c["expected"] = ["unknown"]
cases.append(c)
c = chart_case("finite_lookback_over_missing_scrape")
c["events"][3]["data"].update(state="missing", value=None)
c["expected"] = ["network_data_gap"]
cases.append(c)
c = chart_case("out_of_order_history_responses")
old = copy.deepcopy(c["events"][0])
old["data"].update(request_id="poll-older", bundle_id="older", start=99, end=102)
old["data"]["series"][METRIC] = [[99, 1], [100, 0], [101, 2], [102, 9]]
oldchart = copy.deepcopy(c["events"][-1])
oldchart["data"].update(
    request_id="poll-older",
    bundle_id="older",
    times=[99, 100, 101, 102],
    viewport=[99, 102],
    traces={
        "observed": [1, 0, 2, 9],
        "min": [None] * 4,
        "avg": [None] * 4,
        "max": [None] * 4,
    },
)
c["events"].extend([old, oldchart])
c["expected"] = ["complete", "out_of_order_bundle"]
cases.append(c)
for name, bounds, expected in [
    (
        "delayed_observer",
        [
            ("observer.scheduled", 0),
            ("observer.wake", 700000000),
            ("observer.send", 710000000),
            ("observer.received", 720000000),
        ],
        {"observer_wake": 700000000, "observer_http": 10000000},
    ),
    (
        "backend_queue",
        [
            ("worker.dispatch", 0),
            ("worker.start", 200000000),
            ("worker.end", 201000000),
            ("worker.returned", 202000000),
        ],
        {
            "worker_queue": 200000000,
            "worker_service": 1000000,
            "worker_completion": 1000000,
        },
    ),
    (
        "worker_completion",
        [
            ("worker.dispatch", 0),
            ("worker.start", 1000000),
            ("worker.end", 2000000),
            ("worker.returned", 502000000),
        ],
        {"worker_completion": 500000000},
    ),
    (
        "producer_acquisition_publication",
        [
            ("producer.dispatch", 0),
            ("producer.start", 1000000),
            ("producer.collected", 301000000),
            ("producer.validated", 302000000),
            ("producer.published", 501000000),
            ("producer.end", 502000000),
            ("producer.returned", 802000000),
        ],
        {
            "producer_acquisition": 300000000,
            "producer_publication": 200000000,
            "producer_completion": 300000000,
        },
    ),
]:
    cases.append(
        {
            "name": name,
            "events": [ev("boundary", {"name": k}, ns, "r1") for k, ns in bounds],
            "durations": expected,
        }
    )
cases.append(
    {
        "name": "repository_contention",
        "events": [
            ev("boundary", {"name": k}, ns, "r1", "gate1")
            for k, ns in [
                ("repo.wait", 0),
                ("repo.acquired", 400000000),
                ("repo.released", 401000000),
            ]
        ],
        "admission_wait_ns": 400000000,
    }
)
cases.append(
    {
        "name": "missing_private_wrapper",
        "events": [
            ev(
                "coverage",
                {
                    "boundary": "public.producer_prepare",
                    "available": False,
                    "reason": "private corrected path bypasses wrapper",
                },
            )
        ],
    }
)
for c in cases:
    for i, r in enumerate(c["events"]):
        r["seq"] = i + 1
raw = (json.dumps(cases, indent=2, sort_keys=True) + "\n").encode()
(ROOT / "cases.json").write_bytes(raw)
(ROOT / "SHA256SUMS.json").write_text(
    json.dumps({"cases.json": hashlib.sha256(raw).hexdigest()}, indent=2) + "\n"
)
