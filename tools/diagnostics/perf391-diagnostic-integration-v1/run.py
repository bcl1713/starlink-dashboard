"""Offline Stage 4 runner. No image, browser, service or network entrypoint.

`tests` owns one bounded child and records PID/PGID/start identities before
execution. `analyze` consumes capped JSONL files already on disk. The parent
is a child subreaper so terminated test descendants are joined, never orphaned.
"""

import argparse
import asyncio
import ctypes
import json
import os
import signal
import sys
from pathlib import Path

import build
from analyze import analyze
from evidence import canonical
from owner import Owner

PACKAGE = Path(__file__).resolve().parent
MODULES = (
    "analyze.py",
    "collector.py",
    "collect.mjs",
    "diagnostic_app.py",
    "evidence.py",
    "host.py",
    "integration.py",
    "observer.mjs",
    "owner.py",
    "run.py",
    "backend_probe.py",
    "workers.py",
    "browser.mjs",
    "browser-probe.ts",
    "contract.py",
    "contract.json",
    "integration-event-schema.json",
    "verify_evidence.py",
    "analysis-schema.json",
    "summary-schema.json",
    "build.py",
    "verify.py",
    "verify_backend.py",
    "verify_frontend.py",
    "frontend-config.mjs",
    "build-manifest-schema.json",
    "requirements-test.txt",
)


def source_identity(repo):
    return {
        "starting_commit": "8faeac62601720cec711d0a6ddc97f18a497cb09",
        "integration_commit": build.git(repo, "rev-parse", "HEAD").decode().strip(),
        "pins": build.PINS,
        "modules": {
            name: build.digest((PACKAGE / name).read_bytes()) for name in MODULES
        },
        "patches": {
            name: build.digest((PACKAGE / "patches" / name).read_bytes())
            for name in (
                "A.patch",
                "A.json",
                "C.patch",
                "C.json",
                "frontend/A.patch",
                "frontend/A.json",
                "frontend/C.patch",
                "frontend/C.json",
            )
        },
    }


def read_jsonl(path, *, max_bytes=32 * 1024 * 1024, max_events=100000):
    total = 0
    rows = []
    with Path(path).open("rb") as stream:
        while True:
            raw = stream.readline(1048577)
            if not raw:
                break
            total += len(raw)
            if len(raw) > 1048576 or total > max_bytes or len(rows) >= max_events:
                raise ValueError("offline input budget")
            rows.append(json.loads(raw))
    return rows


async def run_tests(output, *, pattern="test_*.py"):
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "child subreaper unavailable")
    owner = Owner(
        output,
        run="synthetic-stage4",
        sources=source_identity(PACKAGE.parents[2]),
        adopt_descendants=True,
    )
    command = [
        sys.executable,
        "-B",
        "-m",
        "coverage",
        "run",
        "--branch",
        "--source=backend_probe,workers,build,contract,collector,diagnostic_app,evidence,host,integration,owner,analyze,verify_evidence",
        "tests/owned_suite.py",
        pattern,
    ]
    loop = asyncio.get_running_loop()
    interrupted = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, interrupted.set)
    result = 1
    child = None
    with (owner.root / "tests.log").open("wb") as log:
        try:
            child = owner.spawn(
                command,
                stdout=log,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "COVERAGE_FILE": str(owner.root / "coverage.data"),
                },
            )
            # PID remains reserved until cleanup. waitpid WNOWAIT observes exit without reaping.
            deadline = loop.time() + 120
            while loop.time() < deadline and not interrupted.is_set():
                status = os.waitid(  # noqa: ASYNC222 - WNOHANG observes without blocking/reaping
                    os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT
                )
                if status is not None:
                    result = (
                        status.si_status
                        if status.si_code == os.CLD_EXITED
                        else 128 + status.si_status
                    )
                    break
                await asyncio.sleep(0.02)
            else:
                owner.manifest["errors"].append("test_timeout_or_signal")
        finally:
            await owner.close()
            for sig in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(sig)
    print(json.dumps(owner.manifest, indent=2))
    return result if owner.manifest["status"] == "clean" else 1


def integrate_offline(output, *, role, backend_file, stats_file, node_root=None):
    from collector import prepare_collector
    from evidence import Evidence
    from integration import Integration
    from verify_evidence import validate_document, verify_analysis, verify_artifacts

    repo = PACKAGE.parents[2]
    owner = Owner(output, run="synthetic-stage4", sources=source_identity(repo))
    collector = prepare_collector(owner.root / "collector", repo)
    backend = read_jsonl(backend_file)
    run = backend[0]["run_id"] if backend else "synthetic-stage4"
    sink = Evidence(owner.root / "evidence", collector, run=run)
    adapter = Integration(sink, role=role, run=run)
    try:
        adapter.backend(backend)
        if stats_file.stat().st_size > 1048576:
            raise ValueError("backend stats budget")
        adapter.finish_backend(json.loads(stats_file.read_bytes()))
        if node_root is not None:
            verify_artifacts(node_root)
            raw_summary = node_root / "summary.json"
            if raw_summary.stat().st_size > 1048576:
                raise ValueError("node summary budget")
            summary = json.loads(raw_summary.read_bytes())
            if summary["run"] != run:
                raise ValueError("node/backend run mismatch")

            def load(reference):
                name = reference["path"]
                path = node_root / name
                if (
                    path.is_symlink()
                    or node_root.resolve() not in path.resolve().parents
                    or path.stat().st_size > 2097152
                ):
                    raise ValueError("artifact path/body budget")
                return path.read_bytes()

            for raw in read_jsonl(node_root / "records.jsonl"):
                if raw.get("origin") == "observer":
                    adapter.source_record(raw)
                elif raw.get("origin") == "source-body":
                    body = load(raw["artifact"])
                    reference = sink.artifact(body)
                    adapter._v1(
                        "body",
                        {
                            "viewer": "source-observer",
                            "request_id": raw["op"],
                            "status": raw["status"],
                            "artifact": reference,
                        },
                        op=raw["op"],
                    )
                else:
                    adapter.browser_record(raw, load=load)
            browser = summary.get("browsers", [])
            adapter.finish_browser(
                {
                    "closed": summary["closed"],
                    "failed": not summary["complete"],
                    "lost": summary["dropped"] + sum(s["lost"] for s in browser),
                    "ownedOperations": sum(s["ownedOperations"] for s in browser),
                }
            )
            for source in summary.get("sources", []):
                adapter.finish_source(source)
        result = sink.close()
        validate_document(result, "summary")
        verify_artifacts(sink.root)
        rows = read_jsonl(sink.root / "integration.jsonl")
        report = analyze(rows, result)
        verify_analysis(report, rows)
        (owner.root / "analysis.json").write_bytes(canonical(report) + b"\n")
        owner.manifest["streams"] = result["streams"]
        owner.manifest["output_directories"].append(str(sink.root))
        owner.manifest["status"] = "clean"
        owner.persist()
        return {"evidence": result, "analysis": report}
    finally:
        if not sink.closed:
            sink.close()
        # Offline integration creates no child processes or external runtime objects.
        if owner.manifest["status"] != "clean":
            owner.manifest["status"] = "failed_no_runtime_resources"
            owner.persist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    tests = sub.add_parser("tests")
    tests.add_argument("--output", type=Path, required=True)
    tests.add_argument("--pattern", default="test_*.py")
    report = sub.add_parser("analyze")
    report.add_argument("--events", type=Path, required=True)
    report.add_argument("--summary", type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    integration = sub.add_parser("integrate")
    integration.add_argument("--output", type=Path, required=True)
    integration.add_argument("--role", choices=["A", "C"], required=True)
    integration.add_argument("--backend", type=Path, required=True)
    integration.add_argument("--stats", type=Path, required=True)
    integration.add_argument("--node-root", type=Path)
    args = parser.parse_args()
    if args.command == "tests":
        return asyncio.run(run_tests(args.output, pattern=args.pattern))
    if args.command == "integrate":
        result = integrate_offline(
            args.output,
            role=args.role,
            backend_file=args.backend,
            stats_file=args.stats,
            node_root=args.node_root,
        )
        return (
            0
            if result["evidence"]["complete"]
            and result["analysis"]["integrity"]["complete"]
            else 1
        )
    rows = read_jsonl(args.events)
    if args.summary.stat().st_size > 1048576:
        raise ValueError("summary budget")
    summary = json.loads(args.summary.read_bytes())
    result = analyze(rows, summary)
    with args.output.open("xb") as f:
        f.write(canonical(result) + b"\n")
    return 0 if result["integrity"]["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
