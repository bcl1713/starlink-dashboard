#!/usr/bin/env python3
"""Archive an exact application SHA; reuse owned production-image acceptance."""

import argparse
import hashlib
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/acceptance/operator-journal"))
from identity import fingerprints
from lifecycle import verify_browser
from ownership import Owner, free_port
from report import VERSION, summarize


def run(args):
    if args.output.exists():
        raise ValueError("Evidence is immutable: select a new output directory")
    sha = subprocess.check_output(
        ["git", "rev-parse", args.sha + "^{commit}"], cwd=ROOT, text=True, timeout=30
    ).strip()
    harness_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=30
    ).strip()
    if subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=ROOT,
        text=True,
        timeout=30,
    ).strip():
        raise ValueError("Commit harness inputs before recording baseline evidence")
    source_hashes = fingerprints(ROOT, (HERE, ROOT / "tools/acceptance/performance"))
    owner = Owner(args.project, args.output)
    owner.deadline = time.monotonic() + args.total_timeout
    owner.compose_file = owner.root / "compose.json"
    source, archive = owner.root / "source", owner.root / "source.tar"
    port, prom_port = free_port(), free_port()
    while prom_port == port:
        prom_port = free_port()
    owner.ownership.update(
        composeFile=str(owner.compose_file),
        port=port,
        prometheusPort=prom_port,
        temporaryPaths=[str(source), str(archive)],
        volumes=[f"{args.project}_{v}" for v in ("data", "routes", "metrics")],
        fixture="perf390-v1; fictional ocean route; real clock; two missions/two legs; six Operator records",
    )
    handlers = {
        s: signal.signal(s, owner.signal) for s in (signal.SIGINT, signal.SIGTERM)
    }
    result = {
        "candidate_sha": sha,
        "harness_sha": harness_sha,
        "status": "failed",
        "availability_contract": VERSION,
        "harness_files_sha256": source_hashes,
    }
    try:
        owner.admit()
        owner.execute(
            ["git", "archive", "--format=tar", f"--output={archive}", sha], timeout=60
        )
        result["source_archive_sha256"] = hashlib.sha256(
            archive.read_bytes()
        ).hexdigest()
        source.mkdir()
        with tarfile.open(archive) as bundle:
            bundle.extractall(source, filter="data")
        tags = {
            kind: f"{args.project}-{kind}:{sha}" for kind in ("backend", "frontend")
        }
        services = {
            "starlink-location": {
                "image": tags["backend"],
                "command": [
                    "uvicorn",
                    f"performance.{'probe' if args.instrumentation == 'counters' else 'fixture'}:app",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "8000",
                ],
                "environment": {
                    "PYTHONPATH": "/acceptance:/app",
                    "PERF_SYNTHETIC": "1",
                    "STARLINK_MODE": "simulation",
                    "SIMULATION_MODE": "true",
                    "OPERATOR_ENABLED": "true",
                    "STARLINK_PROMETHEUS_URL": "http://prometheus:9090",
                    "STARLINK_ROUTE_LATITUDE_START": "0",
                    "STARLINK_ROUTE_LONGITUDE_START": "-10",
                    "STARLINK_GROUND_ENTRY_LATITUDE": "0",
                    "STARLINK_GROUND_ENTRY_LONGITUDE": "0",
                    "NO_PROXY": "prometheus,localhost,127.0.0.1",
                },
                "volumes": [
                    "data:/app/data",
                    "routes:/data",
                    f"{HERE}:/acceptance/performance:ro",
                    f"{ROOT}/tools/acceptance/performance:/acceptance/strict_performance:ro",
                    f"{source}/tools/acceptance/operator-journal:/acceptance/journal:ro",
                    f"{source}/tools/acceptance/overview_history:/acceptance/overview_history:ro",
                ],
                "healthcheck": {
                    "test": ["CMD", "curl", "-f", "http://localhost:8000/health"],
                    "interval": "2s",
                    "timeout": "5s",
                    "retries": 60,
                },
            },
            "prometheus": {
                "image": "prom/prometheus:v3.5.0",
                "ports": [f"127.0.0.1:{prom_port}:9090"],
                "volumes": [
                    "metrics:/prometheus",
                    f"{source}/monitoring/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro",
                    f"{source}/monitoring/prometheus/rules:/etc/prometheus/rules:ro",
                    f"{owner.root}/history.openmetrics:/seed/history.openmetrics:ro",
                ],
                "command": [
                    "--config.file=/etc/prometheus/prometheus.yml",
                    "--storage.tsdb.retention.time=12h",
                    "--storage.tsdb.path=/prometheus",
                ],
            },
            "mission-planner": {
                "image": tags["frontend"],
                "ports": [f"127.0.0.1:{port}:80"],
                "depends_on": {"starlink-location": {"condition": "service_healthy"}},
            },
        }
        for service in services.values():
            service.update(cpus=args.cpus, mem_limit=args.memory)
        config = {
            "services": services,
            "volumes": {v: {} for v in ("data", "routes", "metrics")},
        }
        owner.compose_file.write_text(json.dumps(config, indent=2))
        owner.persist()
        result["hardware"] = {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu": next(
                (
                    l.split(":", 1)[1].strip()
                    for l in Path("/proc/cpuinfo").read_text().splitlines()
                    if l.startswith("model name")
                ),
                "unknown",
            ),
            "docker": json.loads(
                owner.execute(["docker", "info", "--format", "{{json .}}"], timeout=30)
            ),
        }
        # Retain only non-secret, reproducibility-relevant daemon attributes.
        result["hardware"]["docker"] = {
            k: result["hardware"]["docker"].get(k)
            for k in (
                "ServerVersion",
                "Driver",
                "NCPU",
                "MemTotal",
                "KernelVersion",
                "OperatingSystem",
                "Architecture",
            )
        }
        result["hardware"]["filesystem"] = owner.execute(
            ["stat", "-f", "-c", "%T %S", str(owner.root)], timeout=10
        ).strip()
        for kind, dockerfile, context in (
            ("backend", source / "backend/starlink-location/Dockerfile", source),
            (
                "frontend",
                source / "frontend/mission-planner/Dockerfile",
                source / "frontend/mission-planner",
            ),
        ):
            owner.ownership["images"].append(tags[kind])
            owner.persist()
            command = [
                "docker",
                "build",
                "-f",
                str(dockerfile),
                "--build-arg",
                f"ACCEPTANCE_CANDIDATE_SHA={sha}",
                "-t",
                tags[kind],
            ]
            if ca := os.environ.get("CODEX_PROXY_CERT"):
                command += ["--secret", f"id=proxy_ca,src={ca}"]
            owner.execute([*command, str(context)], timeout=2700)
        result["images"] = {}
        for kind, tag in tags.items():
            image = json.loads(
                owner.execute(
                    ["docker", "image", "inspect", tag, "--format", "{{json .}}"],
                    timeout=30,
                )
            )
            if (
                image["Config"]["Labels"].get("org.opencontainers.image.revision")
                != sha
            ):
                raise ValueError("Image revision differs from candidate")
            result["images"][kind] = {
                "tag": tag,
                "id": image["Id"],
                "revision": sha,
                "filesystem_config_sha256": hashlib.sha256(
                    json.dumps(
                        {"RootFS": image["RootFS"], "Config": image["Config"]},
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
            }
        owner.execute(
            [
                sys.executable,
                str(source / "tools/acceptance/overview_history/seed.py"),
                "--output",
                str(owner.root / "history.openmetrics"),
                "--end",
                str(int(time.time()) - 20),
            ],
            timeout=30,
        )
        os.chmod(owner.root / "history.openmetrics", 0o644)
        owner.compose(
            "run",
            "--rm",
            "--no-deps",
            "--entrypoint",
            "/bin/promtool",
            "prometheus",
            "tsdb",
            "create-blocks-from",
            "openmetrics",
            "/seed/history.openmetrics",
            "/prometheus",
            timeout=120,
        )
        owner.compose(
            "up", "-d", "--no-build", "--wait", "--wait-timeout", "180", timeout=210
        )
        containers = {
            name: owner.compose("ps", "-q", name, timeout=15).strip()
            for name in services
        }
        dependencies = owner.execute(
            [
                "docker",
                "exec",
                "--user",
                "appuser",
                containers["starlink-location"],
                "python",
                "-m",
                "pip",
                "--disable-pip-version-check",
                "list",
                "--format=json",
            ],
            timeout=30,
        )
        (owner.root / "backend-packages.json").write_text(dependencies)
        result["backend_python"] = owner.execute(
            ["docker", "exec", containers["starlink-location"], "python", "--version"],
            timeout=15,
        ).strip()
        result["backend_packages_sha256"] = hashlib.sha256(
            dependencies.encode()
        ).hexdigest()
        result["fixture_hashes"] = {}
        for relative in (
            "backend/starlink-location/config.yaml",
            "monitoring/prometheus/prometheus.yml",
            "tools/acceptance/operator-journal/scenario.py",
            "tools/acceptance/overview_history/seed.py",
        ):
            result["fixture_hashes"][relative] = hashlib.sha256(
                (source / relative).read_bytes()
            ).hexdigest()
        result["images"]["prometheus"] = json.loads(
            owner.execute(
                [
                    "docker",
                    "inspect",
                    containers["prometheus"],
                    "--format",
                    "{{json .Image}}",
                ],
                timeout=15,
            )
        )
        # Existing relay supports rootless hosts without published-port forwarding.
        published = json.loads(
            owner.execute(
                [
                    "docker",
                    "inspect",
                    containers["mission-planner"],
                    "--format",
                    "{{json .NetworkSettings.Ports}}",
                ],
                timeout=15,
            )
        )
        if not published.get("80/tcp"):
            owner.env.update(
                OPERATOR_SOURCE_ROOT=str(source), OPERATOR_ACCEPTANCE_PORT=str(port)
            )
            owner.start_relay(containers["mission-planner"])
        owner.env.update(
            PERF_RUN=json.dumps(
                {
                    "origin": f"http://127.0.0.1:{port}",
                    "prometheus_origin": f"http://127.0.0.1:{prom_port}",
                    "availability_contract": VERSION,
                    "harness_sha": harness_sha,
                    "workload": args.workload,
                    "containers": containers,
                    "output": str(owner.root),
                    "viewers": args.viewers,
                    "operator": args.operator,
                    "window": args.window,
                    "warmup": args.warmup,
                    "duration": args.duration,
                    "instrumentation": args.instrumentation,
                    "operations": args.operations,
                    "fullscreen": args.fullscreen,
                    "root": str(ROOT),
                }
            )
        )
        result.update(
            workload={
                "fixture": "perf390-v1",
                "kind": args.workload,
                "availability_contract": VERSION,
                "availability_observer_hz": 1,
                "fixture_hashes": result["fixture_hashes"],
                "viewers": args.viewers,
                "operator": args.operator,
                "window": args.window,
                "cadence": 1,
                "warmup": args.warmup,
                "duration": args.duration,
                "operations": args.operations,
                "fullscreen": args.fullscreen,
            },
            instrumentation=args.instrumentation,
            runtime={
                "mode": "simulation",
                "backend_python": result["backend_python"],
                "backend_packages_sha256": result["backend_packages_sha256"],
                "scrape_seconds": 1,
                "evaluation_seconds": 1,
                "cpus_per_service": args.cpus,
                "memory_limit": args.memory,
                "viewport": [1920, 1080],
                "dpr": 1,
                "optional_layers": "default-off",
                "transport": "exec-relay" if owner.relay else "published-port",
            },
        )
        owner.execute(
            ["node", str(HERE / "browser.mjs")],
            timeout=args.warmup + args.duration + 120,
        )
        if args.instrumentation == "counters":
            for name in ("tick", "metrics"):
                owner.execute(
                    [
                        "docker",
                        "cp",
                        f"{containers['starlink-location']}:/data/perf-{name}.prof",
                        str(owner.root / f"{name}.prof"),
                    ],
                    timeout=30,
                )
        result["availability"] = json.loads(
            (owner.root / "availability-result.json").read_text()
        )
        if result["availability"].get("status") != "passed":
            raise ValueError("Availability verification failed")
        result["browser"] = json.loads((owner.root / "browser.json").read_text())
        result["runtime"]["history_step_seconds"] = result["browser"][
            "history_step_seconds"
        ]
        result["request_outcomes"] = json.loads(
            (owner.root / "request-outcomes.json").read_text()
        )
        rows = [
            json.loads(line)
            for line in (owner.root / "samples.jsonl").read_text().splitlines()
        ]
        result["status"] = "measured"
        (owner.root / "summary.json").write_text(
            json.dumps(summarize(result, rows), indent=2, allow_nan=False)
        )
    finally:
        try:
            try:
                if owner.admitted and owner.compose_file.exists():
                    owner.compose("logs", "--no-color", timeout=30)
            finally:
                try:
                    result["browser_cleanup"] = verify_browser(owner.root)
                finally:
                    result["cleanup"] = owner.close()
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", prom_port))
            result["cleanup"]["prometheusListenerRemoved"] = True
        finally:
            (owner.root / "run.json").write_text(
                json.dumps(result, indent=2, allow_nan=False)
            )
            owner.release()
            for s, handler in handlers.items():
                signal.signal(s, handler)
    print(
        json.dumps(
            {
                "status": result["status"],
                "output": str(owner.root),
                "cleanup": result["cleanup"],
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument(
        "--project", required=True, help="private starlink-operator-perf390-... name"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--viewers", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument("--operator", action="store_true")
    parser.add_argument(
        "--workload", choices=("steady", "transitions"), default="steady"
    )
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="request the actual app fullscreen layout",
    )
    parser.add_argument(
        "--operations",
        action="store_true",
        help="mission switch and journal write at deterministic measured offsets",
    )
    parser.add_argument("--window", type=int, choices=(1800,), default=1800)
    parser.add_argument("--warmup", type=int, default=60)
    parser.add_argument("--duration", type=int, default=600)
    parser.add_argument("--total-timeout", type=int, default=5400)
    parser.add_argument("--cpus", type=float, default=2)
    parser.add_argument("--memory", default="2g")
    parser.add_argument("--instrumentation", choices=("off", "counters"), default="off")
    args = parser.parse_args()
    if args.operations and args.workload != "transitions":
        parser.error("--operations requires the separate --workload transitions")
    if args.workload == "transitions":
        args.operations = True
    if (
        args.duration < 1
        or args.warmup < 0
        or args.total_timeout <= args.duration + args.warmup
        or args.cpus <= 0
    ):
        parser.error(
            "positive duration/CPU, nonnegative warmup, and a total timeout with setup allowance required"
        )
    run(args)
