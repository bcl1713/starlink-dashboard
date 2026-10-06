"""Bounded child groups, signal cleanup and retained ownership evidence."""

import argparse
import ctypes
import json
import os
import signal
import subprocess
import time
from pathlib import Path


def terminate_group(child):
    def alive():
        child.poll()
        # Reap adopted descendants from this exact owned group only.
        while True:
            try:
                pid, _ = os.waitpid(-child.pid, os.WNOHANG)
                if not pid:
                    break
            except ChildProcessError:
                break
        try:
            os.killpg(child.pid, 0)
            return True
        except ProcessLookupError:
            return False

    for sig, grace in ((signal.SIGTERM, 2), (signal.SIGKILL, 2)):
        if not alive():
            return True
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            return True
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline:
            if not alive():
                return True
            time.sleep(0.05)
    return not alive()


def run_owned(command: list[str], timeout_seconds: float, evidence: Path) -> int:
    evidence.mkdir(parents=True, exist_ok=True)
    owner = {
        "owner_pid": os.getpid(),
        "owner_process_group": os.getpgrp(),
        "command": command,
        "timeout_seconds": timeout_seconds,
    }
    path = evidence / "process-owner.json"
    path.write_text(json.dumps(owner, indent=2))
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(previous), 0, 0, 0) or libc.prctl(36, 1, 0, 0, 0):
        raise RuntimeError("Linux child-subreaper setup failed")
    handlers = {}

    def interrupted(number, frame):
        raise InterruptedError(number)

    for sig in (signal.SIGTERM, signal.SIGINT):
        handlers[sig] = signal.signal(sig, interrupted)
    child = None
    result = 1
    cleaned = True
    try:
        child = subprocess.Popen(command, start_new_session=True)
        owner.update(child_pid=child.pid, child_process_group=child.pid)
        path.write_text(json.dumps(owner, indent=2))
        try:
            result = child.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            result = 124
        except InterruptedError as error:
            result = 128 + error.args[0]
    finally:
        for sig in handlers:
            signal.signal(sig, signal.SIG_IGN)
        if child is not None:
            cleaned = terminate_group(child)
        (evidence / "process-cleanup.json").write_text(
            json.dumps(
                {
                    "status": "passed" if cleaned else "failed",
                    "child_pid": child.pid if child else None,
                    "result": result,
                },
                indent=2,
            )
        )
        libc.prctl(36, previous.value, 0, 0, 0)
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    return result if cleaned else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("child command required")
    raise SystemExit(run_owned(command, args.timeout, args.evidence))
