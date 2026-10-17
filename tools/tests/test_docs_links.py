"""Execute the link gate against deterministic failures and real local anchors."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "tools/check_docs_links.py"


def invoke(root, env=None):
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root-dir", str(root), "docs/"],
        cwd=root,
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.fixture
def fake_lychee(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    executable = binary / "lychee"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json,os,sys\n"
        "with open(os.environ['DOC_LINK_CALLS'], 'a') as log: log.write(json.dumps(sys.argv[1:])+'\\n')\n"
        "internal = '--offline' in sys.argv\n"
        "sys.exit(int(os.environ['DOC_INTERNAL_STATUS' if internal else 'DOC_EXTERNAL_STATUS']))\n"
    )
    executable.chmod(0o755)
    calls = tmp_path / "calls.jsonl"
    env = dict(
        os.environ,
        PATH=f"{binary}{os.pathsep}{os.environ['PATH']}",
        DOC_LINK_CALLS=str(calls),
        DOC_INTERNAL_STATUS="0",
        DOC_EXTERNAL_STATUS="0",
    )
    return env, calls


def test_external_failure_warns_without_failing_gate(tmp_path, fake_lychee):
    env, calls = fake_lychee
    env["DOC_EXTERNAL_STATUS"] = "2"
    result = invoke(tmp_path, env)
    assert result.returncode == 0, result.stderr
    assert "warning" in result.stderr.lower()
    assert "external" in result.stderr.lower()
    assert len(calls.read_text().splitlines()) == 2


def test_internal_failure_is_blocking_and_prevents_network_pass(tmp_path, fake_lychee):
    env, calls = fake_lychee
    env["DOC_INTERNAL_STATUS"] = "3"
    result = invoke(tmp_path, env)
    assert result.returncode == 3
    commands = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len(commands) == 1
    assert "--offline" in commands[0]


@pytest.mark.parametrize("target", ["missing.md", "target.md#missing-anchor"])
def test_real_lychee_rejects_missing_internal_files_and_fragments_despite_ignore(
    tmp_path, target
):
    assert shutil.which(
        "lychee"
    ), "Pinned Lychee is required for strict-link integration tests"
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / ".lycheeignore").write_text("file://*\n")
    (docs / "target.md").write_text("# Known heading\n")
    (docs / "index.md").write_text(f"[Broken]({target})\n")
    result = invoke(tmp_path)
    assert result.returncode != 0
    assert "missing" in result.stdout + result.stderr


def test_real_lychee_accepts_internal_anchors_and_reports_unreachable_external_as_advisory(
    tmp_path,
):
    assert shutil.which(
        "lychee"
    ), "Pinned Lychee is required for strict-link integration tests"
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / ".lycheeignore").write_text("file://*\n")
    (docs / "target.md").write_text("# Known heading\n")
    (docs / "index.md").write_text(
        "[Valid](target.md#known-heading)\n[Unreachable](http://127.0.0.1:1)\n"
    )
    result = invoke(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "warning" in result.stderr.lower()


@pytest.mark.parametrize("phase,expected", [("internal", 2), ("external", 0)])
@pytest.mark.parametrize("failure", ["missing executable", "timeout"])
def test_checker_errors_preserve_required_vs_advisory_policy(
    tmp_path, monkeypatch, capsys, phase, expected, failure
):
    spec = importlib.util.spec_from_file_location("docs_links", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def fail_pass(command, **kwargs):
        if phase == "internal" or "--offline" not in command:
            if failure == "timeout":
                raise subprocess.TimeoutExpired(command, 120)
            raise FileNotFoundError("synthetic missing checker")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(module.subprocess, "run", fail_pass)
    assert module.check_links(tmp_path, ["docs/"]) == expected
    stderr = capsys.readouterr().err
    if phase == "external":
        assert "::warning" in stderr
    else:
        assert "Internal documentation link check failed" in stderr
