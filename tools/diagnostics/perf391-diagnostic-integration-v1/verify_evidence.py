"""Independent offline schema, pair and content verification; no collection."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator

import contract
from analyze import PAIRS
from evidence import file_hash

PACKAGE = Path(__file__).resolve().parent


def validate_document(document, kind):
    if kind not in ("analysis", "summary"):
        raise ValueError("unknown document schema")
    schema = json.loads((PACKAGE / (kind + "-schema.json")).read_text())
    try:
        Draft202012Validator(schema).validate(document)
    except Exception as error:
        raise ValueError(str(error)) from error


def verify_analysis(report, events):
    validate_document(report, "analysis")
    if report["integrity"]["complete"]:
        contract.validate_stream(events)
    lookup = {}
    for event in events:
        key = (event["stream_id"], event["seq"])
        if key in lookup:
            raise ValueError("duplicate event reference")
        lookup[key] = event
    for claim in report["durations"]:
        if claim["ns"] is None:
            if claim["thread_cpu_ns"] is not None:
                raise ValueError("CPU available without complete wall boundaries")
            continue
        if not report["integrity"]["complete"] or claim["reason"] is not None:
            raise ValueError("duration on incomplete evidence")
        if len(claim["events"]) != 2:
            raise ValueError("duration requires two boundaries")
        pair = []
        for ref in claim["events"]:
            event = lookup.get((ref["stream_id"], ref["seq"]))
            if event is None or any(event[k] != v for k, v in ref.items()):
                raise ValueError("missing or altered boundary reference")
            pair.append(event)
        a, b = pair
        for key in ("run_id", "process_uuid", "op_id", "span_id"):
            if claim[key] != a[key]:
                raise ValueError("claim identity differs from source")
        group = [
            e
            for e in events
            if all(e[k] == a[k] for k in ("run_id", "process_uuid", "op_id", "span_id"))
        ]
        if claim["boundary"] == "chart_input.commit":
            group = [
                e
                for e in group
                if e["identity"].get("plot_token") == a["identity"].get("plot_token")
            ]
        begin, end = PAIRS[claim["boundary"]]
        if (
            len([e for e in group if e["phase"] == begin]) != 1
            or len([e for e in group if e["phase"] == end]) != 1
        ):
            raise ValueError("ambiguous original boundary pair")
        if tuple(e["phase"] for e in pair) != PAIRS.get(claim["boundary"]):
            raise ValueError("wrong boundary phases")
        for key in (
            "run_id",
            "process_uuid",
            "process_start_id",
            "clock_id",
            "op_id",
            "span_id",
        ):
            if a[key] != b[key]:
                raise ValueError("cross identity boundary pair")
        if (
            a["outcome"] != "ok"
            or b["outcome"] != "ok"
            or int(b["mono_ns"]) - int(a["mono_ns"]) != claim["ns"]
        ):
            raise ValueError("wrong duration or failed outcome")
        if claim["thread_cpu_ns"] is not None:
            if any(a[k] != b[k] or a[k] is None for k in ("tid", "thread_start_id")):
                raise ValueError("CPU cross-thread identity")
            if (
                a["thread_cpu_ns"] is None
                or b["thread_cpu_ns"] is None
                or int(b["thread_cpu_ns"]) - int(a["thread_cpu_ns"])
                != claim["thread_cpu_ns"]
            ):
                raise ValueError("wrong CPU duration")
    return True


def verify_artifacts(root):
    root = Path(root)
    manifest = root / "SHA256SUMS.json"
    if manifest.stat().st_size > 1048576:
        raise ValueError("hash manifest budget")
    hashes = json.loads(manifest.read_bytes())
    if len(hashes) > 4096:
        raise ValueError("artifact count budget")
    actual = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and p != manifest
    }
    if actual != set(hashes):
        raise ValueError("artifact set mismatch")
    for name, digest in hashes.items():
        path = root / name
        if (
            path.is_symlink()
            or root.resolve() not in path.resolve().parents
            or file_hash(path) != digest
        ):
            raise ValueError("artifact path/hash mismatch")
    return True
