import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "tools/verify"


def run(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VERIFY), *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def load_verify():
    loader = importlib.machinery.SourceFileLoader("verify", str(VERIFY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_invalid_tier_returns_usage_without_running_child():
    result = run("invalid")

    assert result.returncode == 2
    assert "static|backend|frontend|all" in result.stderr


def test_invalid_tier_returns_usage_from_nested_directory():
    result = run("invalid", cwd=ROOT / "backend/starlink-location")

    assert result.returncode == 2
    assert "static|backend|frontend|all" in result.stderr


def test_backend_command_uses_backend_directory(monkeypatch, capsys):
    module = load_verify()
    calls = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, cwd, check: calls.append((command, cwd))
        or types.SimpleNamespace(returncode=0),
    )

    assert module.main(["tools/verify", "backend"]) == 0
    assert calls == module.tier_commands("backend")
    assert "elapsed=" in capsys.readouterr().out


def test_backend_command_uses_manifest_resolved_from_repository_root(monkeypatch):
    monkeypatch.delenv("UV_PYTHON", raising=False)
    module = load_verify()

    command, cwd = module.tier_commands("backend")[0]
    assert cwd == module.BACKEND
    assert str(module.BACKEND / "requirements-dev.txt") in command
    assert str(module.BACKEND / "requirements-gfs.txt") in command
    assert str(module.BACKEND / "requirements-ci.txt") in command
    assert command[command.index("--python") + 1] == "3.11"
    pytest_command = module.tier_commands("backend")[-1][0]
    assert pytest_command[pytest_command.index("pytest") :] == [
        "pytest",
        "tests/",
        "-q",
        "--durations=50",
        "--durations-min=0",
    ]


def test_static_prettier_uses_root_relative_frontend_source_glob():
    module = load_verify()

    command, cwd = module.tier_commands("static")[3]
    assert cwd == module.ROOT
    assert command == [
        "npm",
        "--prefix",
        "frontend/mission-planner",
        "exec",
        "--",
        "prettier",
        "--check",
        "frontend/mission-planner/src/**/*.{ts,tsx,js,jsx,json,md}",
    ]


def test_all_stops_at_first_failed_child_and_preserves_status(monkeypatch, capsys):
    module = load_verify()
    base = module.os.environ["ACCEPTANCE_POLICY_BASE_SHA"]
    git_calls = []
    child_calls = []

    def fake_run(command, cwd, check, **kwargs):
        if command[0] == "git":
            git_calls.append((command, cwd, check, kwargs))
            return types.SimpleNamespace(returncode=0, stdout="")
        assert kwargs == {}
        assert check is False
        child_calls.append((command, cwd))
        return types.SimpleNamespace(returncode=17)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main(["tools/verify", "all"]) == 17
    assert git_calls == [
        (
            ["git", "cat-file", "-e", f"{base}^{{commit}}"],
            module.ROOT,
            False,
            {"capture_output": True},
        ),
        (
            ["git", "merge-base", "--is-ancestor", base, "HEAD"],
            module.ROOT,
            False,
            {"capture_output": True},
        ),
        (
            ["git", "diff", "--unified=0", f"{base}..HEAD"],
            module.ROOT,
            True,
            {"capture_output": True, "text": True},
        ),
    ]
    assert child_calls == [module.tier_commands("static")[0]]
    assert "exit=17" in capsys.readouterr().out


def test_backend_tier_dispatches_from_nested_caller_directory(tmp_path, monkeypatch):
    # Exercise dispatch without launching the full backend suite.
    uv = tmp_path / "uv"
    uv.write_text("#!/bin/sh\npwd\nprintf '%s\\n' \"$@\"\n")
    uv.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    result = run("backend", cwd=ROOT / "backend/starlink-location")

    assert result.returncode == 0
    assert str(ROOT / "backend/starlink-location") in result.stdout
    assert "pytest" in result.stdout


def test_all_dispatches_static_backend_and_frontend_in_order(monkeypatch):
    module = load_verify()
    base = module.os.environ["ACCEPTANCE_POLICY_BASE_SHA"]
    git_calls = []
    child_calls = []

    def fake_run(command, cwd, check, **kwargs):
        if command[0] == "git":
            git_calls.append((command, cwd, check, kwargs))
            return types.SimpleNamespace(returncode=0, stdout="")
        assert kwargs == {}
        assert check is False
        child_calls.append((command, cwd))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main(["tools/verify", "all"]) == 0
    assert git_calls == [
        (
            ["git", "cat-file", "-e", f"{base}^{{commit}}"],
            module.ROOT,
            False,
            {"capture_output": True},
        ),
        (
            ["git", "merge-base", "--is-ancestor", base, "HEAD"],
            module.ROOT,
            False,
            {"capture_output": True},
        ),
        (
            ["git", "diff", "--unified=0", f"{base}..HEAD"],
            module.ROOT,
            True,
            {"capture_output": True, "text": True},
        ),
    ]
    assert child_calls == [
        *module.tier_commands("static"),
        *module.tier_commands("backend"),
        *module.tier_commands("frontend"),
    ]


def test_backend_python_can_use_ci_setup_interpreter(monkeypatch):
    monkeypatch.setenv("UV_PYTHON", "/opt/hostedtoolcache/Python/3.11/bin/python")
    module = load_verify()
    for command, _ in module.tier_commands("backend"):
        assert command[command.index("--python") + 1] == module.os.environ["UV_PYTHON"]


def test_backend_inventory_executes_and_prints_versions():
    module = load_verify()
    command = module.BACKEND_COMMANDS[0][0]
    code = command[command.index("-c") + 1]
    result = subprocess.run(
        [sys.executable, "-c", code], text=True, capture_output=True, check=False
    )
    assert f"Python: {sys.version.split()[0]}" in result.stdout
    assert "executable:" in result.stdout
    if sys.version_info[:2] == (3, 11):
        assert result.returncode == 0, result.stderr
        assert "Installed distributions:\n" in result.stdout
        assert "pytest==" in result.stdout
    else:
        assert result.returncode != 0
        assert "backend requires Python 3.11" in result.stderr


def test_stale_backend_lock_stops_before_uv(tmp_path, monkeypatch, capsys):
    module = load_verify()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **kw: calls.append(a))
    assert module.main(["tools/verify", "backend"]) == 2
    assert calls == []
    assert "regenerate" in capsys.readouterr().err.lower()


def test_reported_backend_rejects_invalid_combinations_before_uv(tmp_path, monkeypatch):
    module = load_verify()
    calls = []
    monkeypatch.setattr(
        module.subprocess, "run", lambda *args, **kwargs: calls.append(args)
    )
    for options in (
        ["--shard", "1/4"],
        [
            "--shard",
            "0/4",
            "--report",
            str(tmp_path / "r.json"),
            "--run-root",
            str(tmp_path / "private"),
        ],
        ["--report", "relative.json", "--run-root", str(tmp_path / "private")],
        ["--report", str(tmp_path / "r.json")],
        ["--run-root", str(tmp_path / "private")],
        [
            "--shard",
            "1/3",
            "--report",
            str(tmp_path / "r.json"),
            "--run-root",
            str(tmp_path / "private"),
        ],
    ):
        assert module.main(["tools/verify", "backend", *options]) == 2
    assert calls == []
    assert (
        module.main(["tools/verify", "all", "--report", str(tmp_path / "r.json")]) == 2
    )
    assert calls == []


def test_reported_backend_dispatches_through_owned_source_wrapper(
    tmp_path, monkeypatch
):
    module = load_verify()
    calls = []
    monkeypatch.setattr(
        module, "run_backend", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    report, root = tmp_path / "evidence/report.json", tmp_path / "private"
    assert (
        module.main(
            [
                "tools/verify",
                "backend",
                "--shard",
                "2/4",
                "--report",
                str(report),
                "--run-root",
                str(root),
            ]
        )
        == 0
    )
    assert calls == [
        (
            (module.ROOT, module.BACKEND_COMMANDS),
            {"report": report, "run_root": root, "shard": "2/4"},
        )
    ]


def test_static_mandatorily_runs_backend_gate_contracts():
    module = load_verify()
    pytest_command = next(cmd for cmd, _ in module.STATIC if "pytest" in cmd)
    for name in (
        "test_acceptance_platform_typing_policy.py",
        "test_docs_links.py",
        "test_backend_ci.py",
        "test_backend_test_runner.py",
        "test_verify.py",
        "test_quality_gate_workflow.py",
    ):
        assert f"tools/tests/{name}" in pytest_command
