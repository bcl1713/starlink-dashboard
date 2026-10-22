"""Offline tooling CLI; runtime collection is opt-in and capped at 180 seconds."""

import argparse
import hashlib
import json
import os
import signal
import threading
import time
from pathlib import Path

from .adapters import import_legacy, observe_once, sample_resources
from .analyze import analyze, human
from .ingestion import CONTROL_FIELDS, stored_events
from .record import Recorder


def dump(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def read_rows(paths):
    rows = []
    total_bytes = 0
    for path in paths:
        with path.open() as stream:
            while line := stream.readline(2 * 1024**2 + 1):
                total_bytes += len(line.encode())
                if total_bytes > 64 * 1024**2:
                    raise ValueError(
                        "offline input byte limit exceeded; partition the run"
                    )
                if len(line) > 2 * 1024**2:
                    raise ValueError("event line limit exceeded")
                row = json.loads(line)
                artifact = row.get("data", {}).get("artifact")
                if artifact and artifact["state"] == "available":
                    body_path = (path.parent / artifact["path"]).resolve()
                    if not body_path.is_relative_to(path.parent.resolve()):
                        raise ValueError("artifact path escapes owned root")
                    if (
                        body_path.stat().st_size != artifact["bytes"]
                        or body_path.stat().st_size > 2 * 1024**2
                    ):
                        raise ValueError("artifact size mismatch")
                    if (
                        hashlib.sha256(body_path.read_bytes()).hexdigest()
                        != artifact["sha256"]
                    ):
                        raise ValueError("artifact hash mismatch")
                rows.append(row)
                if len(rows) > 200000:
                    raise ValueError(
                        "offline event count limit exceeded; partition the run"
                    )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("analyze")
    p.add_argument("inputs", type=Path, nargs="+")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("fixtures")
    p.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "fixtures/cases.json",
    )
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("import-legacy")
    p.add_argument("input", type=Path)
    p.add_argument("--run-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("import-stored")
    p.add_argument("input", type=Path)
    p.add_argument("--run-id", required=True)
    p.add_argument("--attest-stored-range-vector", action="store_true", required=True)
    p.add_argument("--field", action="append", default=[])
    p.add_argument("--output", type=Path, required=True)
    for name in ("observe", "host"):
        p = sub.add_parser(name)
        p.add_argument("--output", type=Path, required=True)
        p.add_argument("--run-id", required=True)
        p.add_argument("--duration", type=int, required=True)
        p.add_argument("--diagnostic-lane", action="store_true", required=True)
        p.add_argument("--url", required=name == "observe")
        p.add_argument("--cgroup", type=Path, action="append", default=[])
        p.add_argument("--pid", type=int, action="append", default=[])
    args = parser.parse_args(argv)
    if args.command == "analyze":
        result = analyze(read_rows(args.inputs))
        args.output.mkdir(parents=True, exist_ok=False)
        dump(args.output / "analysis.json", result)
        (args.output / "analysis.txt").write_text(human(result))
        return 1 if result["issues"] else 0
    if args.command == "fixtures":
        expected_hash = json.loads((args.input.parent / "SHA256SUMS.json").read_text())[
            args.input.name
        ]
        if hashlib.sha256(args.input.read_bytes()).hexdigest() != expected_hash:
            raise ValueError("immutable fixture hash mismatch")
        results = []
        for case in json.loads(args.input.read_text()):
            result = analyze(case["events"])
            if not set(case.get("expected", [])) <= {
                r["classification"] for r in result["charts"]
            }:
                raise ValueError("fixture classification mismatch: " + case["name"])
            for key, expected in case.get("durations", {}).items():
                if result["operations"]["r1"][key]["value_ns"] != expected:
                    raise ValueError("fixture duration mismatch: " + case["name"])
            results.append(
                {"name": case["name"], "status": "passed", "analysis": result}
            )
        dump(
            args.output,
            {
                "schema": "perf391-network-evidence-fixtures-v1",
                "fixture_sha256": expected_hash,
                "passed": len(results),
                "cases": results,
            },
        )
        return 0
    if args.command.startswith("import-"):
        data = json.loads(args.input.read_text())
        rows = (
            import_legacy(data, run_id=args.run_id)
            if args.command == "import-legacy"
            else stored_events(
                data, run_id=args.run_id, fields=args.field or CONTROL_FIELDS
            )
        )
        with args.output.open("x") as stream:
            for row in rows:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
        return 0
    if not 1 <= args.duration <= 180:
        parser.error(
            "only bounded diagnostic collection 1..180 seconds is implemented; no soak runner"
        )
    stop = threading.Event()
    previous = {
        sig: signal.signal(sig, lambda *_: stop.set())
        for sig in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        with Recorder(args.output, run_id=args.run_id) as recorder:
            dump(
                args.output / "owner.json",
                {
                    "pid": os.getpid(),
                    "pgid": os.getpgid(0),
                    "purpose": "bounded supplemental " + args.command,
                    "paths": [str(args.output)],
                    "children": [],
                    "listeners": [],
                    "containers": [],
                    "deadline_seconds": args.duration,
                    "stop_command": f"kill -TERM {os.getpid()}",
                },
            )
            start = time.monotonic_ns()
            deadline, index = start, 0
            while (
                not stop.is_set()
                and time.monotonic_ns() - start < args.duration * 10**9
            ):
                stop.wait(max(0, (deadline - time.monotonic_ns()) / 1e9))
                if stop.is_set():
                    break
                before = time.monotonic_ns()
                utc = time.time_ns()
                after = time.monotonic_ns()
                recorder.emit(
                    "anchor",
                    {"utc_ns": str(utc), "uncertainty_ns": str(after - before)},
                    mono_ns=(before + after) // 2,
                )
                if args.command == "observe":
                    observe_once(recorder, args.url, f"diag-{index+1}", deadline)
                else:
                    recorder.emit(
                        "resource", sample_resources(cgroups=args.cgroup, pids=args.pid)
                    )
                    recorder.drain()
                index += 1
                deadline += 10**9
        dump(
            args.output / "cleanup.json",
            {
                "closed": recorder.closed,
                "children": [],
                "listeners": [],
                "containers": [],
                "signal_requested": stop.is_set(),
                "runtime_created": "collector process only; caller must reap it",
            },
        )
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
