"""Thin private exercise wrapper around existing native maintenance commands."""

import importlib.util
import json
import time
from pathlib import Path
from uuid import uuid4


def load(name):
    spec = importlib.util.spec_from_file_location(
        "training_recovery_control_" + name, Path(__file__).with_name(name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def native(owner, command, manifest=None, *, offline=False):
    program = [
        "/source/tools/training/operator-mission/maintenance.py",
        "/app/data",
        command,
    ]
    if manifest is not None:
        program.extend(["--manifest", str(manifest)])
    if not offline:
        raw = owner.compose(
            "exec", "-T", "--user", "appuser", "starlink-location", "python", *program
        )
        return json.loads(raw.strip().splitlines()[-1])
    name = owner.project + "-maintenance-" + uuid4().hex[:8]
    owner.ownership.setdefault("maintenanceContainers", []).append(name)
    owner.persist()
    try:
        raw = owner.compose(
            "run",
            "--rm",
            "--no-deps",
            "--name",
            name,
            "--user",
            "appuser",
            "--entrypoint",
            "python",
            "starlink-location",
            *program
        )
        return json.loads(raw.strip().splitlines()[-1])
    finally:
        # A timed-out Compose client can leave its one-off container running.
        # Verify both recorded name and private root label before removing it.
        ids = owner.execute(
            ["docker", "container", "ls", "-aq", "--filter", "name=^/" + name + "$"]
        ).split()
        for identifier in ids:
            item = json.loads(owner.execute(["docker", "inspect", identifier]))[0]
            labels = item["Config"]["Labels"]
            if (
                item["Name"] != "/" + name
                or labels.get("com.docker.compose.project") != owner.project
                or labels.get("operator.training.root")
                != owner.ownership["trainingRootId"]
            ):
                raise ValueError("Maintenance survivor ownership mismatch; preserve it")
            if item["State"]["Running"]:
                owner.execute(
                    ["docker", "stop", "--time", "10", identifier], timeout=20
                )
            owner.execute(["docker", "rm", identifier])
        if owner.execute(
            ["docker", "container", "ls", "-aq", "--filter", "name=^/" + name + "$"]
        ).strip():
            raise RuntimeError("Owned maintenance container remains")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(".pending")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def run(owner, command, *, manifest=None, origin=None):
    launcher = load("launcher")
    evidence = load("archive_evidence")
    launcher.validate(owner)
    get = evidence.loopback_reader(owner.ownership["port"])
    if command == "check":
        return native(owner, "check")
    if origin is None:
        raise ValueError("--browser-origin is required for private recovery evidence")
    origin = evidence.browser_origin(origin)
    if command == "backup":
        before = evidence.read_snapshot(get)
        result = native(owner, "backup")
        manifest = result["manifest"]
        inspection = native(owner, "inspect-backup", manifest)
        if (
            inspection["manifest"]["H"] != before["H"]
            or inspection["identity"]["api_epoch"] != before["health"]["api_epoch"]
            or evidence._ordered(inspection["records"]) != before["records"]
            or evidence._ordered(inspection["history"]) != before["history"]
        ):
            raise ValueError(
                "Journal changed during backup; make another native backup"
            )
        path = owner.root / "recovery" / (Path(manifest).stem + ".baseline.json")
        write(
            path,
            {
                "browserOrigin": origin,
                "nativeManifest": manifest,
                "beforeBackup": before,
                "backup": inspection,
            },
        )
        return {"manifest": manifest, "baseline": str(path)}
    if command != "restore" or manifest is None:
        raise ValueError("Restore requires the original native --manifest")
    # Native maintenance independently confines the manifest to the marked root.
    path = owner.root / "recovery" / (Path(manifest).stem + ".baseline.json")
    baseline = json.loads(path.read_text())
    if baseline["nativeManifest"] != manifest:
        raise ValueError("Use the original native backup manifest path")
    if baseline["browserOrigin"] != origin:
        raise ValueError("Use the same private browser origin as the backup")
    selected = native(owner, "inspect-backup", manifest)
    if selected["manifest"] != baseline["backup"]["manifest"]:
        raise ValueError("Native backup changed since the baseline")
    before = evidence.read_snapshot(get)
    if before["health"] != baseline["beforeBackup"]["health"]:
        raise ValueError("Store identity changed since this backup; preserve evidence")
    owner.compose("stop", "starlink-location")
    try:
        restored = native(owner, "restore", manifest, offline=True)
    finally:
        owner.compose("start", "starlink-location")
    deadline = time.monotonic() + 90
    while True:
        try:
            after = evidence.read_snapshot(get)
            break
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise TimeoutError("Restored private backend did not become ready")
            time.sleep(0.5)
    inspection = native(owner, "inspect-backup", manifest)
    checked = native(owner, "check")
    if (
        after["health"]["store_id"] != before["health"]["store_id"]
        or after["health"]["api_epoch"] == before["health"]["api_epoch"]
        or after["health"]["api_epoch"] != restored["api_epoch"]
        or checked["api_epoch"] != restored["api_epoch"]
        or not checked["ready"]
        or after["H"] != inspection["manifest"]["H"]
        or after["records"] != evidence._ordered(inspection["records"])
        or after["history"] != evidence._ordered(inspection["history"])
        or inspection["databaseSha256"] != baseline["backup"]["databaseSha256"]
    ):
        raise ValueError("Native restore and ordinary API evidence disagree")
    report = {
        **baseline,
        "beforeRestore": before,
        "afterRestore": after,
        "restoredBackup": inspection,
        "restoreHealth": restored,
        "checkHealth": checked,
    }
    report_path = path.with_name(Path(manifest).stem + ".evidence.json")
    write(report_path, report)
    return {
        "manifest": manifest,
        "evidence": str(report_path),
        "health": after["health"],
    }
