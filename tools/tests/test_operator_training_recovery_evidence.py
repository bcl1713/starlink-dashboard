"""Recovery evidence reads native backup/restore artifacts without changing them."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend/starlink-location"))


def load(name):
    spec = importlib.util.spec_from_file_location(
        "training_recovery_" + name,
        ROOT / "tools/training/operator-mission" / (name + ".py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reads_validated_native_backup_and_real_epoch_change(tmp_path, monkeypatch):
    import json

    from app.operator.backup import backup_store, checksum
    from app.operator.recovery import restore_store
    from app.operator.settings import OperatorSettings
    from app.operator.store import OperatorStore

    scenario = load("scenario")
    maintenance = load("maintenance")
    root = tmp_path / "private"
    scenario.mark_root(root)
    seeded = scenario.seed_prerequisites(root)
    monkeypatch.setenv("OPERATOR_TRAINING_FIXTURE", "explicit-private-training-v1")
    settings = OperatorSettings(
        enabled=True,
        root=root / "operator",
        source_mode="simulation",
        simulation_run_id=seeded["namespace"],
    )
    clock = scenario.training_clock(root)
    store = OperatorStore.open(settings, initialize=False, clock=clock)
    manifest = backup_store(store, directory=settings.database_path.parent / "backups")
    original = json.loads(manifest.read_text())
    database = manifest.parent / original["database"]
    before = maintenance.inspect_backup(root, manifest)
    assert before["manifest"] == original
    assert before["databaseSha256"] == original["checksum"]
    assert before["identity"]["api_epoch"] == seeded["api_epoch"]
    assert len(before["records"]) == len(before["history"]) == 8
    assert before["restoreReport"] is None
    assert checksum(database) == original["checksum"]

    restored = restore_store(settings, manifest=manifest, clock=clock)
    after = maintenance.inspect_backup(root, manifest)
    assert after["identity"]["api_epoch"] == str(restored.api_epoch)
    assert after["identity"]["api_epoch"] != before["identity"]["api_epoch"]
    assert after["preservedIdentity"] == before["identity"]
    assert after["restoreReport"]["restored_H"] == 8
    assert after["records"] == before["records"]
    assert after["history"] == before["history"]
    assert checksum(database) == original["checksum"]
    database.write_bytes(b"corrupt backup")
    with pytest.raises(Exception, match="backup_checksum_mismatch"):
        maintenance.inspect_backup(root, manifest)


def test_inspection_requires_private_fixture_and_owned_manifest(tmp_path, monkeypatch):
    maintenance = load("maintenance")
    root = tmp_path / "private"
    with pytest.raises(ValueError, match="Explicit private"):
        maintenance.inspect_backup(root, tmp_path / "elsewhere.json")
    monkeypatch.setenv("OPERATOR_TRAINING_FIXTURE", "explicit-private-training-v1")
    load("scenario").mark_root(root)
    with pytest.raises(ValueError, match="private Operator root"):
        maintenance.inspect_backup(root, tmp_path / "elsewhere.json")


@pytest.mark.parametrize("owned", [True, False])
def test_offline_command_failure_reaps_only_verified_owned_survivor(owned):
    import json

    class Owner:
        project = "starlink-operator-training-test"

        def __init__(self):
            self.ownership = {"trainingRootId": "private-root"}
            self.calls = []
            self.present = True

        def persist(self):
            self.calls.append("recorded")

        def compose(self, *args):
            assert self.calls == ["recorded"]
            self.name = args[args.index("--name") + 1]
            raise TimeoutError("native command timed out")

        def execute(self, args, **kwargs):
            self.calls.append(args)
            if args[1:3] == ["container", "ls"]:
                return "exact-container" if self.present else ""
            if args[1] == "inspect":
                return json.dumps(
                    [
                        {
                            "Name": "/" + self.name,
                            "Config": {
                                "Labels": {
                                    "com.docker.compose.project": self.project,
                                    "operator.training.root": (
                                        "private-root" if owned else "foreign"
                                    ),
                                }
                            },
                            "State": {"Running": True},
                        }
                    ]
                )
            if args[1] == "rm":
                self.present = False
            return ""

    owner = Owner()
    control = load("recovery_control")
    with pytest.raises(TimeoutError if owned else ValueError):
        control.native(owner, "restore", "/app/data/operator/backup.json", offline=True)
    mutations = [
        call[1]
        for call in owner.calls
        if isinstance(call, list) and call[1] in {"stop", "rm"}
    ]
    assert mutations == (["stop", "rm"] if owned else [])
    assert owner.present is not owned
