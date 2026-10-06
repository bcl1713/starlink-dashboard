"""The comparison runner owns and reaps only its private runtime resources."""

import json
import socket
import subprocess
import sys
from pathlib import Path

from acceptance.weather_detail_comparison.owned import run_owned

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/acceptance/weather_detail_comparison/run.sh"


def test_timeout_reaps_owned_process_and_listener(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    code = f'import socket,time; s=socket.socket(); s.bind(("127.0.0.1",{port})); s.listen(); time.sleep(60)'
    result = run_owned([sys.executable, "-c", code], 0.2, tmp_path)
    assert result == 124
    owner = json.loads((tmp_path / "process-owner.json").read_text())
    assert not Path(f'/proc/{owner["child_pid"]}').exists()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
    assert (
        json.loads((tmp_path / "process-cleanup.json").read_text())["status"]
        == "passed"
    )


def test_owned_runner_preserves_child_failure(tmp_path):
    assert run_owned([sys.executable, "-c", "raise SystemExit(7)"], 2, tmp_path) == 7
    assert (tmp_path / "process-cleanup.json").exists()


def test_cleanup_failure_is_nonzero(tmp_path, monkeypatch):
    from acceptance.weather_detail_comparison import owned

    monkeypatch.setattr(owned, "terminate_group", lambda child: False)
    assert run_owned([sys.executable, "-c", "pass"], 2, tmp_path) != 0
    assert (
        json.loads((tmp_path / "process-cleanup.json").read_text())["status"]
        == "failed"
    )


def test_ownership_precedes_child_execution(tmp_path):
    path = tmp_path / "process-owner.json"
    code = f'import json; from pathlib import Path; d=json.loads(Path({str(path)!r}).read_text()); assert d["owner_pid"] and d["command"]'
    assert run_owned([sys.executable, "-c", code], 2, tmp_path) == 0


def test_check_without_docker_browser_or_capture():
    result = subprocess.run(
        ["bash", str(RUNNER), "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_reject_non_exact_sha_before_resources():
    result = subprocess.run(
        ["bash", str(RUNNER), "dev"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "exact" in result.stderr
