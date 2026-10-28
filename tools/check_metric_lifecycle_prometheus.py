#!/usr/bin/env python3
"""Real 1 Hz Prometheus control, with task-owned Compose resources and teardown."""

import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exporter-image",
        required=True,
        help="backend image containing the production dependencies",
    )
    parser.add_argument("--backend-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--baseline", action="store_true", help="record known stale baseline behavior"
    )
    args = parser.parse_args()
    project = f"issue393-{os.getpid()}"
    fixture = Path(__file__).with_name("benchmark_metric_lifecycle.py").resolve()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    args.output.mkdir(parents=True, exist_ok=True)

    def docker(*command):
        return subprocess.check_output(["docker", *command], text=True, timeout=120)

    def request(url, post=False):
        req = urllib.request.Request(url, method="POST" if post else "GET")
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.load(response)

    with tempfile.TemporaryDirectory(prefix=f"{project}-") as directory:
        root = Path(directory)
        root.chmod(0o755)
        config = root / "prometheus.yml"
        config.write_text("""global:
  scrape_interval: 1s
scrape_configs:
  - job_name: synthetic-lifecycle
    static_configs:
      - targets: ['exporter:8000']
  - job_name: prometheus
    static_configs:
      - targets: ['localhost:9090']
""")
        compose = root / "compose.json"
        compose.write_text(
            json.dumps(
                {
                    "services": {
                        "exporter": {
                            "image": args.exporter_image,
                            "entrypoint": ["runuser", "-u", "appuser", "--", "python"],
                            "command": [
                                "/fixture.py",
                                "--backend-root",
                                "/source",
                                "--serve",
                                "8000",
                            ],
                            "volumes": [
                                f"{fixture}:/fixture.py:ro",
                                f"{args.backend_root.resolve()}:/source:ro",
                            ],
                            "environment": {"PYTHONDONTWRITEBYTECODE": "1"},
                            "ports": ["127.0.0.1::8000"],
                        },
                        "prometheus": {
                            "image": "prom/prometheus:v3.5.0",
                            "volumes": [
                                f"{config}:/etc/prometheus/prometheus.yml:ro",
                                "tsdb:/prometheus",
                            ],
                            "ports": ["127.0.0.1::9090"],
                        },
                    },
                    "volumes": {"tsdb": {}},
                }
            )
        )
        command = ["compose", "-p", project, "-f", str(compose)]
        (args.output / "owner.json").write_text(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "pgid": os.getpgrp(),
                    "project": project,
                    "temporary_paths": [str(root)],
                    "volumes": [f"{project}_tsdb"],
                    "exporter_image": args.exporter_image,
                    "backend_root": str(args.backend_root),
                },
                indent=2,
            )
        )
        try:
            docker(*command, "up", "-d")
            exporter = "http://" + docker(*command, "port", "exporter", "8000").strip()
            prometheus = (
                "http://" + docker(*command, "port", "prometheus", "9090").strip()
            )

            def query(expression):
                return request(
                    prometheus
                    + "/api/v1/query?"
                    + urllib.parse.urlencode({"query": expression})
                )["data"]["result"]

            deadline = time.monotonic() + 30
            while True:
                try:
                    if query('up{job="synthetic-lifecycle"}')[0]["value"][1] == "1":
                        break
                except (OSError, ValueError, IndexError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Prometheus did not establish a healthy scrape")
                time.sleep(0.2)
            before = time.time()
            for index in (0, 1):
                request(f"{exporter}/switch/{index}", post=True)
                time.sleep(2.2)
                current = query("mission_active_info")
                if not args.baseline:
                    assert len(current) == 1, current
                    assert current[0]["metric"]["mission_id"] == f"synthetic-{index}"
                    assert current[0]["value"][1] == "1"
                assert len(query("mission_comm_state == 0")) == 3
                assert len(query("mission_phase_state == 1")) == 1
            for index in range(2, 202):
                result = request(f"{exporter}/switch/{index}", post=True)
                if not args.baseline:
                    assert result["mission_samples"] == 9, result
            time.sleep(10.2)
            before_clear = query("mission_active_info")
            if not args.baseline:
                assert len(before_clear) == 1
            latency = {
                str(q): query(
                    f'quantile_over_time({q},scrape_duration_seconds{{job="synthetic-lifecycle"}}[10s])'
                )
                for q in (0.5, 0.95, 0.99)
            }
            request(exporter + "/clear", post=True)
            time.sleep(2.2)
            after_clear = query("mission_active_info")
            if args.baseline:
                assert len(after_clear) > 1
            else:
                assert after_clear == []
            assert (
                query(
                    'starlink_network_latency_ms_count{mode="simulation",status="good"}'
                )[0]["value"][1]
                == "1"
            )
            history = query("count_over_time(mission_active_info[5m])")
            assert {"synthetic-0", "synthetic-1"} <= {
                item["metric"]["mission_id"] for item in history
            }, history
            evidence = {
                "project": project,
                "seconds": time.time() - before,
                "switches": 202,
                "baseline": args.baseline,
                "current_mission_info_series_before_clear": len(before_clear),
                "current_mission_info_series_after_clear": len(after_clear),
                "scrape_duration_quantiles_seconds_last_10s": latency,
                "retained_history_identity_count": len(history),
                "retained_history": [
                    item
                    for item in history
                    if item["metric"].get("route_id")
                    in ("renamed-route-0", "renamed-route-1")
                ],
                "scrape_up": query("up"),
                "scrape_duration": query("scrape_duration_seconds"),
                "scrape_samples": query("scrape_samples_scraped"),
                "tsdb_head_series_including_retained_history": query(
                    "prometheus_tsdb_head_series"
                ),
                "images": json.loads(docker(*command, "images", "--format", "json")),
            }
            (args.output / "prometheus.json").write_text(json.dumps(evidence, indent=2))
            print(json.dumps(evidence, indent=2))
        finally:
            try:
                (args.output / "compose.log").write_text(
                    docker(*command, "logs", "--no-color")
                )
            finally:
                docker(*command, "down", "--volumes", "--remove-orphans")
            for kind, flag in (
                ("container", "-aq"),
                ("network", "-q"),
                ("volume", "-q"),
            ):
                remaining = docker(
                    kind,
                    "ls",
                    flag,
                    "--filter",
                    f"label=com.docker.compose.project={project}",
                ).strip()
                assert not remaining, (kind, remaining)
            (args.output / "cleanup.json").write_text(
                json.dumps({"project": project, "remaining": []})
            )


if __name__ == "__main__":
    main()
