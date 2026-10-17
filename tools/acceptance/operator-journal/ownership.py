"""Task-local ownership for the Operator production acceptance runtime."""

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


class Owner:
    def __init__(self, project, root):
        if not re.fullmatch(r"starlink-operator-[a-z0-9-]+", project):
            raise ValueError("Use a private starlink-operator- project")
        self.project, self.root = project, Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.env = dict(os.environ)
        self.compose_file = ROOT / "tools/acceptance/operator-journal/compose.yml"
        self.child = None
        self.relay = None
        self.cleaning = False
        self.deadline = time.monotonic() + 3600
        self.ownership = {
            "pid": os.getpid(),
            "pgid": os.getpgrp(),
            "project": project,
            "composeFile": str(self.compose_file),
            "commands": [],
            "volumes": [
                f"{project}_{n}"
                for n in ("fixture-data", "operator-data", "route-data")
            ],
            "containers": [],
            "images": [],
            "temporaryPaths": [],
            "dockerHost": os.environ.get("DOCKER_HOST"),
            "dockerContext": os.environ.get("DOCKER_CONTEXT"),
            "fixture": "synthetic-operator-demo-v1; simulation; 2026-10-17T16:00:00Z",
            "evidence": str(self.root),
        }
        self.persist()

    def persist(self):
        pending = self.root / "ownership.pending"
        pending.write_text(json.dumps(self.ownership, indent=2))
        pending.replace(self.root / "ownership.json")

    def execute(self, command, timeout=120, *, cwd=ROOT, env=None):
        if not self.cleaning:
            timeout = min(timeout, self.deadline - time.monotonic())
        if timeout <= 0:
            raise TimeoutError("60-minute acceptance deadline exceeded")
        entry = {
            "command": command,
            "cwd": str(cwd),
            "timeout": timeout,
            "started": time.time(),
            "pid": None,
            "pgid": None,
        }
        self.ownership["commands"].append(entry)
        log = self.root / f"command-{len(self.ownership['commands']):03d}.log"
        entry["log"] = str(log)
        self.persist()
        with log.open("w") as output:
            self.child = subprocess.Popen(
                command,
                cwd=cwd,
                env=env or self.env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            entry.update(pid=self.child.pid, pgid=self.child.pid)
            self.persist()
            started = time.monotonic()
            try:
                while self.child.poll() is None:
                    remaining = timeout - (time.monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError(f"Command timed out: {log}")
                    try:
                        self.child.wait(timeout=min(remaining, 30))
                    except subprocess.TimeoutExpired:
                        print(f"Operator acceptance running: {log.name}", flush=True)
                if self.child.returncode:
                    raise RuntimeError(
                        f"Command failed ({self.child.returncode}): {log}"
                    )
            finally:
                self.stop_child()
                entry.update(
                    returncode=self.child.returncode,
                    reaped=True,
                    groupRemaining=group_alive(self.child.pid),
                    finished=time.time(),
                )
                self.child = None
                self.persist()
        return log.read_text()

    def stop_child(self):
        if self.child is None:
            return
        pgid = self.child.pid
        if group_alive(pgid):
            os.killpg(pgid, signal.SIGTERM)
            deadline = time.monotonic() + 10
            while group_alive(pgid) and time.monotonic() < deadline:
                self.child.poll()
                time.sleep(0.05)
            if group_alive(pgid):
                os.killpg(pgid, signal.SIGKILL)
        self.child.wait(timeout=10)

    def signal(self, signum, _frame):
        self.ownership["signal"] = signum
        self.persist()
        raise InterruptedError(f"Interrupted by {signum}")

    def compose(self, *args, timeout=120):
        return self.execute(
            [
                "docker",
                "compose",
                "-p",
                self.project,
                "-f",
                str(self.compose_file),
                *args,
            ],
            timeout=timeout,
        )

    def start_relay(self, container):
        command = [
            "python3",
            str(
                Path(self.env["OPERATOR_SOURCE_ROOT"])
                / "tools/acceptance/operator-journal/relay.py"
            ),
            "--port",
            self.env["OPERATOR_ACCEPTANCE_PORT"],
            "--",
            "docker",
            "exec",
            "-i",
            container,
            "nc",
            "-w",
            "120",
            "127.0.0.1",
            "80",
        ]
        entry = {
            "command": command,
            "role": "loopback-to-production-nginx",
            "pid": None,
            "pgid": None,
            "log": str(self.root / "relay.log"),
        }
        self.ownership["commands"].append(entry)
        self.persist()
        with (self.root / "relay.log").open("w") as output:
            self.relay = subprocess.Popen(
                command,
                env=self.env,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        entry.update(pid=self.relay.pid, pgid=self.relay.pid)
        self.ownership["relay"] = entry
        self.persist()

    def close(self):
        self.cleaning = True
        self.stop_child()
        if self.relay is not None:
            self.child = self.relay
            self.stop_child()
            self.ownership["relay"].update(
                reaped=True,
                returncode=self.relay.returncode,
                groupRemaining=group_alive(self.relay.pid),
            )
            self.child = self.relay = None
            self.persist()
        # Before build config exists, the original file still needs interpolation.
        self.env.setdefault("ACCEPTANCE_CANDIDATE_SHA", "0" * 40)
        self.env.setdefault("OPERATOR_SOURCE_ROOT", str(ROOT))
        self.env.setdefault("OPERATOR_ACCEPTANCE_PORT", "1")
        self.compose("down", "--volumes", "--remove-orphans", timeout=90)
        for container in self.ownership["containers"]:
            existing = self.execute(
                [
                    "docker",
                    "ps",
                    "-aq",
                    "--filter",
                    f"name=^/{container}$",
                    "--filter",
                    f"label=com.docker.compose.project={self.project}",
                ],
                timeout=30,
            ).strip()
            if existing:
                self.execute(["docker", "stop", "--time", "10", container], timeout=25)
                self.execute(["docker", "rm", container], timeout=30)
        remaining = {}
        for kind, command in {
            "containers": ["docker", "ps", "-aq"],
            "networks": ["docker", "network", "ls", "-q"],
            "volumes": ["docker", "volume", "ls", "-q"],
        }.items():
            remaining[kind] = self.execute(
                [
                    *command,
                    "--filter",
                    f"label=com.docker.compose.project={self.project}",
                ],
                timeout=30,
            ).strip()
        result = {
            "remaining": remaining,
            "composeRemoved": not any(remaining.values()),
            "childrenReaped": all(
                not e.get("groupRemaining", False) for e in self.ownership["commands"]
            ),
        }
        self.ownership["cleanup"] = result
        self.persist()
        if not result["composeRemoved"] or not result["childrenReaped"]:
            raise RuntimeError("Owned resources remain; inspect ownership.json")
        for tag in self.ownership["images"]:
            if self.execute(["docker", "image", "ls", "-q", tag], timeout=30).strip():
                self.execute(["docker", "image", "rm", tag], timeout=60)
        for name in self.ownership["temporaryPaths"]:
            path = Path(name)
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
        if "port" in self.ownership:
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(("127.0.0.1", self.ownership["port"]))
        result.update(
            listenerRemoved=True, temporaryPathsRemoved=True, imagesRemoved=True
        )
        self.persist()
        return result
