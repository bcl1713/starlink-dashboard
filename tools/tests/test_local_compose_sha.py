"""Ordinary local Compose builds bind all images to the checked-out commit."""

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ("starlink-location", "mission-planner", "gfs-worker")


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
    assert all(
        config["services"][name]["build"]["args"]["ACCEPTANCE_CANDIDATE_SHA"] == sha
        for name in SERVICES
    )


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


def _wrapper_checkout(tmp_path: Path) -> Path:
    shutil.copytree(ROOT / "scripts", tmp_path / "scripts")
    for name in ("docker-compose.yml", "docker-compose.gfs.yml"):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copy(ROOT / ".env.example", tmp_path / ".env")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "test",
        ],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path / "scripts/compose.sh"


def _wrapper_config(wrapper: Path, *args: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    result = subprocess.run(
        [str(wrapper), *args, "config", "--format", "json"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_default_stack_has_worker_without_profile_and_shared_mounts(tmp_path: Path):
    services = _wrapper_config(_wrapper_checkout(tmp_path))["services"]
    worker = services["gfs-worker"]
    assert not worker.get("profiles")
    assert worker["cpus"] == 1.0 and int(worker["mem_limit"]) == 1024**3
    assert "ports" not in worker
    api_mounts = {v["target"]: v for v in services["starlink-location"]["volumes"]}
    worker_mounts = {v["target"]: v for v in worker["volumes"]}
    assert api_mounts["/app/data/gfs"]["read_only"]
    for path in ("/app/data/gfs", "/app/data/gfs-mailbox", "/app/data/settings"):
        assert api_mounts[path]["source"] == worker_mounts[path]["source"]
    assert worker_mounts["/app/data/settings"]["read_only"]
    # The worker must see the same persisted settings and IPC as the API.
    assert (
        worker["environment"]["AVIATION_SETTINGS_PATH"]
        == "/app/data/settings/aviation-weather.json"
    )


def test_default_stack_keeps_native_local_overrides(tmp_path: Path):
    wrapper = _wrapper_checkout(tmp_path)
    (tmp_path / "docker-compose.override.yml").write_text(
        'services:\n  starlink-location:\n    environment:\n      LOCAL_OVERRIDE: "preserved"\n'
    )
    services = _wrapper_config(wrapper)["services"]
    assert services["starlink-location"]["environment"]["LOCAL_OVERRIDE"] == "preserved"
    assert "gfs-worker" in services


def test_dotenv_can_select_custom_stack(tmp_path: Path):
    wrapper = _wrapper_checkout(tmp_path)
    (tmp_path / "custom.yml").write_text(
        "services:\n  custom:\n    image: alpine:3.20\n"
    )
    (tmp_path / ".env").write_text("COMPOSE_FILE=custom.yml\n")
    assert set(_wrapper_config(wrapper)["services"]) == {"custom"}


def test_existing_explicit_gfs_overlay_command_still_works(tmp_path: Path):
    services = _wrapper_config(
        _wrapper_checkout(tmp_path),
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.gfs.yml",
        "--profile",
        "gfs",
    )["services"]
    assert "gfs-worker" in services
    for name in ("gfs-worker", "starlink-location"):
        targets = [v["target"] for v in services[name]["volumes"]]
        assert targets.count("/app/data/gfs") == 1
        assert targets.count("/app/data/gfs-mailbox") == 1
