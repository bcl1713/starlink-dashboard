import importlib.machinery
import importlib.util
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


def test_backend_command_uses_backend_directory(monkeypatch):
    module = load_verify()
    calls = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda command, cwd, check: calls.append((command, cwd))
        or types.SimpleNamespace(returncode=0),
    )

    assert module.main(["tools/verify", "backend"]) == 0
    assert calls == [(module.tier_commands("backend")[0][0], module.BACKEND)]


def test_backend_command_uses_manifest_resolved_from_repository_root():
    module = load_verify()

    command, cwd = module.tier_commands("backend")[0]
    assert cwd == module.BACKEND
    assert command[3] == str(module.ROOT / "backend/starlink-location/requirements-dev.txt")


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


def test_all_stops_at_first_failed_child_and_preserves_status(monkeypatch):
    module = load_verify()
    calls = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd))
        return types.SimpleNamespace(returncode=17)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main(["tools/verify", "all"]) == 17
    assert calls == [module.tier_commands("static")[0]]


def test_backend_tier_dispatches_from_nested_caller_directory():
    result = run("backend", cwd=ROOT / "backend/starlink-location")

    assert result.returncode == 0


def test_all_dispatches_static_backend_and_frontend_in_order(monkeypatch):
    module = load_verify()
    calls = []

    def fake_run(command, cwd, check):
        calls.append((command, cwd))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(module.subprocess, "run", fake_run)

    assert module.main(["tools/verify", "all"]) == 0
    assert calls == [
        *module.tier_commands("static"),
        *module.tier_commands("backend"),
        *module.tier_commands("frontend"),
    ]
