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
