"""Disposable production proof of private backup, restore, reset and child cleanup."""

import importlib.util
import json
import re
import signal
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

spec = importlib.util.spec_from_file_location(
    "operator_training_lifecycle_launcher", Path(__file__).with_name("launcher.py")
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def validate_root(root):
    root = root.absolute()
    if (
        root.parent != Path("/tmp")
        or not root.name.startswith("issue-376-training-lifecycle-")
        or root.is_symlink()
    ):
        raise ValueError("Explicit fresh task-owned disposable lifecycle root required")
    if root.exists() and any(root.iterdir()):
        raise ValueError("Lifecycle proof refuses existing data or ownership")
    return root


def request(origin, path, *, data=None, headers=None):
    body = None if data is None else json.dumps(data).encode()
    req = Request(
        origin.split("/operator")[0] + path,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urlopen(req, timeout=10) as response:
        return json.load(response)


def ready(origin):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            health = request(origin, "/api/v2/operator/health")
            if health.get("ready"):
                return health
        except (HTTPError, URLError, TimeoutError):
            pass
        time.sleep(0.5)
    raise RuntimeError("Private lifecycle proof backend did not become ready")


def note(origin, health, mission_id, title):
    command = {
        "schema_version": 1,
        "record_type": "journal_entry",
        "mission_id": mission_id,
        "leg_id": None,
        "scope": "mission",
        "time": {
            "occurred_at": None,
            "ended_at": None,
            "precision": "unknown",
            "end_state": "unknown",
            "planned_start_at": None,
            "planned_end_at": None,
        },
        "payload": {
            "schema_version": 1,
            "entry_type": "note",
            "title": title,
            "note": "Fictional disposable lifecycle evidence",
            "previous_leg_id": None,
            "next_leg_id": None,
        },
    }
    return request(
        origin,
        "/api/v2/operator/records",
        data=command,
        headers={
            "Idempotency-Key": str(uuid4()),
            "X-Operator-Store-Epoch": health["api_epoch"],
        },
    )


def record_ids(origin, mission):
    page = request(origin, f"/api/v2/operator/records?mission_id={mission}")
    if page["cursor"]:
        raise AssertionError("Unexpected partial proof record list")
    return sorted(item["record"]["record_id"] for item in page["items"])


def maintenance(owner, command, *, manifest=None, offline=False):
    program = [
        "/source/tools/training/operator-mission/maintenance.py",
        "/app/data",
        command,
    ]
    if manifest:
        program.extend(["--manifest", manifest])
    if offline:
        raw = owner.compose(
            "run",
            "--rm",
            "--no-deps",
            "--user",
            "appuser",
            "--entrypoint",
            "python",
            "starlink-location",
            *program,
            timeout=120,
        )
    else:
        raw = owner.compose(
            "exec",
            "-T",
            "--user",
            "appuser",
            "starlink-location",
            "python",
            *program,
            timeout=120,
        )
    return json.loads(raw)


def main():
    root = validate_root(Path(sys.argv[1]))
    initial = launcher.open_owner(root, create=True, disposable=True)
    runner = launcher.Owner(initial.project, root / "lifecycle-runner")
    runner.ownership.update(
        candidateSha=initial.ownership["candidateSha"],
        purpose="disposable lifecycle proof",
        ownedRoots=[str(root)],
    )
    runner.persist()
    handlers = {
        number: signal.signal(number, runner.signal)
        for number in (signal.SIGINT, signal.SIGTERM)
    }
    report = {
        "candidateSha": initial.ownership["candidateSha"],
        "checksPassed": False,
        "cleanup": {},
    }
    roots = [root]
    try:
        if runner.execute(
            ["git", "status", "--porcelain"], cwd=launcher.SOURCE
        ).strip():
            raise ValueError("Lifecycle proof requires a clean committed worktree")
        origin = launcher.start(initial, relay=True)
        first = ready(origin)
        missions = request(origin, "/api/v2/missions")
        mission = missions[0]["id"]
        retained = note(origin, first, mission, "Synthetic retained backup sentinel")
        saved_id = retained["saved_records"][0]["record_id"]
        backup = maintenance(initial, "backup")
        discarded = note(origin, first, mission, "Synthetic write after backup")
        discarded_id = discarded["saved_records"][0]["record_id"]
        assert discarded_id in record_ids(origin, mission)
        initial.compose("stop", "starlink-location", timeout=120)
        restored_cli = maintenance(
            initial, "restore", manifest=backup["manifest"], offline=True
        )
        assert restored_cli["ready"]
        initial.compose("start", "starlink-location", timeout=120)
        restored = ready(origin)
        assert restored["store_id"] == first["store_id"]
        assert restored["api_epoch"] != first["api_epoch"]
        before_reset = record_ids(origin, mission)
        assert saved_id in before_reset and discarded_id not in before_reset
        assert len(before_reset) == 9
        checked = maintenance(initial, "check")
        assert checked["ready"]
        child_root = root / "import-destination"
        child = launcher.open_owner(
            child_root, create=True, disposable=True, destination=True
        )
        destination_origin = launcher.start(child, relay=True)
        destination_health = ready(destination_origin)
        destination_mission = "synthetic-import-sentinel"
        request(
            destination_origin,
            "/api/v2/missions",
            data={"id": destination_mission, "name": "Fictional import sentinel"},
        )
        destination_receipt = note(
            destination_origin,
            destination_health,
            destination_mission,
            "Synthetic destination Operator sentinel",
        )
        destination_id = destination_receipt["saved_records"][0]["record_id"]
        assert record_ids(destination_origin, destination_mission) == [destination_id]
        # Exercise the real reset command, which records the successor before starting it.
        result = json.loads(
            runner.execute(
                [
                    "python3",
                    str(
                        launcher.SOURCE / "tools/training/operator-mission/launcher.py"
                    ),
                    "reset",
                    "--root",
                    str(root),
                    "--disposable",
                    "--relay",
                ],
                cwd=launcher.SOURCE,
                timeout=1800,
            )
        )
        new_root = Path(result["newRoot"])
        roots.append(new_root)
        runner.ownership["ownedRoots"] = [str(path) for path in roots]
        runner.persist()
        fresh = ready(result["origin"])
        assert fresh["store_id"] != restored["store_id"]
        assert fresh["simulation_run_id"] != restored["simulation_run_id"]
        assert len(record_ids(result["origin"], mission)) == 8
        child_after = launcher.open_owner(child_root, destination=True)
        assert launcher.check_resources(child_after) == {
            "container": [],
            "network": [],
            "volume": [],
        }
        old = launcher.open_owner(root)
        remaining_old = launcher.check_resources(old)
        assert (
            not remaining_old["container"]
            and not remaining_old["network"]
            and remaining_old["volume"]
        )
        old_origin = launcher.start(old, relay=True)
        reopened = ready(old_origin)
        assert (
            reopened["store_id"] == restored["store_id"]
            and reopened["api_epoch"] == restored["api_epoch"]
        )
        assert record_ids(old_origin, mission) == before_reset
        report.update(
            checksPassed=True,
            firstHealth=first,
            restoredHealth=restored,
            freshHealth=fresh,
            retainedRoot=str(root),
            newRoot=str(new_root),
            retainedRecordIds=before_reset,
            retainedReceipt=retained,
            discardedReceipt=discarded,
            destinationReceipt=destination_receipt,
            backupManifest=backup["manifest"],
            oldDataRetained=True,
            parentResetRemovedImportDestination=True,
        )
    finally:
        runner.stop_child()
        # A signal may arrive after successor creation but before reset returns JSON.
        errors = []
        try:
            state = json.loads((root / "ownership.json").read_text())
            successor = state.get("resetSuccessor")
            if successor:
                path = Path(successor)
                if path.parent != root.parent or not re.fullmatch(
                    re.escape(root.name) + r"-reset-[0-9a-f]{8}", path.name
                ):
                    raise ValueError(
                        "Invalid recorded reset successor; preserve it for recovery"
                    )
                if path not in roots and (path / "ownership.json").exists():
                    roots.append(path)
        except (OSError, ValueError, TypeError) as error:
            errors.append(f"Reset successor ownership: {error}")
        for path in reversed(roots):
            try:
                report["cleanup"][str(path)] = launcher.stop(launcher.open_owner(path))
            # Continue with other owned projects; report all cleanup errors below.
            except Exception as error:  # noqa: BLE001
                errors.append(f"{path}: {error}")
        if errors:
            report["cleanupErrors"] = errors
        (root / "lifecycle-proof.json").write_text(json.dumps(report, indent=2))
        for number, handler in handlers.items():
            signal.signal(number, handler)
        print(json.dumps(report, indent=2))
        if errors:
            raise RuntimeError(
                "Owned lifecycle cleanup incomplete: " + "; ".join(errors)
            )


if __name__ == "__main__":
    main()
