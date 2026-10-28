#!/usr/bin/env python3
"""Bounded synthetic mission churn benchmark; optional isolated scrape fixture.

Run with the backend's Python dependencies. --backend-root permits identical
workloads against archived baseline source without changing the working tree.
This measures exporter behavior, not production workload or TSDB disk savings.
"""

import argparse
import json
import os
import platform
import signal
import sys
import time
import tracemalloc
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from statistics import median


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--switches", type=int, default=200)
    parser.add_argument("--scrapes", type=int, default=100)
    parser.add_argument(
        "--serve", type=int, help="serve a disposable synthetic fixture"
    )
    args = parser.parse_args()
    if not 1 <= args.switches <= 10000 or not 1 <= args.scrapes <= 10000:
        parser.error("switches and scrapes must be between 1 and 10000")
    sys.path.insert(0, str(args.backend_root.resolve()))
    from app.core.metrics import metric_updater as updater
    from app.core.metrics import prometheus_metrics as metrics
    from prometheus_client import generate_latest

    current = None

    def switch(index):
        nonlocal current
        if current is not None:
            updater.clear_mission_metrics(current)
        current = f"synthetic-{index}"
        updater.update_mission_active_metric(current, f"renamed-route-{index}")
        updater.update_mission_phase_metric(current, "in_flight")
        updater.update_mission_timeline_timestamp(current, 1234567890)
        updater.update_mission_next_conflict_metric(current, -1)
        updater.update_mission_duration_metrics(current, 0, 0)
        for transport in ("X", "Ka", "Ku"):
            updater.update_mission_comm_state_metric(current, transport, 0)

    def counts():
        families = list(metrics.REGISTRY.collect())
        return {
            "mission_samples": sum(
                len(f.samples) for f in families if f.name.startswith("mission_")
            ),
            "exporter_samples": sum(len(f.samples) for f in families),
            "exporter_bytes": len(generate_latest(metrics.REGISTRY)),
        }

    if args.serve:
        metrics.starlink_network_latency_ms.labels(
            mode="simulation", status="good"
        ).observe(42)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = generate_latest(metrics.REGISTRY)
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4")
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path.startswith("/switch/"):
                    switch(int(self.path.rsplit("/", 1)[1]))
                elif self.path == "/clear" and current is not None:
                    updater.clear_mission_metrics(current)
                else:
                    self.send_error(404)
                    return
                body = json.dumps(counts()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_):
                pass

        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        with HTTPServer(("0.0.0.0", args.serve), Handler) as server:
            print(json.dumps({"pid": os.getpid(), "port": args.serve}), flush=True)
            server.serve_forever()
        return

    generate_latest(metrics.REGISTRY)  # warm imports/exposition before measuring
    tracemalloc.start()
    before_memory = tracemalloc.get_traced_memory()[0]
    started = time.perf_counter()
    for index in range(args.switches):
        switch(index)
    mutation_seconds = time.perf_counter() - started
    memory = tracemalloc.get_traced_memory()[0] - before_memory
    tracemalloc.stop()  # avoid instrumentation overhead in scrape latency
    active = counts()
    durations = []
    cpu_started = time.process_time()
    for _ in range(args.scrapes):
        started = time.perf_counter()
        generate_latest(metrics.REGISTRY)
        durations.append((time.perf_counter() - started) * 1000)
    cpu_seconds = time.process_time() - cpu_started
    updater.clear_mission_metrics(current)
    ordered = sorted(durations)
    print(
        json.dumps(
            {
                "python": platform.python_version(),
                "platform": platform.platform(),
                "switches": args.switches,
                "scrapes": args.scrapes,
                "active": active,
                "cleared": counts(),
                "retained_python_bytes_delta": memory,
                "peak_rss_kib": __import__("resource").getrusage(0).ru_maxrss,
                "mutation_seconds": mutation_seconds,
                "scrape_cpu_seconds": cpu_seconds,
                "scrape_ms": {
                    "p50": median(durations),
                    "p95": ordered[int(len(ordered) * 0.95) - 1],
                    "p99": ordered[int(len(ordered) * 0.99) - 1],
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
