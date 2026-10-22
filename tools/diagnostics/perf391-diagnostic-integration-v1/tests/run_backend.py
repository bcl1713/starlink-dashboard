"""Own one bounded offline unittest child; no application/service lifecycle.

The outer GNU timeout is still required. SIGINT/TERM forwards only to the owned
child process group and reaps it. Output/owner files must live in a fresh path.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def start_id(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def run(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable,
        "-B",
        "-m",
        "coverage",
        "run",
        "--branch",
        "--source=backend_probe,workers,build,contract",
        "-m",
        "unittest",
        "discover",
        "-v",
        "-s",
        "tests",
        "-p",
        "test_*.py",
    ]
    owner = {
        "purpose": "Stage 2 offline tests only",
        "command": command,
        "owner_pid": os.getpid(),
        "owner_pgid": os.getpgrp(),
        "owner_start": start_id(os.getpid()),
        "child": None,
        "deadline_seconds": 180,
        "services": [],
        "listeners": [],
        "containers": [],
        "networks": [],
        "volumes": [],
        "status": "starting",
    }

    def persist():
        temp = output / "owner.tmp"
        temp.write_text(json.dumps(owner, indent=2) + "\n")
        temp.replace(output / "owner.json")

    persist()
    child = None
    interrupted = [None]

    def stop(signum, frame):
        interrupted[0] = signum
        if child is not None and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop)
    with (output / "tests.log").open("w") as log:
        try:
            env = {
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "COVERAGE_FILE": str((output / "coverage.data").resolve()),
            }
            child = subprocess.Popen(
                command,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,
            )
            owner["child"] = {
                "pid": child.pid,
                "pgid": child.pid,
                "start": start_id(child.pid),
            }
            owner["status"] = "running"
            persist()
            deadline = time.monotonic() + 180
            while child.poll() is None:
                if interrupted[0] is not None or time.monotonic() >= deadline:
                    os.killpg(child.pid, signal.SIGTERM)
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=2)
                    break
                try:
                    child.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    pass
            owner["returncode"] = child.returncode
            returncode = (
                child.returncode if interrupted[0] is None else 128 + interrupted[0]
            )
        finally:
            if child is not None and child.poll() is None:
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=2)
            if child is not None:
                rows = subprocess.check_output(
                    ["ps", "-eo", "pid=,pgid=,stat="], text=True
                )
                survivors = [
                    line.strip()
                    for line in rows.splitlines()
                    if int(line.split()[1]) == child.pid
                    and not line.split()[2].startswith("Z")
                ]
                owner["live_group_survivors"] = survivors
                owner["status"] = "clean" if not survivors else "cleanup_failed"
            persist()
    print(json.dumps(owner, indent=2))
    return returncode if owner["status"] == "clean" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(run(parser.parse_args().output))
