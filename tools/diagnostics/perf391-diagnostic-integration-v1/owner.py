"""Explicit process/lifecycle registry. No Docker, service or browser startup CLI.

Only children created by this instance can enter the teardown registry. Group
membership and /proc start identity are verified immediately before each signal.
"""

import asyncio
import inspect
import json
import os
import signal
import subprocess
import time
from pathlib import Path


def start_id(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def members(group):
    result = []
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            pid = int(path.name)
            if os.getpgid(pid) == group:
                result.append({"pid": pid, "start_id": start_id(pid)})
        except (OSError, IndexError):
            pass
    return result


class Owner:
    def __init__(self, root, *, run, sources):
        if not run.startswith("synthetic-") or len(run) > 96:
            raise ValueError("synthetic owner required")
        self.root = Path(root).absolute()
        self.root.mkdir(parents=True, exist_ok=False)
        self.children = []
        self.callbacks = []
        self.closing = None
        self.manifest = {
            "schema": "perf391-collection-owner-v1",
            "version": 1,
            "run_id": run,
            "owner": {
                "pid": os.getpid(),
                "pgid": os.getpgrp(),
                "start_id": start_id(os.getpid()),
                "pid_namespace": os.readlink("/proc/self/ns/pid"),
            },
            "sources": sources,
            "processes": [],
            "streams": [],
            "output_directories": [str(self.root)],
            "budgets": {
                "processes": 16,
                "callbacks": 16,
                "streams": 4096,
                "queue_events": 4096,
                "queue_bytes": 8388608,
                "body_bytes": 2097152,
                "disk_bytes": 268435456,
                "shutdown_seconds": 5,
            },
            "compose_project": None,
            "containers": [],
            "networks": [],
            "volumes": [],
            "listeners": [],
            "cleanup_commands": [],
            "status": "registered",
            "errors": [],
        }
        self.persist()

    def persist(self):
        raw = (json.dumps(self.manifest, sort_keys=True, indent=2) + "\n").encode()
        if len(raw) > 1024 * 1024:
            raise ValueError("manifest budget")
        with (self.root / "manifest.tmp").open("wb") as f:
            f.write(raw)
            f.flush()
        (self.root / "manifest.tmp").replace(self.root / "manifest.json")

    def spawn(self, command, *, stdout=subprocess.DEVNULL, env=None):
        if self.closing is not None or len(self.children) >= 16:
            raise ValueError("owner closed or process budget")
        if (
            not command
            or len(command) > 64
            or any(not isinstance(v, str) or len(v) > 4096 for v in command)
        ):
            raise ValueError("command budget")
        row = {
            "command": command,
            "pid": None,
            "pgid": None,
            "start_id": None,
            "status": "intent",
            "reaped": False,
        }
        self.manifest["processes"].append(row)
        self.persist()
        child = subprocess.Popen(
            command,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        # Register immediately after successful fork; failure to persist still leaves owned handle.
        self.children.append((child, row))
        row.update(
            pid=child.pid,
            pgid=child.pid,
            start_id=start_id(child.pid),
            status="running",
        )
        self.manifest["cleanup_commands"].append(
            {
                "pid": child.pid,
                "start_id": row["start_id"],
                "command": ["kill", "-TERM", "--", str(child.pid)],
                "guard": "verify PID namespace, PGID and start_id before signal; reap via owner",
            }
        )
        try:
            self.persist()
        except BaseException:
            child.terminate()
            child.wait(timeout=5)
            raise
        return child

    def register_close(self, name, callback):
        if self.closing is not None or len(self.callbacks) >= 16:
            raise ValueError("close registry budget")
        self.callbacks.append((name, callback))

    async def _shutdown(self):
        self.manifest["status"] = "closing"
        for name, callback in self.callbacks:
            try:
                value = callback()
                if inspect.isawaitable(value):
                    await asyncio.wait_for(value, timeout=5)
            except (
                Exception,  # noqa: BLE001 - cleanup must continue after callback failure
                asyncio.CancelledError,
            ) as error:
                self.manifest["errors"].append(name + ":" + type(error).__name__)
        for child, row in self.children:
            # A unique session's group remains reserved while any descendants survive.
            actions = []
            for sig in (signal.SIGTERM, signal.SIGKILL):
                try:
                    if start_id(child.pid) != row["start_id"]:
                        self.manifest["errors"].append("process_identity_changed")
                        break
                except FileNotFoundError:
                    pass
                for member in members(child.pid):
                    try:
                        if (
                            os.getpgid(member["pid"]) == child.pid
                            and start_id(member["pid"]) == member["start_id"]
                        ):
                            os.kill(member["pid"], sig)
                            actions.append({**member, "signal": sig.name})
                    except ProcessLookupError:
                        pass
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(child.wait, timeout=1), timeout=2
                    )
                except (TimeoutError, subprocess.TimeoutExpired):
                    pass
                # Reap descendants adopted by the offline runner's subreaper, when present.
                until = time.monotonic() + 1
                while time.monotonic() < until:
                    try:
                        while True:
                            pid, _ = (
                                os.waitpid(  # noqa: ASYNC222 - WNOHANG never blocks
                                    -child.pid, os.WNOHANG
                                )
                            )
                            if not pid:
                                break
                    except ChildProcessError:
                        pass
                    if not members(child.pid):
                        break
                    await asyncio.sleep(0.01)
                if not members(child.pid):
                    break
            row.update(
                status="stopped",
                returncode=child.poll(),
                reaped=child.returncode is not None,
                actions=actions,
                survivors=members(child.pid),
            )
            if row["survivors"] or not row["reaped"]:
                self.manifest["errors"].append("process_cleanup_failed")
        self.manifest["status"] = (
            "cleanup_failed" if self.manifest["errors"] else "clean"
        )
        self.persist()
        return self.manifest

    async def close(self):
        if self.closing is None:
            self.closing = asyncio.create_task(self._shutdown())
        cancelled = False
        while not self.closing.done():
            try:
                await asyncio.shield(self.closing)
            except asyncio.CancelledError:
                cancelled = True
        result = self.closing.result()
        if cancelled:
            raise asyncio.CancelledError
        return result
