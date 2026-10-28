"""Stop/start only the owned disposable backend for recovery acceptance."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

root = Path(os.environ["OPERATOR_ACCEPTANCE_EVIDENCE"])
ownership = json.loads((root / "ownership.json").read_text())
project = os.environ["OPERATOR_ACCEPTANCE_PROJECT"]
action = sys.argv[1]
if (
    ownership["project"] != project
    or not project.startswith("starlink-operator-")
    or action not in ("stop", "start")
):
    raise ValueError("Only the owned acceptance backend may be controlled")
command = [
    "docker",
    "compose",
    "-p",
    project,
    "-f",
    ownership["composeFile"],
    action,
    "starlink-location",
]
record = root / f"sync-backend-control-{time.time_ns()}.json"
state = {
    "command": command,
    "owner_pid": os.getpid(),
    "owner_pgid": os.getpgrp(),
    "pid": None,
    "state": "starting",
}
record.write_text(json.dumps(state, indent=2))
child = subprocess.Popen(
    command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
)
state.update(pid=child.pid)
record.write_text(json.dumps(state, indent=2))
try:
    output, _ = child.communicate(timeout=60)
except BaseException:
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait()
    raise
finally:
    state.update(state="complete", returncode=child.returncode)
    record.write_text(json.dumps(state, indent=2))
if child.returncode:
    raise RuntimeError(output)
print(output)
