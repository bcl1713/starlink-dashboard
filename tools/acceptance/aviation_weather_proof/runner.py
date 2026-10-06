"""Exact-candidate diagnostic lifecycle. Run through run.sh's wall-clock limit."""

from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from acceptance.platform.evidence import (
    prepare_evidence_parent,
    read_fingerprint_authority,
    seal_fingerprint,
    verify_manifest,
    write_artifacts,
)

from .lifecycle import Deadline, enable_subreaper, stop_owned_groups
from .report import evaluate_proofs

ROOT = Path(__file__).resolve().parents[3]
PROJECT = "starlink-290-aviation-proof"
IMAGE = "sha256:da6d08532bcd1336d6f3d217859700c96b32efa31c47ac2b6b43b5d3d58bed9a"


def prepare_fixture_mount(products: Path) -> None:
    """Permit app UID traversal inside the read-only normalized-only bind mount."""
    for path in (products, *products.rglob("*")):
        if path.is_symlink():
            raise ValueError("fixture mount cannot contain symlinks")
        path.chmod(0o755 if path.is_dir() else 0o644)


def wait_ports_free(ports: list[int], *, seconds: float = 65) -> dict:
    """Require the original exclusive-bind criterion after bounded teardown lag."""
    start = time.monotonic()
    observations = []
    while True:
        failures = {}
        for port in ports:
            try:
                with socket.socket() as listener:
                    listener.bind(("127.0.0.1", port))
            except OSError as error:
                failures[port] = str(error)
        if not failures:
            return {
                "remaining": [],
                "observations": observations,
                "elapsed_seconds": time.monotonic() - start,
            }
        rows = []
        inodes = set()
        for table in ("tcp", "tcp6"):
            for line in (Path("/proc/net") / table).read_text().splitlines()[1:]:
                fields = line.split()
                if int(fields[1].rsplit(":", 1)[1], 16) in failures:
                    rows.append({"table": table, "entry": line.strip()})
                    inodes.add(fields[9])
        owners = []
        if not observations:
            for process in Path("/proc").iterdir():
                if not process.name.isdigit():
                    continue
                try:
                    for fd in (process / "fd").iterdir():
                        link = os.readlink(fd)
                        if link.startswith("socket:[") and link[8:-1] in inodes:
                            owners.append(
                                {
                                    "pid": int(process.name),
                                    "pgid": os.getpgid(int(process.name)),
                                    "comm": (process / "comm").read_text().strip(),
                                    "socket": link,
                                }
                            )
                except (OSError, ProcessLookupError):
                    continue
        observations.append(
            {
                "at_ms": int(time.time() * 1000),
                "bind_errors": failures,
                "kernel_sockets": rows,
                "owners": owners,
            }
        )
        if time.monotonic() - start >= seconds:
            return {
                "remaining": [f"listener:{p}" for p in failures],
                "observations": observations,
                "elapsed_seconds": time.monotonic() - start,
            }
        time.sleep(max(0, min(0.25, seconds - (time.monotonic() - start))))


def cleanup_owned_runtime(output, owner, budget, *, compose, env, ports):
    """Stop runtimes first; bound each step and retain receipts even on failure."""
    budget.begin_cleanup()
    errors = []
    killed = list(owner.get("killed_descendants", []))
    killed_containers = []
    commands = []

    def command(argv, name, seconds=20):
        record = {"command": argv, "name": name, "state": "starting"}
        commands.append(record)
        (output / "cleanup-commands.json").write_text(json.dumps(commands, indent=2))
        with (output / (name + ".log")).open("wb") as log:
            child = subprocess.Popen(
                argv,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            record.update(pid=child.pid, pgid=child.pid)
            (output / "cleanup-commands.json").write_text(
                json.dumps(commands, indent=2)
            )
            try:
                code = budget.wait(child, seconds, reserve=2)
                if code:
                    raise RuntimeError(f"{name} exited {code}")
            finally:
                stopped = stop_owned_groups(
                    [child.pid], grace=0.1, seconds=min(0.5, budget.remaining(2))
                )
                killed.extend(stopped["killed_descendants"])
                errors.extend(f"process:{pid}" for pid in stopped["remaining"])
                child.poll()
                record["returncode"] = child.returncode
                (output / "cleanup-commands.json").write_text(
                    json.dumps(commands, indent=2)
                )

    def attempt(operation):
        try:
            return operation()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error))
            return None

    groups = [
        c["pgid"]
        for c in owner["children"]
        if "pgid" in c and not c.get("group_reaped")
    ]
    browser_owner = output / "browser" / "browser-owner.json"
    if browser_owner.exists():
        browser = json.loads(browser_owner.read_text())
        groups.extend(
            [browser["browser_pgid"], browser.get("xvfb_pgid", browser["xvfb_pid"])]
        )
    stopped = stop_owned_groups(groups, grace=0.5, seconds=min(1, budget.remaining(3)))
    killed.extend(stopped["killed_descendants"])
    errors.extend(f"process:{pid}" for pid in stopped["remaining"])

    # Stop/remove recorded workers in one bounded operation, not one grace per worker.
    existing = []
    for name in owner["workers"]:
        try:
            result = subprocess.run(
                ["docker", "inspect", name],
                capture_output=True,
                timeout=max(0.01, min(1, budget.remaining(3))),
                check=False,
            )
            if result.returncode == 0:
                existing.append(name)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error))
    if existing:
        attempt(
            lambda: command(
                ["docker", "stop", "--time", "1", *existing], "workers-stop", 2
            )
        )
        for name in existing:
            try:
                result = subprocess.run(
                    ["docker", "inspect", name],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=max(0.01, min(0.5, budget.remaining(2))),
                )
                if json.loads(result.stdout)[0]["State"]["ExitCode"] == 137:
                    killed_containers.append(name)
            except (
                OSError,
                ValueError,
                RuntimeError,
                subprocess.SubprocessError,
            ) as error:
                errors.append(str(error))
        attempt(lambda: command(["docker", "rm", *existing], "workers-remove", 1))
    if compose:
        attempt(
            lambda: command(
                [*compose, "down", "--volumes", "--remove-orphans", "--timeout", "1"],
                "compose-cleanup",
                45 if not budget.interrupted else 2,
            )
        )
    remnants = {}
    queries = (
        {
            "containers": ["docker", "ps", "-aq"],
            "networks": ["docker", "network", "ls", "-q"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }
        if compose
        else {}
    )
    for kind, argv in queries.items():
        try:
            result = subprocess.run(
                [*argv, "--filter", f"label=com.docker.compose.project={PROJECT}"],
                capture_output=True,
                text=True,
                check=True,
                timeout=max(0.01, min(2, budget.remaining(2))),
            )
            remnants[kind] = result.stdout.split()
            errors.extend(f"{kind}:{item}" for item in remnants[kind])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error))
    for name in existing:
        try:
            result = subprocess.run(
                ["docker", "inspect", name],
                capture_output=True,
                timeout=max(0.01, min(1, budget.remaining(2))),
                check=False,
            )
            if result.returncode == 0:
                errors.append(f"worker:{name}")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            errors.append(str(error))
    port_result = wait_ports_free(
        ports, seconds=0 if budget.interrupted else min(65, budget.remaining(3))
    )
    (output / "port-cleanup.json").write_text(json.dumps(port_result, indent=2))
    errors.extend(port_result["remaining"])
    receipt = {
        "status": (
            "passed"
            if not errors and not killed and not killed_containers
            else "failed"
        ),
        "remaining": errors,
        "killed_descendants": sorted(set(killed)),
        "docker": remnants,
        "killed_containers": killed_containers,
        "ports": ports,
        "verified_at_ms": int(time.time() * 1000),
    }
    (output / "cleanup.json").write_text(json.dumps(receipt, indent=2))
    return receipt


def publish_evidence(stage, output, candidate, evidence_root=None):
    result = evaluate_proofs(output)
    if (output / "failure.json").exists():
        result["runner_error"] = json.loads((output / "failure.json").read_text())[
            "error"
        ]
        result["status"] = "failed"
    (output / "evaluation.json").write_text(json.dumps(result, indent=2))
    root = evidence_root or Path(
        "/srv/starlink-acceptance/evidence/issue-290/diagnostic"
    )
    parent = prepare_evidence_parent(root / stage.name)
    sealed = parent / candidate
    artifacts = {
        str(p.relative_to(output)): p.read_bytes()
        for p in output.rglob("*")
        if p.is_file()
    }
    write_artifacts(sealed, artifacts)
    seal_fingerprint(
        sealed,
        json.dumps(
            {
                "candidate": candidate,
                "diagnostic_only": True,
                "status": result["status"],
                "source_stage": str(stage),
            },
            sort_keys=True,
        ).encode(),
    )
    verify_manifest(sealed)
    read_fingerprint_authority(sealed)
    print(
        json.dumps(
            {"evidence": str(sealed), "stage": str(stage), "result": result}, indent=2
        ),
        flush=True,
    )
    return 0 if result["status"] == "passed" else 1


def run(candidate: str, captures: Path, profile: Path, budget: Deadline) -> int:
    enable_subreaper()
    if not re.fullmatch("[0-9a-f]{40}", candidate):
        raise ValueError("clean 40-hex SHA required")
    if (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        != candidate
        or subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=ROOT,
            text=True,
        ).strip()
    ):
        raise ValueError("candidate must be clean tracked HEAD")
    for port in (15290, 18290):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", port))
    label = f"com.docker.compose.project={PROJECT}"

    def remaining():
        return {
            kind: subprocess.check_output(command, text=True).split()
            for kind, command in {
                "containers": ["docker", "ps", "-aq", "--filter", f"label={label}"],
                "networks": [
                    "docker",
                    "network",
                    "ls",
                    "-q",
                    "--filter",
                    f"label={label}",
                ],
                "volumes": [
                    "docker",
                    "volume",
                    "ls",
                    "-q",
                    "--filter",
                    f"label={label}",
                ],
            }.items()
        }

    if any(remaining().values()):
        raise ValueError("existing private project cannot be adopted")
    stage = Path(tempfile.mkdtemp(prefix="starlink-290-task5-attempt-"))
    os.chmod(stage, 0o700)
    source = stage / "source"
    source.mkdir()
    output = stage / "evidence"
    output.mkdir()
    children: list[dict] = []
    workers: list[str] = []
    killed: list[int] = []
    active = None
    started = False
    failure = None
    owner = {
        "candidate": candidate,
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "command": sys.argv,
        "project": PROJECT,
        "ports": [15290, 18290],
        "temporary_paths": [str(stage)],
        "private_volumes": [
            "missions",
            "settings",
            "satellites",
            "coverage",
            "routes",
            "simulation-routes",
            "pois",
            "metrics",
        ],
        "workers": workers,
        "children": children,
    }

    def write_owner():
        (output / "runtime-owner.json").write_text(json.dumps(owner, indent=2))

    write_owner()

    def command(argv: list[str], name: str, seconds=120, env=None):
        nonlocal active
        with (output / (name + ".log")).open("wb") as log:
            children.append({"command": argv, "name": name, "state": "starting"})
            write_owner()
            active = subprocess.Popen(
                argv,
                cwd=ROOT,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            children[-1].update(pid=active.pid, pgid=active.pid)
            write_owner()
            try:
                code = budget.wait(active, seconds)
                if code:
                    raise RuntimeError(f"{name} exit {code}; {log.name}")
            finally:
                stopped = stop_owned_groups(
                    [active.pid], grace=1.5, seconds=min(2, budget.remaining(3))
                )
                killed.extend(stopped["killed_descendants"])
                children[-1]["group_reaped"] = not stopped["remaining"]
                if stopped["remaining"]:
                    children[-1]["remaining"] = stopped["remaining"]
                active.poll()
                children[-1]["returncode"] = active.returncode
                write_owner()
                active = None

    env = {
        **os.environ,
        "WEATHER_ACCEPTANCE_PROJECT": PROJECT,
        "WEATHER_ACCEPTANCE_FRONTEND_PORT": "15290",
        "WEATHER_ACCEPTANCE_BACKEND_PORT": "18290",
        "WEATHER_ACCEPTANCE_SOURCE_ROOT": str(source),
        "WEATHER_ACCEPTANCE_CAPTURE_DIR": str(output / "products"),
        "WEATHER_ACCEPTANCE_CONTROL_DIR": str(output / "control"),
        "WEATHER_ACCEPTANCE_MODE": "aviation-proof",
        "ACCEPTANCE_CANDIDATE_SHA": candidate,
    }
    compose = [
        "docker",
        "compose",
        "-p",
        PROJECT,
        "-f",
        str(ROOT / "tools/acceptance/overview-weather/compose.yml"),
    ]

    def worker(mode, name):
        worker_name = f"{PROJECT}-{mode}-{name}"
        workers.append(worker_name)
        write_owner()
        args = [
            "docker",
            "create",
            "--name",
            worker_name,
            "--label",
            f"{PROJECT}.owner={candidate}",
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "1g",
            "--memory-swap",
            "1g",
            "--pids-limit",
            "64",
            "--entrypoint",
            "python",
            "--mount",
            f"type=bind,src={source}/tools,dst=/work/tools,readonly",
            "--mount",
            f"type=bind,src={output},dst=/evidence",
            "--mount",
            f"type=bind,src={output}/captures,dst=/evidence/captures,readonly",
            "-w",
            "/work",
            "-e",
            "PYTHONPATH=/work/tools",
            "-e",
            "OPENBLAS_NUM_THREADS=1",
            "-e",
            "OMP_NUM_THREADS=1",
            IMAGE,
            "-m",
            "acceptance.aviation_weather_proof.worker",
            mode,
            name,
            "/evidence",
        ]
        command(args, f"{mode}-{name}-create")
        try:
            command(
                [
                    "timeout",
                    "--kill-after=10s",
                    "120s",
                    "docker",
                    "start",
                    "--attach",
                    worker_name,
                ],
                f"{mode}-{name}",
                135,
            )
            command(["docker", "inspect", worker_name], f"{mode}-{name}-inspect")
            info = json.loads((output / f"{mode}-{name}-inspect.log").read_text())[0]
            if info["State"]["ExitCode"] != 0 or info["State"]["OOMKilled"]:
                raise RuntimeError("scientific worker failed")
        finally:
            if not budget.work_stopped:
                command(
                    ["docker", "stop", "--time", "10", worker_name],
                    f"{mode}-{name}-stop",
                    20,
                )
                command(["docker", "rm", worker_name], f"{mode}-{name}-remove")

    try:
        command(
            [
                "git",
                "archive",
                "--format=tar",
                "-o",
                str(stage / "candidate.tar"),
                candidate,
            ],
            "archive",
        )
        command(
            ["tar", "-xf", str(stage / "candidate.tar"), "-C", str(source)], "extract"
        )
        shutil.copytree(captures / "captures", output / "captures")
        for directory in ("products", "oracles", "control", "browser"):
            (output / directory).mkdir()
        (output / "control" / "control.json").write_text("{}")
        os.chmod(output / "control", 0o777)
        os.chmod(output / "control" / "control.json", 0o666)
        for name in ("gfs", "isigmet", "goes19-c13"):
            worker("normalize", name)
        prepare_fixture_mount(output / "products")
        command(
            ["docker", "info", "--format", "{{.ServerVersion}} {{.Name}}"],
            "docker-runtime",
        )
        command(compose + ["config"], "compose", env=env)
        command(
            ["timeout", "--kill-after=10s", "15m", *compose, "build"], "build", 920, env
        )
        started = True
        command(
            compose
            + ["up", "--no-build", "--detach", "--wait", "--wait-timeout", "180"],
            "start",
            210,
            env,
        )
        command(
            [
                "docker",
                "image",
                "inspect",
                f"{PROJECT}-backend:{candidate}",
                f"{PROJECT}-frontend:{candidate}",
            ],
            "images",
        )
        command(
            [
                sys.executable,
                "-m",
                "acceptance.aviation_weather_proof.run_browser",
                "--origin",
                "http://127.0.0.1:15290",
                "--artifacts",
                str(output / "browser"),
                "--profile",
                str(profile),
            ],
            "browser",
            650,
            {**os.environ, "PYTHONPATH": str(ROOT / "tools")},
        )
        for name in ("gfs", "goes19-c13"):
            worker("sample", name)
    except BaseException as error:  # noqa: BLE001
        failure = f"{type(error).__name__}: {error}"
        (output / "failure.json").write_text(json.dumps({"error": failure}))
    finally:
        owner["killed_descendants"] = killed
        try:
            cleanup_owned_runtime(
                output,
                owner,
                budget,
                compose=compose if started else None,
                env=env,
                ports=[15290, 18290],
            )
        except BaseException as error:  # noqa: BLE001
            (output / "cleanup.json").write_text(
                json.dumps(
                    {
                        "status": "failed",
                        "remaining": [str(error)],
                        "killed_descendants": killed,
                    }
                )
            )
    if budget.interrupted and not (output / "failure.json").exists():
        (output / "failure.json").write_text(
            json.dumps({"error": "interrupted during cleanup"})
        )
    (output / "deadline.json").write_text(
        json.dumps(
            {
                "work_seconds": budget.work_seconds,
                "remaining_seconds": budget.remaining(),
                "interrupted": budget.interrupted,
                "work_stopped": budget.work_stopped,
            }
        )
    )
    # Evidence precedes optional disk staging removal, especially after a signal.
    result = publish_evidence(stage, output, candidate)
    if not budget.interrupted and budget.remaining() > 10:
        shutil.rmtree(source)
        (stage / "candidate.tar").unlink(missing_ok=True)
    return result


def main():
    if len(sys.argv) != 4:
        raise ValueError("candidate capture-root profile-path required")
    remaining = min(
        1200,
        float(os.environ.get("AVIATION_PROOF_OUTER_DEADLINE", time.time() + 1200))
        - time.time(),
    )
    if remaining <= 240:
        raise TimeoutError(
            "insufficient time after admission wait; no resources allocated"
        )
    with Deadline(work_seconds=remaining - 240, total_seconds=remaining) as budget:
        return run(
            sys.argv[1],
            Path(sys.argv[2]).resolve(),
            Path(sys.argv[3]).resolve(),
            budget,
        )


if __name__ == "__main__":
    raise SystemExit(main())
