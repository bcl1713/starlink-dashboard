"""Ordinary local Compose builds bind both images to the checked-out commit."""

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ("starlink-location", "mission-planner")


def _compose_config(tmp_path: Path, sha: str) -> dict:
    shutil.copy(ROOT / "docker-compose.yml", tmp_path / "docker-compose.yml")
    shutil.copy(ROOT / ".env.example", tmp_path / ".env")
    result = subprocess.run(
        ["docker", "compose", "config", "--format", "json"],
        cwd=tmp_path,
        env={**os.environ, "ACCEPTANCE_CANDIDATE_SHA": sha},
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_local_compose_renders_both_builds_with_exact_full_sha(tmp_path: Path) -> None:
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    config = _compose_config(tmp_path, sha)
    assert len(sha) == 40
    assert {name: config["services"][name]["build"]["args"] for name in SERVICES} == {
        name: {"ACCEPTANCE_CANDIDATE_SHA": sha} for name in SERVICES
    }


def test_local_compose_respects_explicit_sha_override(tmp_path: Path) -> None:
    sha = "b" * 40
    config = _compose_config(tmp_path, sha)
    assert all(
        config["services"][name]["build"]["args"]["ACCEPTANCE_CANDIDATE_SHA"] == sha
        for name in SERVICES
    )


def _fake_docker(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$ACCEPTANCE_CANDIDATE_SHA" "$@" > "$COMPOSE_CAPTURE"\nexit "${FAKE_COMPOSE_STATUS:-0}"\n'
    )
    docker.chmod(0o755)
    return bin_dir


def test_wrapper_forwards_flags_and_overrides_stale_environment(tmp_path: Path) -> None:
    bin_dir = _fake_docker(tmp_path)
    capture = tmp_path / "capture"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "COMPOSE_CAPTURE": str(capture),
        "ACCEPTANCE_CANDIDATE_SHA": "stale",
    }
    result = subprocess.run(
        [str(ROOT / "scripts/compose.sh"), "-p", "local-test", "up", "-d", "--build"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    assert result.returncode == 0, result.stderr
    assert capture.read_text().splitlines() == [
        sha,
        "compose",
        "-p",
        "local-test",
        "up",
        "-d",
        "--build",
    ]


def test_wrapper_fails_without_git_sha_before_compose(tmp_path: Path) -> None:
    bin_dir = _fake_docker(tmp_path)
    capture = tmp_path / "capture"
    git = bin_dir / "git"
    git.write_text("#!/bin/sh\nexit 1\n")
    git.chmod(0o755)
    result = subprocess.run(
        [str(ROOT / "scripts/compose.sh"), "build"],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "COMPOSE_CAPTURE": str(capture),
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "SHA" in result.stderr
    assert not capture.exists()


def test_wrapper_propagates_compose_error(tmp_path: Path) -> None:
    bin_dir = _fake_docker(tmp_path)
    capture = tmp_path / "capture"
    result = subprocess.run(
        [str(ROOT / "scripts/compose.sh"), "config"],
        env={
            **os.environ,
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "COMPOSE_CAPTURE": str(capture),
            "FAKE_COMPOSE_STATUS": "37",
        },
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 37
    assert capture.read_text().splitlines()[-2:] == ["compose", "config"]
