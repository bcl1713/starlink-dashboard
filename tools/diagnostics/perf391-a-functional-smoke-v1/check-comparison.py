"""Offline two-role regeneration and Compose validation; never starts resources."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import signal


def interrupted(signum, frame):
    raise SystemExit(128 + signum)


for sig in (signal.SIGINT, signal.SIGTERM):
    signal.signal(sig, interrupted)

from comparison import HERE, PREP, regenerate, prepare, validate_compose

E = HERE / "evidence/comparison"
E.mkdir(exist_ok=True)
task = Path(tempfile.mkdtemp(prefix="perf391-preflight-contract-"))
ownership = {
    "pid": os.getpid(),
    "pgid": os.getpgrp(),
    "paths": [str(task)],
    "compose_project": "perf391-preflight-contract",
    "resources_started": [],
    "runtime_attempts": 0,
}
prepare.write(E / "ownership.json", ownership)
try:
    generated, comparison = regenerate(task)
    prepare.write(E / "comparison.json", comparison)
    shutil.copyfile(
        task / "context/runtime-build-plan.json", E / "regenerated-build-plan.json"
    )
    for role in ("A", "C"):
        launch, rendered = validate_compose(role, task / "context", comparison)
        prepare.write(E / f"launch-{role}.json", launch)
        prepare.write(E / f"{role}.compose.json", rendered)
        print(
            role
            + ": all original fields identical except approved override; full effective Compose configuration matches approved checkpoint"
        )
    for name in ("test_preparation.py", "test_node_identity.py", "test_logging.py"):
        run = subprocess.run(
            [os.sys.executable, "-B", str(PREP / name)],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, "PERF391_OFFLINE_ROOT": str(task / "context")},
        )
        (E / name.replace(".py", ".log")).write_text(run.stdout + run.stderr)
        run.check_returncode()
    run = subprocess.run(
        [os.sys.executable, "-B", str(HERE / "test_comparison.py")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    (E / "test_comparison.log").write_text(run.stdout + run.stderr)
    run.check_returncode()
    print(
        "PASS: both roles offline; existing identity/logging tests pass; runtime attempts 0"
    )
finally:
    shutil.rmtree(task)
    prepare.write(
        E / "cleanup.json",
        {
            "temporary_path": str(task),
            "temporary_path_absent": not task.exists(),
            "runtime_resources_created": [],
            "runtime_attempts": 0,
        },
    )
