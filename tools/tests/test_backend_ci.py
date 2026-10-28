"""Exercise observation through real, isolated pytest subprocesses."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1]


def test_backend_inventory_does_not_inherit_host_distributions(tmp_path):
    import backend_ci

    host = tmp_path / "host-python"
    venv.EnvBuilder(with_pip=False).create(host)
    site = (
        host
        / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    )
    package = site / "ambient_ci_probe-99.0.dist-info"
    package.mkdir()
    (package / "METADATA").write_text("Name: ambient-ci-probe\nVersion: 99.0\n")
    command = backend_ci.backend_commands(TOOLS.parent, str(host / "bin/python"))[0][0]
    # Exercise the canonical interpreter/environment flags without downloading
    # application dependencies: a package installed only on the host must vanish.
    command = command[: command.index("--with-requirements")]
    result = subprocess.run(
        command
        + [
            "python",
            "-c",
            (
                "import importlib.metadata as m, json; "
                "print(json.dumps([d.metadata['Name'] for d in m.distributions()]))"
            ),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert "ambient-ci-probe" not in json.loads(result.stdout)


def run_suite(tmp_path, source, *args, conftest="", plugin=True):
    (tmp_path / "test_sample.py").write_text(source)
    (tmp_path / "conftest.py").write_text(conftest)
    report = tmp_path / "report.json"
    env = {
        **os.environ,
        "PYTHONPATH": str(TOOLS),
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


def test_whole_file_assignment_is_stable_and_validates_paths():
    import backend_ci

    path = "tests/unit/test_new+[odd].py"
    expected = int.from_bytes(hashlib.sha256(path.encode()).digest(), "big") % 4 + 1
    assert backend_ci.assign_file(path, 4, {}) == expected
    assert backend_ci.assign_file(path, 4, {path: 2}) == 2
    for invalid in ("../tests/x.py", "/tests/x.py", "tests/../x.py", "other.py"):
        with pytest.raises(ValueError):
            backend_ci.assign_file(invalid, 4, {})
    for count in (True, 0, 3):
        with pytest.raises(ValueError):
            backend_ci.assign_file(path, count, {})
    with pytest.raises(ValueError):
        backend_ci.assign_file(path, 4, {path: True})


def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(tmp_path):
    import backend_ci

    for content in (
        '{"x": 1, "x": 2}',
        '{"x": NaN}',
        '{"x": Infinity}',
        '{"x": 1e999}',
    ):
        path = tmp_path / "invalid.json"
        path.write_text(content)
        with pytest.raises(ValueError):
            backend_ci.read_json(path)


def test_real_shards_preserve_collected_owner_order_and_union(tmp_path):
    import backend_ci

    tests = tmp_path / "tests"
    tests.mkdir()
    (tmp_path / "cases.py").write_text(
        "import pytest\n@pytest.mark.parametrize('value',[1,2],ids=['a::b','c'])\n"
        "def test_imported(value): assert value > 0\n"
    )
    overrides = {}
    for i in range(1, 5):
        path = f"tests/test_{i}+[odd].py"
        overrides[path] = i
        (tmp_path / path).write_text(
            "from cases import test_imported\nclass TestGroup:\n"
            "    def test_pass(self): pass\n"
        )
    config = tmp_path / "shards.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "shard_count": 4,
                "overrides": overrides,
                "allowed_existing_nonpasses": [],
            }
        )
    )
    plain_report = tmp_path / "plain.json"
    plain = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "-p",
            "backend_ci",
            f"--backend-ci-report={plain_report}",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(TOOLS), "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert plain.returncode == 0, plain.stdout + plain.stderr
    plain_ids = backend_ci.read_json(plain_report)["collection"]["full_nodeids"]
    reports = []
    for i in range(1, 5):
        report = tmp_path / f"report-{i}.json"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/",
                "-q",
                "-p",
                "backend_ci",
                f"--backend-ci-report={report}",
                f"--backend-ci-shard={i}/4",
                f"--backend-ci-config={config}",
            ],
            cwd=tmp_path,
            env={**os.environ, "PYTHONPATH": str(TOOLS), "PYTEST_ADDOPTS": ""},
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        reports.append(backend_ci.read_json(report))
    full = reports[0]["collection"]["full_nodeids"]
    assert full == plain_ids
    assert len(full) == 12
    union = []
    for i, report in enumerate(reports, 1):
        assert report["collection"]["full_nodeids"] == full
        selected = report["collection"]["selected_nodeids"]
        assert selected == [
            node for node in full if node.startswith(f"tests/test_{i}+[")
        ]
        assert len(report["collection"]["deselected_nodeids"]) == 9
        assert all(
            path.startswith("tests/")
            for path in report["collection"]["file_assignments"]
        )
        union += selected
    assert sorted(union) == sorted(full)
    assert len(set(union)) == len(union)


def valid_gate_reports():
    import backend_ci

    reports = []
    full = [f"tests/test_{i}.py::test_ok" for i in range(1, 5)]
    mapping = {node.split("::")[0]: i for i, node in enumerate(full, 1)}
    inventory = ["pytest==1", "setuptools==2", "setuptools==2"]
    for i, node in enumerate(full, 1):
        identity = {
            "checkout_sha": "a" * 40,
            "github_sha": "a" * 40,
            "pr_head_sha": "b" * 40,
            "run_id": "17",
            "run_attempt": "2",
            "workflow": "quality",
            "shard": {"index": i, "count": 4},
            "python": {
                "version": "3.11.1",
                "implementation": "CPython",
                "executable": f"/tmp/{i}/python",
            },
            "distributions": inventory,
            "distribution_sha256": hashlib.sha256(
                "\n".join(inventory).encode()
            ).hexdigest(),
            "observer_sha256": "c" * 64,
            "runner_sha256": "d" * 64,
            "verify_sha256": "e" * 64,
            "config_sha256": "f" * 64,
            "input_sha256": {"requirements-ci.txt": "1" * 64},
            "backend_tree": "2" * 40,
            "uv_version": "uv 0.12.19",
        }
        reports.append(
            {
                "schema_version": 3,
                "identity": identity,
                "session": {
                    "finished": True,
                    "exit_code": 0,
                    "collect_only": False,
                    "interrupted": None,
                    "internal_errors": [],
                    "duration_seconds": 1.0,
                },
                "collection": {
                    "full_nodeids": full,
                    "selected_nodeids": [node],
                    "deselected_nodeids": [x for x in full if x != node],
                    "errors": [],
                    "skipped_collectors": [],
                    "duration_seconds": 0.1,
                    "file_assignments": mapping,
                    "nodeid_paths": {n: n.split("::")[0] for n in full},
                    "assignment_sha256": backend_ci.assignment_digest(mapping),
                },
                "allowed_existing_nonpasses": [],
                "phases": [
                    {
                        "nodeid": node,
                        "when": when,
                        "outcome": "passed",
                        "duration": 0.1,
                        "wasxfail": None,
                        "longrepr": None,
                        "skip_reason": None,
                    }
                    for when in ("setup", "call", "teardown")
                ],
            }
        )
    return reports


def test_gate_accepts_complete_disjoint_reports_and_distribution_multiset():
    import backend_ci

    reports = valid_gate_reports()
    result = backend_ci.validate_reports(
        reports,
        {
            "checkout_sha": "a" * 40,
            "run_id": "17",
            "run_attempt": "2",
            "pr_head_sha": "b" * 40,
        },
        {f"backend_{i}": {"result": "success"} for i in range(1, 5)},
    )
    assert result["cases"] == 4
    assert result["outcomes"] == {"passed": 4}


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-report",
        "extra-report",
        "wrong-sha",
        "wrong-github-sha",
        "wrong-run",
        "wrong-attempt",
        "wrong-head",
        "wrong-deps",
        "wrong-config",
        "empty",
        "missing-call",
        "duplicate-phase",
        "teardown-failure",
        "nonzero",
        "collection-error",
        "internal-error",
        "unfinished",
        "collect-only",
        "duplicate-id",
        "missing-id",
        "extra-phase",
        "wrong-selection",
        "wrong-assignment",
        "unexpected-skip",
        "unexpected-xfail",
        "bool-schema",
        "bool-shard",
        "nan-duration",
        "bad-type",
    ],
)
def test_gate_rejects_incomplete_or_altered_evidence(mutation):
    import backend_ci

    reports = valid_gate_reports()
    r = reports[0]
    if mutation == "missing-report":
        reports.pop()
    elif mutation == "extra-report":
        reports.append(reports[0])
    elif mutation.startswith("wrong-") and mutation in {
        "wrong-sha",
        "wrong-github-sha",
        "wrong-run",
        "wrong-attempt",
        "wrong-head",
        "wrong-deps",
        "wrong-config",
    }:
        key = {
            "wrong-sha": "checkout_sha",
            "wrong-github-sha": "github_sha",
            "wrong-run": "run_id",
            "wrong-attempt": "run_attempt",
            "wrong-head": "pr_head_sha",
            "wrong-deps": "distribution_sha256",
            "wrong-config": "config_sha256",
        }[mutation]
        r["identity"][key] = "wrong"
    elif mutation == "empty":
        r["collection"]["selected_nodeids"] = []
    elif mutation == "missing-call":
        r["phases"].pop(1)
    elif mutation == "duplicate-phase":
        r["phases"].append(dict(r["phases"][0]))
    elif mutation == "teardown-failure":
        r["phases"][-1]["outcome"] = "failed"
    elif mutation == "nonzero":
        r["session"]["exit_code"] = 1
    elif mutation == "collection-error":
        r["collection"]["errors"] = ["failure"]
    elif mutation == "internal-error":
        r["session"]["internal_errors"] = ["failure"]
    elif mutation == "unfinished":
        r["session"]["finished"] = False
    elif mutation == "collect-only":
        r["session"]["collect_only"] = True
    elif mutation == "duplicate-id":
        r["collection"]["full_nodeids"].append(r["collection"]["full_nodeids"][0])
    elif mutation == "missing-id":
        r["collection"]["full_nodeids"] = r["collection"]["full_nodeids"][:-1]
    elif mutation == "extra-phase":
        r["phases"][0]["nodeid"] = "unexpected"
    elif mutation == "wrong-selection":
        r["collection"]["selected_nodeids"] = [r["collection"]["full_nodeids"][1]]
    elif mutation == "wrong-assignment":
        r["collection"]["file_assignments"]["tests/test_1.py"] = 2
    elif mutation == "unexpected-skip":
        r["phases"][1]["outcome"] = "skipped"
        r["phases"][1]["skip_reason"] = "new skip"
    elif mutation == "unexpected-xfail":
        r["phases"][1]["wasxfail"] = "new xfail"
    elif mutation == "bool-schema":
        r["schema_version"] = True
    elif mutation == "bool-shard":
        r["identity"]["shard"]["index"] = True
    elif mutation == "nan-duration":
        r["phases"][0]["duration"] = float("nan")
    elif mutation == "bad-type":
        r["collection"]["full_nodeids"] = "not-a-list"
    with pytest.raises(ValueError):
        backend_ci.validate_reports(
            reports,
            {
                "checkout_sha": "a" * 40,
                "run_id": "17",
                "run_attempt": "2",
                "pr_head_sha": "b" * 40,
            },
            {f"backend_{i}": {"result": "success"} for i in range(1, 5)},
        )


@pytest.mark.parametrize(
    "status", ["failure", "cancelled", "skipped", "setupfailed", "unknown", None]
)
def test_actual_gate_cli_rejects_non_success_needs_before_download(tmp_path, status):
    needs = {f"backend_{i}": {"result": "success"} for i in range(1, 5)}
    if status is None:
        needs.pop("backend_2")
    else:
        needs["backend_2"]["result"] = status
    path = tmp_path / "needs.json"
    path.write_text(json.dumps(needs))
    result = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "backend_ci.py"),
            "check-needs",
            "--needs-json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert "backend_2" in result.stderr


def _owner_fixture(report, path, index):
    # The fixture uses the actual tracked canonical argv; producer correctness is
    # separately exercised end to end with the source verifier and real pytest.
    import copy
    import runpy

    commands = runpy.run_path(str(TOOLS / "verify"))["BACKEND_COMMANDS"]
    root = str(TOOLS.parent)
    run_root = str(path.parent.parent.parent / f"private-{index}")
    pipeline = []
    for position, (command, cwd) in enumerate(commands):
        command = list(command)
        if position == 1:
            command += [
                "-p",
                "backend_ci",
                f"--backend-ci-report={path}",
                f"--basetemp={run_root}/basetemp",
                f"--backend-ci-shard={index}/4",
            ]
        pipeline.append(
            {
                "label": "inventory" if position == 0 else "pytest",
                "command": command,
                "cwd": str(cwd),
            }
        )
    identity = report["identity"]
    context = {
        "schema_version": 1,
        "run_id": identity["run_id"],
        "run_attempt": identity["run_attempt"],
        "checkout_sha": identity["checkout_sha"],
        "checkout": root,
        "cwd": str(TOOLS.parent / "backend/starlink-location"),
        "report": str(path),
        "run_root": run_root,
        "shard": identity["shard"],
        "python_selector": pipeline[0]["command"][3],
        "verify_sha256": identity["verify_sha256"],
        "pipeline": pipeline,
        "pipeline_sha256": hashlib.sha256(
            json.dumps(pipeline, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    identity.update(
        checkout_path=root,
        cwd=context["cwd"],
        report_path=str(path),
        owner_context=copy.deepcopy(context),
        pytest_args=pipeline[1]["command"][
            pipeline[1]["command"].index("pytest") + 1 :
        ],
    )
    return {
        "context": context,
        "checkout": root,
        "report": str(path),
        "shard": f"{index}/4",
        "cleanup": {"survivors": [], "listeners": []},
        "private_paths_removed": True,
        "commands": [
            {
                **copy.deepcopy(stage),
                "exit_code": 0,
                "subprocess_returncode": 0,
                "harness_error": None,
                "cleanup_error": None,
            }
            for stage in pipeline
        ],
    }


def _gate_cli_fixture(tmp_path):
    import backend_ci

    reports = valid_gate_reports()
    expected = backend_ci._source_identity()
    sha = subprocess.run(
        ["git", "-C", str(TOOLS.parent), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    overrides = backend_ci.load_shard_config()["overrides"]
    paths = {}
    number = 0
    while len(paths) != 4:
        path = f"tests/test_unlisted_cli_{number}.py"
        number += 1
        paths.setdefault(backend_ci.assign_file(path, 4, overrides), path)
    full = [f"{paths[i]}::test_ok" for i in range(1, 5)]
    mapping = {paths[i]: i for i in range(1, 5)}
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    files = []
    for i, report in enumerate(reports, 1):
        report["identity"].update(expected, checkout_sha=sha, github_sha=sha)
        report["collection"].update(
            full_nodeids=full,
            selected_nodeids=[full[i - 1]],
            deselected_nodeids=[n for n in full if n != full[i - 1]],
            file_assignments=mapping,
            nodeid_paths={n: n.split("::")[0] for n in full},
            assignment_sha256=backend_ci.assignment_digest(mapping),
        )
        report["allowed_existing_nonpasses"] = backend_ci.load_shard_config()[
            "allowed_existing_nonpasses"
        ]
        for event in report["phases"]:
            event["nodeid"] = full[i - 1]
        name = backend_ci.report_name("17", "2", i)
        folder = artifacts / name
        folder.mkdir()
        path = folder / f"{name}.json"
        owner = _owner_fixture(report, path, i)
        path.write_text(json.dumps(report))
        files.append(path)
        (folder / "ownership.json").write_text(json.dumps(owner))
    needs = tmp_path / "needs.json"
    needs.write_text(
        json.dumps({f"backend_{i}": {"result": "success"} for i in range(1, 5)})
    )
    command = [
        sys.executable,
        str(TOOLS / "backend_ci.py"),
        "gate",
        "--reports",
        str(artifacts),
        "--needs-json",
        str(needs),
        "--sha",
        sha,
        "--run-id",
        "17",
        "--attempt",
        "2",
        "--pr-head-sha",
        "b" * 40,
    ]
    return command, artifacts, files


def test_actual_gate_cli_accepts_only_complete_current_artifacts(tmp_path):
    command, _, _ = _gate_cli_fixture(tmp_path)
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=15, check=False
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["cases"] == 4


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-artifact",
        "extra-artifact",
        "missing-report",
        "extra-report",
        "stale-name",
        "malformed",
        "duplicate-key",
        "nonfinite",
        "wrong-attempt",
        "wrong-sha",
        "wrong-head",
        "wrong-inputs",
        "wrong-sources",
        "altered-skip-allowance",
        "altered-mapping",
        "failed-session",
        "cleanup-survivors",
        "missing-ownership",
        "failed-command",
    ],
)
def test_actual_gate_cli_fails_closed_on_artifact_and_runtime_faults(
    tmp_path, mutation
):
    import shutil

    command, artifacts, files = _gate_cli_fixture(tmp_path)
    path = files[0]
    report = json.loads(path.read_text())
    if mutation == "missing-artifact":
        shutil.rmtree(path.parent)
    elif mutation == "extra-artifact":
        (artifacts / "stale-run-artifact").mkdir()
    elif mutation == "missing-report":
        path.unlink()
    elif mutation == "extra-report":
        (path.parent / "backend-report-stale.json").write_text("{}")
    elif mutation == "stale-name":
        path.rename(path.with_name("backend-report-old.json"))
    elif mutation == "malformed":
        path.write_text("{")
    elif mutation == "duplicate-key":
        path.write_text('{"schema_version": 3,"schema_version": 2}')
    elif mutation == "nonfinite":
        path.write_text('{"duration": NaN}')
    elif mutation in {
        "wrong-attempt",
        "wrong-sha",
        "wrong-head",
        "wrong-inputs",
        "wrong-sources",
    }:
        key = {
            "wrong-attempt": "run_attempt",
            "wrong-sha": "checkout_sha",
            "wrong-head": "pr_head_sha",
            "wrong-inputs": "input_sha256",
            "wrong-sources": "runner_sha256",
        }[mutation]
        report["identity"][key] = "wrong"
        path.write_text(json.dumps(report))
    elif mutation == "altered-skip-allowance":
        report["allowed_existing_nonpasses"] = []
        path.write_text(json.dumps(report))
    elif mutation == "altered-mapping":
        key = next(iter(report["collection"]["file_assignments"]))
        report["collection"]["file_assignments"][key] = 4
        path.write_text(json.dumps(report))
    elif mutation == "failed-session":
        report["session"]["exit_code"] = 1
        path.write_text(json.dumps(report))
    elif mutation == "missing-ownership":
        (path.parent / "ownership.json").unlink()
    else:
        owner = json.loads((path.parent / "ownership.json").read_text())
        if mutation == "cleanup-survivors":
            owner["cleanup"]["survivors"] = [{"pid": 1}]
        elif mutation == "failed-command":
            owner["commands"][0]["subprocess_returncode"] = 1
        (path.parent / "ownership.json").write_text(json.dumps(owner))
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=15, check=False
    )
    assert result.returncode != 0
    assert "backend gate error:" in result.stderr


@pytest.mark.parametrize("when", ["setup", "call"])
def test_gate_preserves_only_recorded_existing_skip_identity_and_reason(when):
    import backend_ci

    reports = valid_gate_reports()
    node = reports[0]["collection"]["selected_nodeids"][0]
    allowed = {
        "nodeid": node,
        "outcome": "skipped",
        "reason": "Skipped: existing reason",
    }
    for report in reports:
        report["allowed_existing_nonpasses"] = [allowed]
    phases = reports[0]["phases"]
    terminal = next(p for p in phases if p["when"] == when)
    terminal.update(outcome="skipped", skip_reason="Skipped: existing reason")
    if when == "setup":
        phases.pop(1)
    summary = backend_ci.validate_reports(
        reports,
        {
            "checkout_sha": "a" * 40,
            "run_id": "17",
            "run_attempt": "2",
            "pr_head_sha": "b" * 40,
        },
        {f"backend_{i}": {"result": "success"} for i in range(1, 5)},
    )
    assert summary["outcomes"] == {"skipped": 1, "passed": 3}


@pytest.mark.parametrize(
    "override",
    [
        "PYTEST_ADDOPTS",
        "PYTEST_PLUGINS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_DEBUG",
    ],
)
def test_reported_runs_reject_inherited_pytest_overrides(override):
    import backend_ci

    with pytest.raises(ValueError, match=override):
        backend_ci.reject_pytest_overrides({override: "unexpected"})


def test_real_empty_shard_is_nonzero_and_cannot_supply_success_evidence(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_only.py").write_text("def test_ok(): pass\n")
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "shard_count": 4,
                "overrides": {"tests/test_only.py": 1},
                "allowed_existing_nonpasses": [],
            }
        )
    )
    report = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "-p",
            "backend_ci",
            "--backend-ci-shard=4/4",
            f"--backend-ci-config={config}",
            f"--backend-ci-report={report}",
        ],
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(TOOLS), "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode != 0
    assert "empty selected shard" in result.stdout + result.stderr
    if report.exists():
        assert json.loads(report.read_text())["session"]["exit_code"] != 0


@pytest.mark.parametrize(
    "source,reason",
    [
        (
            "import pytest\npytest.skip('collector unavailable', allow_module_level=True)\n",
            "collector unavailable",
        ),
        (
            "import pytest\npytest.importorskip('ci404_nonexistent_optional_dependency')\n",
            "ci404_nonexistent_optional_dependency",
        ),
    ],
)
def test_actual_gate_rejects_real_skipped_collector_with_identical_reduced_manifests(
    tmp_path, source, reason
):
    command, _, files = _gate_cli_fixture(tmp_path)
    fixture = tmp_path / "suite"
    fixture.mkdir()
    template = json.loads(files[0].read_text())
    for path in template["collection"]["file_assignments"]:
        target = fixture / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("def test_ok(): pass\n")
    (fixture / "tests/test_unavailable.py").write_text(source)
    actual = fixture / "actual.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/",
            "-q",
            "-p",
            "backend_ci",
            f"--backend-ci-report={actual}",
        ],
        cwd=fixture,
        env={**os.environ, "PYTHONPATH": str(TOOLS), "PYTEST_ADDOPTS": ""},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(actual.read_text())
    full = observed["collection"]["full_nodeids"]
    assert len(full) == 4 and all("unavailable" not in node for node in full)
    for path in files:
        report = json.loads(path.read_text())
        assert set(report["collection"]["full_nodeids"]) == set(full)
        report["collection"]["skipped_collectors"] = observed["collection"].get(
            "skipped_collectors", []
        )
        path.write_text(json.dumps(report))
    gated = subprocess.run(
        command, capture_output=True, text=True, timeout=15, check=False
    )
    assert (
        gated.returncode != 0
    ), "identically reduced manifests with a real skipped module passed the aggregate"
    skipped = observed["collection"]["skipped_collectors"]
    assert len(skipped) == 1
    assert skipped[0]["nodeid"] == "tests/test_unavailable.py"
    assert reason in skipped[0]["reason"]
    assert "collector" in gated.stderr


@pytest.mark.parametrize(
    "mutation",
    [
        "owner-run",
        "owner-attempt",
        "owner-sha",
        "owner-shard",
        "owner-report",
        "owner-checkout",
        "owner-cwd",
        "owner-selection",
        "inventory-only",
        "missing-inventory",
        "unlabelled",
        "different-command",
        "wrong-command-cwd",
        "matching-filtered-plan",
        "observed-selection",
        "owner-bool-schema",
    ],
)
def test_actual_gate_cli_rejects_mismatched_owner_and_incomplete_pipeline(
    tmp_path, mutation
):
    command, _, files = _gate_cli_fixture(tmp_path)
    path = files[0].parent / "ownership.json"
    owner = json.loads(path.read_text())
    key = {
        "owner-run": "run_id",
        "owner-attempt": "run_attempt",
        "owner-sha": "checkout_sha",
        "owner-shard": "shard",
        "owner-report": "report",
        "owner-checkout": "checkout",
        "owner-cwd": "cwd",
    }
    if mutation in key:
        owner["context"][key[mutation]] = "different"
    elif mutation == "owner-selection":
        owner["context"]["pipeline"][1]["command"].append("-k=omit")
    elif mutation == "inventory-only":
        owner["commands"] = owner["commands"][:1]
    elif mutation == "missing-inventory":
        owner["commands"] = owner["commands"][1:]
    elif mutation == "unlabelled":
        owner["commands"][1].pop("label")
    elif mutation == "different-command":
        owner["commands"][1]["command"].append("-k=omit")
    elif mutation == "wrong-command-cwd":
        owner["commands"][1]["cwd"] = "/another/checkout"
    elif mutation in {"matching-filtered-plan", "owner-bool-schema"}:
        report = json.loads(files[0].read_text())
        if mutation == "matching-filtered-plan":
            owner["context"]["pipeline"][1]["command"].append("-k=omit")
            owner["commands"][1]["command"].append("-k=omit")
            report["identity"]["pytest_args"].append("-k=omit")
            owner["context"]["pipeline_sha256"] = hashlib.sha256(
                json.dumps(
                    owner["context"]["pipeline"], sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()
        else:
            owner["context"]["schema_version"] = True
        report["identity"]["owner_context"] = owner["context"]
        files[0].write_text(json.dumps(report))
    elif mutation == "observed-selection":
        report = json.loads(files[0].read_text())
        report["identity"]["pytest_args"].append("-k=omit")
        files[0].write_text(json.dumps(report))
    path.write_text(json.dumps(owner))
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=15, check=False
    )
    assert (
        result.returncode != 0
    ), f"{mutation} accepted unrelated/incomplete ownership evidence"
    assert "backend gate error:" in result.stderr
