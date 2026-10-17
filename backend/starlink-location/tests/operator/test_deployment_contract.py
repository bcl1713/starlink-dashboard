"""Compose opt-in/persistence contract and executable private-directory setup."""

import json
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[4]


def test_compose_opt_in_and_independent_durable_mount():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    service = compose["services"]["starlink-location"]
    # Compose's default expansion must keep the feature off in ordinary deploys.
    assert service["environment"]["OPERATOR_ENABLED"] == "${OPERATOR_ENABLED:-false}"
    mounts = [entry.split(":") for entry in service["volumes"]]
    operator = [entry for entry in mounts if entry[1] == "/app/data/operator"]
    assert len(operator) == 1
    volume, target = operator[0]
    assert volume in compose["volumes"]
    assert target not in {"/app/data/missions", "/app/data/flight-events"}
    assert all(
        volume not in str(other.get("volumes", []))
        for name, other in compose["services"].items()
        if name != "starlink-location"
    )


def test_entrypoint_private_top_level_preserves_history(tmp_path):
    root = tmp_path / "operator"
    root.mkdir(mode=0o775)
    history = root / "operations.sqlite3"
    history.write_bytes(b"durable sentinel")
    history.chmod(0o600)
    tools = tmp_path / "tools"
    tools.mkdir()
    log = tmp_path / "commands.jsonl"
    command = tools / "command"
    command.write_text("""#!/usr/bin/python3
import json, os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
args = sys.argv[1:]
with open(os.environ['COMMAND_LOG'], 'a') as output:
    output.write(json.dumps([name, *args]) + '\\n')
root = os.environ['OPERATOR_ROOT']
if name == 'mkdir' and args[-1] == root:
    pathlib.Path(root).mkdir(parents=True, exist_ok=True)
if name == 'chmod' and args[-1] == root:
    os.chmod(root, int(args[0], 8))
if name == 'runuser':
    os.execvp(args[3], args[3:])
""")
    command.chmod(0o755)
    for name in ("mkdir", "chown", "chmod", "runuser"):
        (tools / name).symlink_to(command)
    env = dict(
        os.environ,
        PATH=str(tools) + ":" + os.defpath,
        OPERATOR_ROOT=str(root),
        COMMAND_LOG=str(log),
    )
    result = subprocess.run(
        ["sh", str(ROOT / "backend/starlink-location/entrypoint.sh"), "/usr/bin/true"],
        env=env,
        timeout=10,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert root.stat().st_mode & 0o777 == 0o700
    assert history.read_bytes() == b"durable sentinel"
    assert history.stat().st_mode & 0o777 == 0o600
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    private = [args for args in commands if str(root) in args]
    assert ["chown", "appuser:appuser", str(root)] in private
    assert all("-R" not in args and "-r" not in args for args in private)
