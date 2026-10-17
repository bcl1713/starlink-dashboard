"""Occupied Docker identities never grant a new runner teardown authority."""

import json
import subprocess
import sys

import pytest
from test_operator_journal_acceptance import implementation, repository


@pytest.mark.parametrize("kind", ["container", "network", "volume", "image"])
def test_occupied_project_is_untouched(tmp_path, monkeypatch, kind):
    module = implementation()
    sha = repository(tmp_path / "repo")
    commands = []
    foreign = {"retained": True}

    def execute(self, command, **kwargs):
        commands.append(command)
        if any(word in command for word in ("down", "rm", "build", "up")):
            foreign["retained"] = False
        if command[:2] == ["docker", kind]:
            return "foreign-resource\n"
        return ""

    def build(*args):
        pytest.fail("Occupied project reached allocation")

    monkeypatch.setattr(module, "ROOT", tmp_path / "repo")
    monkeypatch.setattr(module.Owner, "execute", execute)
    monkeypatch.setattr(module, "build_candidate", build)
    with pytest.raises(RuntimeError, match="occupied"):
        module.run(sha, "starlink-operator-collision-test", tmp_path / "evidence")
    assert foreign["retained"]
    assert not any("compose" in command for command in commands)
    report = json.loads((tmp_path / "evidence/summary.json").read_text())
    assert report["cleanup"]["admitted"] is False


def test_project_reservation_is_cross_process_and_released(tmp_path):
    module = implementation()
    assert hasattr(module.Owner, "admit"), "Project reservation is missing"
    child_code = """
import sys
sys.path.insert(0, sys.argv[1])
from ownership import Owner
owner = Owner('starlink-operator-concurrent-test', sys.argv[2])
owner.execute = lambda *args, **kwargs: ''
owner.admit()
print('reserved', flush=True)
sys.stdin.read()
owner.release()
"""
    child = subprocess.Popen(
        [
            sys.executable,
            "-u",
            "-c",
            child_code,
            str(module.ROOT / "tools/acceptance/operator-journal"),
            str(tmp_path / "child"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    contender = module.Owner(
        "starlink-operator-concurrent-test", tmp_path / "contender"
    )
    contender.execute = lambda *args, **kwargs: ""
    try:
        assert child.stdout.readline().strip() == "reserved"
        with pytest.raises(RuntimeError, match="reserved"):
            contender.admit()
        assert contender.close()["admitted"] is False
        child.communicate(timeout=5)
        assert child.returncode == 0
        contender.admit()
        assert contender.admitted
    finally:
        contender.release()
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=5)
