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
    elif action == "clock":
        from datetime import datetime

        value = datetime.fromisoformat(sys.argv[2])
        if value.utcoffset() is None:
            raise ValueError("Aware synthetic UTC required")
        script = (
            "from pathlib import Path; Path('/app/data/synthetic-issue-clock.txt').write_text("
            + repr(value.isoformat())
            + ")"
        )
        command += ["exec", "-T", "starlink-location", "python", "-c", script]
    elif action == "restore-epoch":
        script = """import json
from pathlib import Path
from datetime import datetime
from app.operator.backup import backup_store
from app.operator.recovery import restore_store
from app.operator.settings import OperatorSettings
from app.operator.store import OperatorStore
from scenario import ScenarioClock, RUN_ID
root=Path('/app/data')
clock=ScenarioClock(datetime.fromisoformat((root/'synthetic-issue-clock.txt').read_text().strip()))
settings=OperatorSettings(enabled=True,root=root/'operator',source_mode='simulation',simulation_run_id=RUN_ID)
store=OperatorStore.open(settings,initialize=False,clock=clock)
try:
 old=str(store.health().api_epoch)
 manifest=backup_store(store,directory=settings.database_path.parent/'synthetic-epoch-backups')
 restored=restore_store(settings,manifest=manifest,clock=clock)
 assert restored.ready and str(restored.api_epoch)!=old
 print(json.dumps({'previous':old,'restored':str(restored.api_epoch)}))
finally:
 store.close()
"""
        command += [
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            "-c",
            script,
        ]
    elif action == "restart":
        command += ["restart", "starlink-location"]
    elif action == "event-counts":
        import re

        occurrence = sys.argv[2]
        if not re.fullmatch(r"[0-9a-f]{64}", occurrence):
            raise ValueError("Synthetic occurrence ID required")
        script = f"""import json,sqlite3
with sqlite3.connect('file:{DB}?mode=ro',uri=True) as db:
 occurrence={occurrence!r}
 print(json.dumps(dict(acknowledgments=db.execute('SELECT count(*) FROM event_acknowledgments WHERE occurrence_id=?',(occurrence,)).fetchone()[0], receipts=db.execute("SELECT count(*) FROM commands WHERE json_extract(response_json,'$.occurrence_id')=?",(occurrence,)).fetchone()[0])))
"""
        command += ["exec", "-T", "starlink-location", "python", "-c", script]
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
