"""Exercise observation through real, isolated pytest subprocesses."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]


def run_suite(tmp_path, source, *args, conftest="", plugin=True):
    (tmp_path / "test_sample.py").write_text(source)
    (tmp_path / "conftest.py").write_text(conftest)
    report = tmp_path / "report.json"
    env = {
        **os.environ,
        "PYTHONPATH": str(TOOLS),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTEST_ADDOPTS": "",
        "BACKEND_CI_RUN_ID": "synthetic-17",
        "BACKEND_CI_RUN_ATTEMPT": "2",
    }
    command = [sys.executable, "-m", "pytest", "-q", *args]
    if plugin:
        command += ["-p", "backend_ci", f"--backend-ci-report={report}"]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if not plugin:
        return result, None
    assert report.exists(), result.stdout + result.stderr
    return result, json.loads(report.read_text())


def test_observes_order_imported_parameters_and_identity(tmp_path):
    (tmp_path / "cases.py").write_text(
        "import pytest\n@pytest.mark.parametrize('value', [1, 2])\n"
        "def test_imported(value): assert value > 0\n"
    )
    result, report = run_suite(
        tmp_path,
        "from cases import test_imported\nclass TestGroup:\n"
        "    def test_pass(self): pass\n",
    )
    assert result.returncode == 0
    expected = [
        "test_sample.py::test_imported[1]",
        "test_sample.py::test_imported[2]",
        "test_sample.py::TestGroup::test_pass",
    ]
    assert report["schema_version"] == 1
    assert report["collection"]["full_nodeids"] == expected
    assert report["collection"]["selected_nodeids"] == expected
    assert report["collection"]["deselected_nodeids"] == []
    assert report["session"]["exit_code"] == 0
    assert report["session"]["finished"] is True
    assert report["session"]["ended_at"] >= report["session"]["started_at"]
    assert report["session"]["duration_seconds"] > 0
    for nodeid in expected:
        phases = [event for event in report["phases"] if event["nodeid"] == nodeid]
        assert [event["when"] for event in phases] == ["setup", "call", "teardown"]
        assert all(event["outcome"] == "passed" for event in phases)
        assert all(event["duration"] >= 0 for event in phases)
    identity = report["identity"]
    assert identity["run_id"] == "synthetic-17"
    assert identity["run_attempt"] == "2"
    assert identity["python"]["version"] == sys.version
    assert len(identity["checkout_sha"]) == 40
    assert (
        identity["observer_sha256"]
        == hashlib.sha256((TOOLS / "backend_ci.py").read_bytes()).hexdigest()
    )
    distributions = identity["distributions"]
    assert distributions == sorted(distributions)
    assert any(value.startswith("pytest==") for value in distributions)
    assert (
        identity["distribution_sha256"]
        == hashlib.sha256("\n".join(distributions).encode()).hexdigest()
    )
    assert identity["input_sha256"]["backend/starlink-location/requirements-dev.txt"]
    assert identity["platform"]["system"]
    assert identity["command"]
    assert not list(tmp_path.glob(".report.json.*"))


@pytest.mark.parametrize(
    ("source", "conftest", "exit_code", "phase", "outcome", "xfail"),
    [
        ("def test_case(): pass", "", 0, "call", "passed", None),
        (
            "import pytest\n@pytest.mark.skip(reason='setup skip')\ndef test_case(): pass",
            "",
            0,
            "setup",
            "skipped",
            None,
        ),
        (
            (
                "import pytest\n@pytest.mark.xfail(reason='expected')\n"
                "def test_case(): assert False"
            ),
            "",
            0,
            "call",
            "skipped",
            "expected",
        ),
        (
            "import pytest\n@pytest.mark.xfail(reason='unexpected')\ndef test_case(): pass",
            "",
            0,
            "call",
            "passed",
            "unexpected",
        ),
        ("def test_case(): assert False, 'call failed'", "", 1, "call", "failed", None),
        (
            "def test_case(broken): pass",
            "import pytest\n@pytest.fixture\ndef broken(): raise RuntimeError('setup failed')",
            1,
            "setup",
            "failed",
            None,
        ),
        (
            "def test_case(broken): pass",
            (
                "import pytest\n@pytest.fixture\ndef broken():\n"
                "    yield\n    raise RuntimeError('teardown failed')"
            ),
            1,
            "teardown",
            "failed",
            None,
        ),
    ],
)
def test_outcomes_preserve_pytest_status(
    tmp_path, source, conftest, exit_code, phase, outcome, xfail
):
    plain, _ = run_suite(tmp_path, source, conftest=conftest, plugin=False)
    result, report = run_suite(tmp_path, source, conftest=conftest)
    assert result.returncode == plain.returncode == exit_code
    assert report["session"]["exit_code"] == exit_code
    event = next(event for event in report["phases"] if event["when"] == phase)
    assert event["outcome"] == outcome
    assert event["wasxfail"] == xfail
    if outcome == "failed":
        assert "failed" in event["longrepr"]
    if phase == "setup" and outcome != "passed":
        assert [event["when"] for event in report["phases"]] == ["setup", "teardown"]


def test_collection_only_has_manifest_without_synthetic_outcomes(tmp_path):
    result, report = run_suite(tmp_path, "def test_case(): pass", "--collect-only")
    assert result.returncode == 0
    assert report["session"]["collect_only"] is True
    assert report["collection"]["full_nodeids"] == ["test_sample.py::test_case"]
    assert report["collection"]["duration_seconds"] >= 0
    assert report["phases"] == []


def test_collection_error_is_reported_without_changing_status(tmp_path):
    source = "raise RuntimeError('collection failed')"
    plain, _ = run_suite(tmp_path, source, plugin=False)
    result, report = run_suite(tmp_path, source)
    assert result.returncode == plain.returncode == 2
    assert report["session"]["exit_code"] == 2
    assert report["collection"]["errors"][0]["nodeid"] == "test_sample.py"
    assert "collection failed" in report["collection"]["errors"][0]["longrepr"]
    assert report["phases"] == []


def test_keyboard_interrupt_is_incomplete_and_keeps_nonzero_status(tmp_path):
    source = "def test_case(): raise KeyboardInterrupt()"
    plain, _ = run_suite(tmp_path, source, plugin=False)
    result, report = run_suite(tmp_path, source)
    assert result.returncode == plain.returncode == 2
    assert report["session"]["exit_code"] == 2
    assert report["session"]["interrupted"]
    assert not any(event["when"] == "call" for event in report["phases"])


def test_report_path_must_be_absolute(tmp_path):
    result, _ = run_suite(tmp_path, "def test_case(): pass", plugin=False)
    assert result.returncode == 0
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "backend_ci",
        "--backend-ci-report=relative.json",
    ]
    result = subprocess.run(
        command,
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(TOOLS),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 4
    assert "absolute" in result.stderr
    assert not (tmp_path / "relative.json").exists()


@pytest.mark.parametrize(
    "changed",
    [
        "requirements-dev.txt",
        "requirements.txt",
        "requirements-gfs.txt",
        ".python-version",
    ],
)
def test_backend_lock_rejects_changed_source_inputs(tmp_path, changed):
    import backend_ci

    backend = tmp_path / "backend/starlink-location"
    backend.mkdir(parents=True)
    for name in (
        "requirements-dev.txt",
        "requirements.txt",
        "requirements-gfs.txt",
        ".python-version",
    ):
        (backend / name).write_text(
            "3.11\n" if name == ".python-version" else "example>=1\n"
        )
    digest = backend_ci.backend_lock_input_hashes(tmp_path)
    (backend / "requirements-ci.txt").write_text(
        "# backend-lock-input-sha256: " + json.dumps(digest) + "\nexample==1\n"
    )
    backend_ci.validate_backend_lock(tmp_path)
    (backend / changed).write_text((backend / changed).read_text() + "# change\n")
    with pytest.raises(ValueError, match="regenerate"):
        backend_ci.validate_backend_lock(tmp_path)


@pytest.mark.parametrize(
    "header",
    [
        "",
        "# backend-lock-input-sha256: not-json\n",
        "# backend-lock-input-sha256: {}\n",
    ],
)
def test_backend_lock_rejects_missing_or_incomplete_provenance(tmp_path, header):
    import backend_ci

    backend = tmp_path / "backend/starlink-location"
    backend.mkdir(parents=True)
    (backend / "requirements-ci.txt").write_text(header)
    with pytest.raises(ValueError, match="regenerate"):
        backend_ci.validate_backend_lock(tmp_path)
