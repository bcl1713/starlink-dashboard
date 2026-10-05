"""Guard candidate identity and exclusive ownership before production startup."""

import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "tools/acceptance/simulation-speed/run.sh"


@pytest.fixture
def candidate(tmp_path):
    assert RUNNER.exists(), "Paced production runner is not implemented"
    repo = tmp_path / "repo"
    repo.mkdir()
    script = repo / "run.sh"
    script.write_text(RUNNER.read_text())
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "candidate",
        ],
        check=True,
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$*" >> "$DOCKER_LOG"\nif [ "$FAKE_EXISTING" = 1 ]; then echo occupied; fi\n'
    )
    docker.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "DOCKER_LOG": str(tmp_path / "docker.log"),
        "FAKE_EXISTING": "0",
        "DOCKER_HOST": "unix:///actor.sock",
    }
    return repo, script, env


def run(candidate, **changes):
    repo, script, env = candidate
    return subprocess.run(
        ["bash", str(script), "--check"],
        cwd=repo,
        env={**env, **changes},
        capture_output=True,
        text=True,
    )


def test_rejects_dirty_or_wrong_candidate(candidate):
    repo, script, _env = candidate
    assert run(candidate, ACCEPTANCE_CANDIDATE_SHA="0" * 40).returncode == 2
    script.write_text(script.read_text() + "\n# dirty\n")
    result = run(candidate)
    assert result.returncode == 2
    assert "clean" in result.stderr.lower()
    assert not (repo.parent / "docker.log").exists()


def test_refuses_existing_project(candidate):
    result = run(candidate, FAKE_EXISTING="1")
    assert result.returncode == 2
    assert "Existing starlink-262" in result.stderr
    log = Path(candidate[2]["DOCKER_LOG"]).read_text()
    assert "build" not in log and "down" not in log


def test_uses_archived_production_sources():
    source = RUNNER.read_text()
    compose = (RUNNER.parent / "compose.yml").read_text()
    assert 'git archive "$ACCEPTANCE_CANDIDATE_SHA"' in source
    assert "SIMULATION_SPEED_SOURCE_ROOT" in compose
    assert "15262:80" in compose and "8000:8000" not in compose
    assert "main:app" in source
    assert "git status --porcelain" in source
    assert "DOCKER_HOST" in source and "unset DOCKER" not in source
    assert "--workers" not in compose


def test_cleans_only_owned_resources():
    source = RUNNER.read_text()
    assert "trap cleanup EXIT" in source
    assert "result=$?" in source
    assert "if [[ $started == 1 ]]" in source
    assert "down --volumes" in source
    assert "com.docker.compose.project=starlink-262" in source
    assert "docker system prune" not in source and "docker volume prune" not in source
    assert 'rm -rf -- "$SIMULATION_SPEED_SOURCE_ROOT"' in source
