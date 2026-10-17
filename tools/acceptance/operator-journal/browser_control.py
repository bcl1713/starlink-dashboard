"""Browser-side host controls: only recorded project service and synthetic DB."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

DB = "/app/data/operator/simulation/synthetic-operator-demo-v1/operations.sqlite3"


def main():
    root = Path(os.environ["OPERATOR_ACCEPTANCE_EVIDENCE"])
    ownership = json.loads((root / "ownership.json").read_text())
    project = os.environ["OPERATOR_ACCEPTANCE_PROJECT"]
    assert ownership["project"] == project and project.startswith("starlink-operator-")
    action = sys.argv[1]
    command = ["docker", "compose", "-p", project, "-f", ownership["composeFile"]]
    if action in ("readonly", "writable"):
        mode = "0o400" if action == "readonly" else "0o600"
        directory_mode = "0o500" if action == "readonly" else "0o700"
        script = f"""from pathlib import Path
p=Path({DB!r})
p.parent.chmod({directory_mode})
for f in p.parent.glob('operations.sqlite3*'): f.chmod({mode})
print('synthetic Operator SQLite media {action}')
"""
        command += [
            "exec",
            "-T",
            "--user",
            "0",
            "starlink-location",
            "python",
            "-c",
            script,
        ]
    elif action == "restart":
        command += ["restart", "starlink-location"]
    elif action == "counts":
        key = sys.argv[2]
        script = f"""import json,sqlite3
with sqlite3.connect('file:{DB}?mode=ro',uri=True) as db:
 key={key!r}
 receipts=db.execute('SELECT command_id FROM commands WHERE idempotency_key=?',(key,)).fetchall()
 revisions=db.execute('SELECT count(*) FROM revisions WHERE command_id IN (SELECT command_id FROM commands WHERE idempotency_key=?)',(key,)).fetchone()[0]
 print(json.dumps({{'receipts':len(receipts),'revisions':revisions}}))
"""
        command += ["exec", "-T", "starlink-location", "python", "-c", script]
    else:
        raise ValueError("Unknown owned control")
    record = root / f"browser-control-{time.time_ns()}.json"
    state = {
        "action": action,
        "command": command,
        "pid": os.getpid(),
        "pgid": os.getpgrp(),
        "state": "starting",
    }
    record.write_text(json.dumps(state, indent=2))
    result = subprocess.run(
        command, check=False, text=True, capture_output=True, timeout=60
    )
    state.update(state="complete", returncode=result.returncode)
    record.write_text(json.dumps(state, indent=2))
    print(result.stdout)
    if result.returncode:
        raise RuntimeError(result.stderr)


if __name__ == "__main__":
    main()
