"""Process-local durations and request-ID joins. Never compare clock origins."""

import argparse
import hashlib
import itertools
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def dist(values):
    values = sorted(values)
    return (
        {
            "count": len(values),
            "mean": statistics.mean(values),
            **{
                p: values[math.ceil(len(values) * q) - 1]
                for p, q in [("p50", 0.5), ("p95", 0.95), ("p99", 0.99), ("max", 1)]
            },
        }
        if values
        else {"count": 0}
    )


def grouped(rows):
    result = defaultdict(dict)
    for row in rows:
        if row.get("op", "").startswith("diag-"):
            result[row["op"]][row["event"]] = row["ns"]
    return result


def correlate(observer, backend):
    client, server = grouped(observer["events"]), grouped(backend["events"])
    result = []
    for op, c in client.items():
        s = server.get(op, {})
        rtt = (
            c["http.body"] - c["http.send"]
            if "http.body" in c and "http.send" in c
            else None
        )
        duration = (
            s["asgi.end"] - s["asgi.arrival"]
            if "asgi.end" in s and "asgi.arrival" in s
            else None
        )
        phases = {}
        for name, start, end in [
            ("worker_queue_ns", "worker_dispatch.start", "worker_execution.start"),
            ("worker_service_ns", "worker_execution.start", "worker_execution.end"),
            ("worker_return_to_loop_ns", "worker_execution.end", "worker_dispatch.end"),
        ]:
            phases[name] = s[end] - s[start] if start in s and end in s else None
        result.append(
            {
                **phases,
                "op": op,
                "rtt_ns": rtt,
                "server_ns": duration,
                "unallocated_ns": (
                    rtt - duration if rtt is not None and duration is not None else None
                ),
                "outcome": (
                    "complete"
                    if rtt is not None and duration is not None
                    else "incomplete"
                ),
            }
        )
    return result


def capture_gaps(captures):
    stamps = [r["capture_ns"] for r in captures if r.get("capture_ns") is not None]
    gaps = [b - a for a, b in itertools.pairwise(stamps)]
    return {"ns": dist(gaps), "over_1_5_seconds": sum(x > 1.5e9 for x in gaps)}


def parse_stat(value):
    return {k: int(v) for k, v in (line.split() for line in value.splitlines())}


def analyze(root):
    run = json.loads((root / "run.json").read_text())
    result = {
        "status": run["status"],
        "cleanup": run.get("cleanup"),
        "browser_cleanup": run.get("browser_cleanup"),
        "sha": run["candidate_sha"],
        "instrumentation": run.get("instrumentation"),
        "workload": run.get("workload"),
        "packages_sha256": run.get("backend_packages_sha256"),
    }
    if not (root / "observer.json").exists():
        return result
    o = json.loads((root / "observer.json").read_text())
    b = (
        json.loads((root / "trace/backend.json").read_text())
        if (root / "trace/backend.json").exists()
        else {"events": [], "dropped": 0}
    )
    rows = b["events"]
    # Bound backend analysis by request IDs in that process, not observer timestamps.
    selected = [r["ns"] for r in rows if r.get("op", "").startswith("diag-")]
    if selected:
        rows = [r for r in rows if min(selected) <= r["ns"] <= max(selected)]
    timings = defaultdict(list)
    cpus = defaultdict(list)
    for row in rows:
        if row["event"].endswith(".end") and "wall_ns" in row:
            kind = row["event"][:-4]
            timings[kind].append(row["wall_ns"])
            if kind != "worker_dispatch":
                cpus[kind].append(row["cpu_ns"])
        if row["event"] == "lock.released" and row["depth"] == 0:
            kind = "lock_hold/" + (
                "observer"
                if row["op"].startswith("diag-")
                else "producer" if row["op"].startswith("tick-") else "other"
            )
            timings[kind].append(row["wall_ns"])
    byop = grouped(rows)
    dispatch = [r for r in rows if r["event"] == "tick.dispatch"]
    starts = {r["op"]: r["ns"] for r in rows if r["event"] == "tick.start"}
    timings["tick_executor_wait"] = [
        starts[r["op"]] - r["ns"] for r in dispatch if r["op"] in starts
    ]
    timings["worker_executor_wait"] = [
        r["worker_execution.start"] - r["worker_dispatch.start"]
        for r in byop.values()
        if "worker_execution.start" in r and "worker_dispatch.start" in r
    ]
    timings["asgi_to_worker"] = [
        r["worker_execution.start"] - r["asgi.arrival"]
        for r in byop.values()
        if "worker_execution.start" in r and "asgi.arrival" in r
    ]
    timings["backend_loop_delay"] = [
        r["delay_ns"] for r in rows if r["event"] == "loop.wake"
    ]
    timings["observer_loop_delay"] = [
        r["delay_ns"] for r in o["events"] if r["event"] == "loop.wake"
    ]
    timings["observer_wake_delay"] = [
        r["delay_ns"] for r in o["events"] if r["event"] == "observer.wake"
    ]
    joins = correlate(o, {"events": rows})
    for name in ("worker_queue_ns", "worker_service_ns", "worker_return_to_loop_ns"):
        timings[name.removesuffix("_ns")] = [
            r[name] for r in joins if r[name] is not None
        ]
    timings["observer_http"] = [r["rtt_ns"] for r in joins if r["rtt_ns"] is not None]
    timings["unallocated_http"] = [
        r["unallocated_ns"] for r in joins if r["unallocated_ns"] is not None
    ]
    acquisitions = [r["ns"] for r in rows if r["event"] == "acquisition"]
    timings["collection_completion_gap"] = [
        b - a for a, b in itertools.pairwise(acquisitions)
    ]
    host = [r for r in rows if r["event"] == "host.sample"]
    throttle = {}
    if len(host) > 1 and host[0]["cpu_stat"] and host[-1]["cpu_stat"]:
        first, last = [parse_stat(r["cpu_stat"]) for r in (host[0], host[-1])]
        throttle = {k: last[k] - first[k] for k in last if k in first}
    scheduler = []
    for a, z in itertools.pairwise(host):
        for tid, v in z["schedstat"].items():
            av = a["schedstat"].get(tid)
            if av and v:
                start, end = [list(map(int, s.split())) for s in (av, v)]
                scheduler.append(end[1] - start[1])
    result.update(
        capture_gaps=capture_gaps(o["captures"]),
        durations_ns={k: dist(v) for k, v in timings.items()},
        thread_cpu_ns={k: dist(v) for k, v in cpus.items()},
        dropped=b["dropped"],
        requests=joins,
        injected=[r for r in b["events"] + o["events"] if r["event"] == "injection"],
        capture_age_seconds=dist(
            [r["age_seconds"] for r in o["captures"] if r["age_seconds"] is not None]
        ),
        scheduler_wait_per_thread_sample_ns=dist(scheduler),
        cgroup_delta=throttle,
        browser_requests=len(o["traffic"]),
        browser_failures=[r for r in o["traffic"] if r["status"] >= 400],
        observer_cpu_us=o.get("observer_cpu_us"),
        elapsed_ns=o.get("elapsed_ns"),
        cancelled=o.get("cancelled"),
        failure=o.get("failure"),
    )
    if o.get("backend_before") and o.get("backend_after"):
        before, after = [
            parse_stat(o[k]["cpu_stat"]) for k in ("backend_before", "backend_after")
        ]
        result["backend_cpu_ms"] = (after["usage_usec"] - before["usage_usec"]) / 1000
    result["observer_errors"] = [r for r in o["events"] if r["event"] == "http.error"]
    if run.get("instrumentation") == "off":
        result["requests"] = []
        result["backend_attribution"] = "disabled by control design"
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = {
        p.name: analyze(p)
        for p in sorted(args.root.iterdir())
        if (p / "run.json").exists()
    }
    hashes = {
        str(p.relative_to(args.root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in args.root.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    args.output.write_text(
        json.dumps({"runs": results, "raw_manifest": hashes}, indent=2)
    )
