"""Verify the separately owned Chromium group after its Node owner exits."""

import json
import os
import shutil
import signal
import time
from pathlib import Path


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return {"pgid": int(fields[2]), "start_ticks": fields[19], "state": fields[0]}
    except FileNotFoundError:
        return None


def verify_browser(root):
    path = root / "browser-owner.json"
    if not path.exists():
        return {"started": False}
    record = json.loads(path.read_text())
    pid, pgid = record["pid"], record["pgid"]
    if pid != pgid:
        raise RuntimeError(f"Browser group is not independently owned: {record}")

    def members():
        result = []
        for entry in Path("/proc").iterdir():
            if entry.name.isdigit():
                state = identity(int(entry.name))
                if state and state["pgid"] == pgid and state["state"] != "Z":
                    result.append(int(entry.name))
        return result

    for sig in (None, signal.SIGTERM, signal.SIGKILL):
        remaining = members()
        if not remaining:
            break
        current = identity(pid)
        if sig is not None:
            if current is None or current["start_ticks"] != record["start_ticks"]:
                raise RuntimeError(
                    f"Browser group survivors need ownership review: {remaining}"
                )
            os.killpg(pgid, sig)
        deadline = time.monotonic() + 5
        while members() and time.monotonic() < deadline:
            time.sleep(0.05)
    remaining = members()
    result = {"started": True, "pid": pid, "pgid": pgid, "remaining": remaining}
    (root / "browser-host-cleanup.json").write_text(json.dumps(result, indent=2))
    if remaining:
        raise RuntimeError(f"Browser resources remain: {remaining}")
    for argument in record["command"]:
        if argument.startswith("--user-data-dir=/tmp/playwright_chromiumdev_profile-"):
            (
                shutil.rmtree(argument.split("=", 1)[1], ignore_errors=False)
                if Path(argument.split("=", 1)[1]).exists()
                else None
            )
    return result
