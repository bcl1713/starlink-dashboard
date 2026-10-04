"""Runner safety: reject mutable builds and occupied task ports before Docker."""

import os
from pathlib import Path
import shutil
import socket
import subprocess

import pytest

RUNNER = Path(__file__).parents[1] / "acceptance/overview-window-sync/run.sh"


@pytest.fixture
def checkout(tmp_path):
    runner = tmp_path / "tools/acceptance/overview-window-sync/run.sh"
    runner.parent.mkdir(parents=True)
    shutil.copyfile(RUNNER, runner)
    (tmp_path / "input.txt").write_text("confirmed")
    for args in (
        ["init", "-q"],
        ["add", "."],
        [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "candidate",
        ],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True)
    return tmp_path, runner


def invoke(checkout):
    root, runner = checkout
    return subprocess.run(
        ["bash", str(runner), "--check"],
        cwd=root,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )


def test_refuses_dirty_tracked_build(checkout):
    (checkout[0] / "input.txt").write_text("draft")
    result = invoke(checkout)
    assert result.returncode != 0
    assert "clean tracked worktree" in result.stderr


@pytest.mark.parametrize("port", [15257, 18257])
def test_refuses_occupied_loopback_port(checkout, port):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", port))
        listener.listen()
        result = invoke(checkout)
    assert result.returncode != 0
    assert f"127.0.0.1:{port}" in result.stderr
    assert "occupied" in result.stderr
