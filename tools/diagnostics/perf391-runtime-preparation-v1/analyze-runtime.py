"""Offline receipt-bound importer through the unchanged Stage 5/#407 API."""

import argparse
import json
from pathlib import Path

from prepare import REPO, sha, verify_overlay, write, check_release
from launcher import validate_receipt
from collector import prepare_collector
from evidence import Evidence
from integration import Integration
from analyze import analyze
from run import read_jsonl
from verify_evidence import validate_document, verify_analysis, verify_artifacts


def analyze_runtime(build_plan, receipt_path, runtime, output):
    plan = json.loads(build_plan.read_bytes())
    receipt = json.loads(receipt_path.read_bytes())
    check_release()
    verify_overlay(plan)
    validate_receipt(receipt, plan, sha(build_plan))
    role = receipt["role"]
    owner = json.loads((runtime / "manifest.json").read_bytes())
    launch = json.loads((runtime / "launch.json").read_bytes())
    result = json.loads((runtime / "runtime-result.json").read_bytes())
    cleanup = json.loads((runtime / "cleanup-audit.json").read_bytes())
    expected_run = "synthetic-408" + role.lower()
    if (
        owner["sources"]["build_plan_sha256"] != sha(build_plan)
        or owner["sources"]["receipt_sha256"] != sha(receipt_path)
        or owner["run_id"] != expected_run
        or owner["status"] != "clean"
        or launch["role"] != role
        or launch["root"] != str(runtime.resolve())
        or any(
            launch["env"]["PERF391_" + kind.upper() + "_IMAGE"]
            != receipt["images"][kind]["id"]
            for kind in ("backend", "frontend")
        )
        or result["failure"] is not None
        or result["cleanup_error"] is not None
        or result["owner_status"] != "clean"
        or not cleanup["clean"]
        or cleanup["project"] != launch["project"]
        or cleanup["runtime_root"] != str(runtime.resolve())
    ):
        raise ValueError("runtime evidence/receipt/ownership/cleanup mismatch")
    output.mkdir(parents=True, exist_ok=False)
    collector = prepare_collector(output / "collector", REPO)
    backend = read_jsonl(runtime / "backend/backend.jsonl")
    if not backend:
        raise ValueError("empty backend evidence")
    run = backend[0]["run_id"]
    if run != expected_run or any(
        row["run_id"] != run or row["role"] != role for row in backend
    ):
        raise ValueError("backend run/role continuity")
    node_root = runtime / "browser/node"
    verify_artifacts(node_root)
    summary = json.loads((node_root / "summary.json").read_bytes())
    frontend = json.loads((runtime / "browser/frontend-final.json").read_bytes())
    final = frontend["after"]
    if not final["closed"] or any(
        final[k] for k in ("failed", "lost", "pending", "inflight")
    ):
        raise ValueError("frontend final summary incomplete")
    if summary["run"] != run or not summary["complete"]:
        raise ValueError("Node/backend run or loss gate")
    streams = summary["streams"]
    if len(streams) != 1 or streams[0]["last_seq"] != final["seq"]:
        raise ValueError("frontend final sequence mismatch or unexpected document")
    stats = json.loads((runtime / "backend/backend-stats.json").read_bytes())
    from backend_evidence import validate_stats

    validate_stats(stats)
    host_rows = read_jsonl(runtime / "host.jsonl", max_bytes=67108864)
    host_final = [r for r in host_rows if r["kind"] == "summary"]
    if (
        len(host_final) != 1
        or not host_final[0]["complete"]
        or host_final[0]["completed"] != 5
        or host_final[0]["skipped"]
    ):
        raise ValueError("host final sample/loss gate")
    sink = Evidence(output / "evidence", collector, run=run)
    adapter = Integration(
        sink,
        role=role,
        run=run,
        module_hashes=plan["roles"][role]["identity"]["projection_module_hashes"],
    )
    wakes = []
    try:
        adapter.backend(backend)
        adapter.finish_backend(stats)

        def load(ref):
            from prepare import build

            build.safe_path(ref["path"])
            path = node_root / ref["path"]
            if (
                path.is_symlink()
                or node_root.resolve() not in path.resolve().parents
                or path.stat().st_size > 2097152
            ):
                raise ValueError("artifact path/body budget")
            return path.read_bytes()

        for raw in read_jsonl(node_root / "records.jsonl"):
            if raw.get("origin") == "observer":
                if raw["event"]["phase"] == "observer.wake":
                    wakes.append(int(raw["event"]["mono_ns"]))
                adapter.source_record(raw)
            elif raw.get("origin") == "source-body":
                adapter._v1(
                    "body",
                    {
                        "viewer": "source-observer",
                        "request_id": raw["op"],
                        "status": raw["status"],
                        "artifact": sink.artifact(load(raw["artifact"])),
                    },
                    op=raw["op"],
                )
            else:
                adapter.browser_record(raw, load=load)
        if len(wakes) != 5 or any(
            b <= a or b - a > 1500000000 for a, b in zip(wakes, wakes[1:])
        ):
            raise ValueError("unchanged 1.5-second observer cadence gate")
        for source in summary["sources"]:
            if (
                source["completed"] != 5
                or source["skipped"]
                or source["failed"]
                or source["cancelled"]
            ):
                raise ValueError("source final sample/loss gate")
            adapter.finish_source(source)
        browsers = summary["browsers"]
        adapter.finish_browser(
            {
                "closed": summary["closed"],
                "failed": not summary["complete"],
                "lost": summary["dropped"] + sum(b["lost"] for b in browsers),
                "ownedOperations": sum(b["ownedOperations"] for b in browsers),
            }
        )
        result = sink.close()
        validate_document(result, "summary")
        verify_artifacts(sink.root)
        rows = read_jsonl(sink.root / "integration.jsonl")
        phases = {row["phase"] for row in rows}
        required = {
            "producer.dispatch",
            "producer.start",
            "producer.collected",
            "producer.end",
            "producer.returned",
            "asgi.entry",
            "asgi.end",
            "app.request",
            "app.parse_available",
            "plot.commit",
            "history.retained",
        }
        if role == "C":
            required |= {"source.final.begin", "source.final.end", "publication.result"}
        if not required <= phases:
            raise ValueError(
                "required smoke boundaries missing: " + str(sorted(required - phases))
            )
        report = analyze(rows, result)
        verify_analysis(report, rows)
        required_join_phases = {
            "asgi.entry",
            "asgi.end",
            "browser.request",
            "app.response",
            "app.parse_available",
            "history.retained",
            "plot.commit",
        }
        if not any(
            join["state"] == "joined"
            and required_join_phases <= {e["phase"] for e in join["events"]}
            for join in report["request_joins"]
        ):
            raise ValueError(
                "explicit browser/backend history-to-chart request join absent"
            )
        write(output / "analysis.json", report)
        write(
            output / "qualification.json",
            {
                "build_plan_sha256": sha(build_plan),
                "receipt_sha256": sha(receipt_path),
                "runtime": "short synthetic diagnostic smoke only",
                "wire_body": "unavailable: no capture adapter/permissions",
                "physical_scanout": "unavailable",
                "host_identity": "consult retained host mappings/counters; no cross-clock subtraction",
            },
        )
        if not result["complete"] or not report["integrity"]["complete"]:
            raise ValueError("integration integrity incomplete")
        return result
    finally:
        if not sink.closed:
            sink.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("build-plan", "receipt", "runtime", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    analyze_runtime(args.build_plan, args.receipt, args.runtime, args.output)
