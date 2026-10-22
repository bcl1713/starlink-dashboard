"""Conservative integration analyzer, independent of frozen #407 duration tables."""

from collections import defaultdict

import contract

PAIRS = {
    "producer.queue": ("producer.dispatch", "producer.start"),
    "producer.execution": ("producer.start", "producer.end"),
    "producer.delivery": ("producer.end", "producer.returned"),
    "producer.collection": ("collection.enter", "collection.return"),
    "producer.publication": ("producer.collected", "producer.published"),
    "publication.cas": ("publication.attempt", "publication.result"),
    "producer.final_authority": ("source.final.begin", "source.final.end"),
    "admission.local_wait": ("repo.wait", "repo.local_grant"),
    "admission.file_wait": ("repo.local_grant", "repo.acquired"),
    "admission.hold": ("repo.acquired", "repo.released"),
    "worker.queue": ("worker.dispatch", "worker.start"),
    "worker.execution": ("worker.start", "worker.end"),
    "worker.delivery": ("worker.end", "worker.returned"),
    "asgi.elapsed": ("asgi.entry", "asgi.end"),
    "observer.late_wake": ("observer.scheduled", "observer.wake"),
    "observer.invocation_to_headers": ("observer.send", "observer.headers"),
    "observer.body": ("observer.headers", "observer.received"),
    "observer.parse_available": ("observer.received", "observer.parsed"),
    "observer.drain": ("observer.parsed", "observer.written"),
    "polling.request_to_response": ("app.request", "app.response"),
    "polling.delivery": ("app.response", "query.success"),
    "chart_input.commit": ("history.retained", "plot.commit"),
    "presentation.capture": ("paint.request", "paint.artifact"),
}
UNAVAILABLE = {
    name: {"available": False, "reason": reason}
    for name, reason in {
        "axios_parse_start": "Axios exposes resolution after parsing, no native parse-start boundary",
        "physical_acquisition": "no physical acquisition instrumentation",
        "physical_scanout": "compositor sample does not establish physical scanout",
        "cross_clock_one_way": "independent process/document clock origins",
        "observer.wire_send": "HTTP invocation is not kernel wire send",
        "passive_http_capture": "Stage 3B deferred; no raw browser body provenance",
        "all_server_workers": "only explicitly instrumented call sites are covered",
    }.items()
}


def analyze(events, summaries):
    import itertools

    events = list(itertools.islice(events, 100001))
    errors = []
    streams = defaultdict(list)
    if len(events) > 100000:
        raise ValueError("analysis event budget; use bounded run segments")
    try:
        contract.validate_stream(events)
    except (ValueError, KeyError) as error:
        errors.append(str(error)[:512])
    for e in events:
        streams[e["stream_id"]].append(e)
    finals = {}
    for s in summaries:
        if s["stream_id"] in finals:
            errors.append("duplicate summary")
        finals[s["stream_id"]] = s
    for stream, rows in streams.items():
        summary = finals.get(stream)
        if (
            not summary
            or not summary["complete"]
            or summary["dropped"]
            or summary["last_seq"] != max(e["seq"] for e in rows)
        ):
            errors.append("missing/incomplete/loss summary:" + stream)
        if len({(e["tid"], e["thread_start_id"]) for e in rows}) != 1:
            errors.append("thread identity changed in stream:" + stream)
    groups = defaultdict(list)
    requests = defaultdict(list)
    for e in events:
        key = (e["run_id"], e["process_uuid"], e["op_id"], e["span_id"])
        if e["phase"] in ("history.retained", "plot.commit"):
            key = (*key, e["identity"].get("plot_token"))
        groups[key].append(e)
        request = e["identity"].get("request_id")
        if not request and e["phase"].startswith("asgi."):
            request = e["op_id"]
        if request:
            requests[(e["run_id"], request)].append(e)
    durations = []
    for key, rows in sorted(groups.items(), key=lambda item: str(item[0])):
        phases = defaultdict(list)
        for e in rows:
            phases[e["phase"]].append(e)
        for boundary, (begin, end) in PAIRS.items():
            if (
                begin not in phases
                and end not in phases
                and not (
                    boundary == "producer.publication"
                    and any(e["operation_type"] in ("tick", "replay") for e in rows)
                )
            ):
                continue
            starts, ends = phases[begin], phases[end]
            ns = cpu = None
            reason = None
            pair = []
            if errors:
                reason = "stream integrity unavailable"
            elif len(starts) != 1 or len(ends) != 1:
                reason = "missing or ambiguous boundary"
            else:
                a, b = starts[0], ends[0]
                pair = [
                    {
                        k: e[k]
                        for k in ("stream_id", "seq", "phase", "clock_id", "mono_ns")
                    }
                    for e in (a, b)
                ]
                clock = ("run_id", "process_uuid", "process_start_id", "clock_id")
                if any(a[k] != b[k] for k in clock):
                    reason = "different clock/process identity"
                elif a["outcome"] != "ok" or b["outcome"] != "ok":
                    reason = "unsuccessful boundary outcome"
                elif int(b["mono_ns"]) < int(a["mono_ns"]):
                    reason = "monotonic reset/order"
                else:
                    ns = int(b["mono_ns"]) - int(a["mono_ns"])
                    if (
                        a["thread_cpu_ns"] is not None
                        and b["thread_cpu_ns"] is not None
                        and all(a[k] == b[k] for k in ("tid", "thread_start_id"))
                    ):
                        delta = int(b["thread_cpu_ns"]) - int(a["thread_cpu_ns"])
                        if delta >= 0:
                            cpu = delta
            durations.append(
                {
                    "boundary": boundary,
                    "run_id": key[0],
                    "process_uuid": key[1],
                    "op_id": key[2],
                    "span_id": key[3],
                    "ns": ns,
                    "thread_cpu_ns": cpu,
                    "reason": reason,
                    "events": pair,
                }
            )
    joins = []
    for (run, request), rows in sorted(requests.items()):
        backend = [
            e for e in rows if e["emitter"] == "backend" and e["phase"] == "asgi.entry"
        ]
        browser = [
            e for e in rows if e["emitter"] == "browser" and e["phase"] == "app.request"
        ]
        state = "joined" if len(backend) == 1 and len(browser) == 1 else "unavailable"
        joins.append(
            {
                "run_id": run,
                "request_id": request,
                "state": state,
                "reason": (
                    "explicit request identity; no clock subtraction"
                    if state == "joined"
                    else "missing/ambiguous request side"
                ),
                "events": [
                    {"stream_id": e["stream_id"], "seq": e["seq"], "phase": e["phase"]}
                    for e in rows
                ],
            }
        )
    operation_keys = {(e["run_id"], e["process_uuid"], e["op_id"]) for e in events}
    operation_joins = []
    for key in sorted(
        {
            (e["run_id"], e["process_uuid"], e["op_id"], e["parent_op_id"])
            for e in events
            if e["parent_op_id"] is not None
        }
    ):
        operation_joins.append(
            {
                "run_id": key[0],
                "process_uuid": key[1],
                "op_id": key[2],
                "parent_op_id": key[3],
                "state": (
                    "joined"
                    if (key[0], key[1], key[3]) in operation_keys
                    else "unavailable"
                ),
            }
        )
    boundaries = {
        name: {
            "available": any(
                d["boundary"] == name and d["ns"] is not None for d in durations
            ),
            "reason": (
                "complete same-clock pair"
                if any(d["boundary"] == name and d["ns"] is not None for d in durations)
                else "missing, inapplicable, failed or ambiguous instrumentation"
            ),
        }
        for name in PAIRS
    }
    return {
        "schema": "perf391-integration-analysis-v1",
        "version": 1,
        "integrity": {"complete": not errors, "errors": errors},
        "durations": durations,
        "request_joins": joins,
        "operation_joins": operation_joins,
        "boundaries": boundaries,
        "unavailable": UNAVAILABLE,
        "successful_publications": (
            sum(
                e["phase"] == "producer.published"
                and e["role"] == "C"
                and e["outcome"] == "ok"
                and e["operation_type"] in ("tick", "replay")
                and e["identity"].get("cas_success") is True
                and e["identity"].get("publication_kind") == "ready"
                for e in events
            )
            if not errors
            and any(
                e["phase"] == "publication.result" and e["role"] == "C" for e in events
            )
            else None
        ),
        "policy": "Missing instrumentation is unavailable. Durations overlap and are not additive CPU savings. ID joins survive UTC steps.",
    }
