"""Own a sequential short matched matrix; each child owns its isolated Compose stack."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--duration", type=int, default=30)
    p.add_argument("--repetitions", type=int, choices=(2, 3), default=2)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    child = None
    ledger = {
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "commands": [],
        "compose_projects": [],
    }

    def save():
        (args.output / "matrix-owner.json").write_text(json.dumps(ledger, indent=2))

    def interrupted(signum, frame):
        raise InterruptedError(f"Matrix interrupted by {signum}")

    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, interrupted)
    try:
        for repetition in range(1, args.repetitions + 1):
            for loaded in (False, True):
                for mode in ("off", "trace"):
                    # Alternate order to reduce fixed first/second bias.
                    roles = [("original", "25e34168"), ("candidate", "e1f65798")]
                    if repetition % 2 == 0:
                        roles.reverse()
                    for role, sha in roles:
                        name = f'{mode}-r{repetition}-{"loaded" if loaded else "unloaded"}-{role}'
                        project = "starlink-operator-diag391-" + name
                        command = [
                            sys.executable,
                            str(Path(__file__).with_name("run.py")),
                            "--sha",
                            sha,
                            "--project",
                            project,
                            "--output",
                            str(args.output / name),
                            "--duration",
                            str(args.duration),
                            "--warmup",
                            "5",
                            "--total-timeout",
                            "800",
                            "--instrumentation",
                            mode,
                            "--viewers",
                            "2" if loaded else "0",
                        ]
                        if loaded:
                            command.append("--operator")
                        entry = {
                            "name": name,
                            "command": command,
                            "pid": None,
                            "pgid": None,
                            "started": time.time(),
                        }
                        ledger["commands"].append(entry)
                        ledger["compose_projects"].append(project)
                        save()
                        with (args.output / (name + ".log")).open("w") as log:
                            child = subprocess.Popen(
                                ["timeout", "--kill-after=10s", "14m", *command],
                                stdout=log,
                                stderr=subprocess.STDOUT,
                                start_new_session=True,
                            )
                            entry.update(pid=child.pid, pgid=child.pid)
                            save()
                            child.wait()
                        entry.update(
                            returncode=child.returncode,
                            reaped=True,
                            finished=time.time(),
                        )
                        save()
                        print(name, child.returncode, flush=True)
                        child = None
                        # Never continue past failed cleanup or a rejected attempt.
                        if entry["returncode"]:
                            raise RuntimeError(
                                "Diagnostic failed; inspect retained output before retry"
                            )
    finally:
        if child and child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=100)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait(timeout=10)
            ledger["commands"][-1].update(returncode=child.returncode, reaped=True)
        save()


if __name__ == "__main__":
    main()
