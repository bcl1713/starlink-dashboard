"""Explicit CLI actions use the same durable maintenance interfaces."""

import json

import pytest


def test_explicit_cli_workflow(tmp_path, capsys):
    from app.operator.__main__ import main

    common = [
        "--root",
        str(tmp_path / "store"),
        "--mode",
        "simulation",
        "--run",
        "cli-run",
    ]
    assert main(["initialize", *common]) == 0
    initialized = json.loads(capsys.readouterr().out)
    assert initialized["ready"] and initialized["simulation_run_id"] == "cli-run"
    assert main(["check", *common]) == 0
    assert json.loads(capsys.readouterr().out)["ready"]
    assert main(["backup", *common, "--directory", str(tmp_path / "backups")]) == 0
    manifest = json.loads(capsys.readouterr().out)["manifest"]
    assert main(["restore", *common, "--manifest", manifest]) == 0
    restored = json.loads(capsys.readouterr().out)
    assert restored["api_epoch"] != initialized["api_epoch"]


def test_cli_missing_store_does_not_initialize(tmp_path, capsys):
    from app.operator.__main__ import main

    assert main(["check", "--root", str(tmp_path / "missing"), "--mode", "live"]) == 1
    assert json.loads(capsys.readouterr().out)["error_code"] == "store_unavailable"
    assert not (tmp_path / "missing").exists()
    with pytest.raises(SystemExit) as error:
        main(["initialize"])
    assert error.value.code == 2


def test_cli_initialize_refuses_prior_store_artifacts(tmp_path, capsys):
    from app.operator.__main__ import main

    root = tmp_path / "store"
    root.mkdir()
    (root / "operations.lock").write_bytes(b"preserved artifact")
    assert main(["initialize", "--root", str(root), "--mode", "live"]) == 1
    assert (
        json.loads(capsys.readouterr().out)["error_code"] == "store_recovery_required"
    )
    assert not (root / "operations.sqlite3").exists()
    assert (root / "operations.lock").read_bytes() == b"preserved artifact"


def test_export_existing_journal_without_overwriting_a_destination(
    service, record_data, tmp_path
):
    import json
    import zipfile

    from app.operator.__main__ import main
    from tests.operator.service_helpers import create

    create(service, record_data)
    output = tmp_path / "retained-journal.zip"
    args = [
        "export",
        "--root",
        str(service.store.settings.root),
        "--mode",
        "live",
        "--mission",
        "demo-mission",
        "--output",
        str(output),
    ]
    assert main(args) == 0
    with zipfile.ZipFile(output) as archive:
        assert (
            len(json.loads(archive.read("operations/journal.json"))["current_records"])
            == 1
        )
        assert "operations/audit.jsonl" in archive.namelist()
    before = output.read_bytes()
    assert main(args) == 1
    assert output.read_bytes() == before
