import json
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_COMPOSE_PATH = REPO_ROOT / "deployment" / "portainer-ghcr-compose.yml"
LOCAL_COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
PUBLISH_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish-ghcr.yml"
SMOKE_SCRIPT_PATH = REPO_ROOT / "tools" / "smoke-portainer-profile.sh"


def run_smoke_with_command_doubles(
    tmp_path: Path, sha: str, *, worker_status: int = 0
) -> tuple[subprocess.CompletedProcess[str], list[list[str]]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "if sys.argv[1:] != ['-C', os.environ['SMOKE_REPO_ROOT'], 'rev-parse', '--verify', 'HEAD']:\n"
        "    sys.exit(2)\n"
        "print(os.environ['SMOKE_GIT_SHA'])\n",
        encoding="utf-8",
    )
    git.chmod(0o755)
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['SMOKE_DOCKER_LOG'], 'a', encoding='utf-8') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if 'exec' in sys.argv and any('GfsMailbox' in arg for arg in sys.argv):\n"
        "    sys.exit(int(os.environ.get('SMOKE_WORKER_STATUS', '0')))\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    sleep = bin_dir / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    sleep.chmod(0o755)
    log_path = tmp_path / "docker.jsonl"
    result = subprocess.run(
        ["bash", str(SMOKE_SCRIPT_PATH)],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "TMPDIR": str(tmp_path),
            "SMOKE_REPO_ROOT": str(REPO_ROOT),
            "SMOKE_GIT_SHA": sha,
            "SMOKE_DOCKER_LOG": str(log_path),
            "SMOKE_WORKER_STATUS": str(worker_status),
        },
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    calls = (
        [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
        if log_path.exists()
        else []
    )
    return result, calls


def test_portainer_smoke_passes_checked_out_sha_to_product_builds(
    tmp_path: Path,
) -> None:
    sha = "a" * 40
    result, calls = run_smoke_with_command_doubles(tmp_path, sha)

    assert result.returncode == 0, result.stderr
    builds = [call for call in calls if call[0] == "build"]
    assert len(builds) == 4
    for product in ("backend/starlink-location", "frontend/mission-planner"):
        build = next(
            call
            for call in builds
            if call[-1] == str(REPO_ROOT / product)
            and (
                "--file" not in call
                or not call[call.index("--file") + 1].endswith("Dockerfile.gfs")
            )
        )
        assert (
            build[build.index("--build-arg") + 1] == f"ACCEPTANCE_CANDIDATE_SHA={sha}"
        )
        assert build[build.index("--tag") + 1].endswith(f":sha-{sha}")
    assert any(call[:2] == ["network", "create"] for call in calls)
    assert any(call[:2] == ["network", "rm"] for call in calls)


@pytest.mark.parametrize("sha", ["", "not-a-sha", "A" * 40])
def test_portainer_smoke_rejects_invalid_sha_before_creating_resources(
    tmp_path: Path, sha: str
) -> None:
    result, calls = run_smoke_with_command_doubles(tmp_path, sha)

    assert result.returncode != 0
    assert "full 40-character lowercase commit SHA" in result.stderr
    assert calls == []
    assert not list(tmp_path.glob("starlink-ghcr-smoke-*"))


def test_portainer_profile_uses_immutable_ghcr_images_and_stable_proxy_aliases() -> (
    None
):
    compose = DEPLOY_COMPOSE_PATH.read_text(encoding="utf-8")

    assert "ghcr.io/bcl1713/starlink-dashboard/" in compose
    assert "build:" not in compose
    assert "${STARLINK_IMAGE_TAG:?Set an immutable GHCR image tag}" in compose
    assert "proxy:" in compose
    assert "external: true" in compose
    assert "aliases:" in compose
    for service_name in (
        "starlink-location",
        "mission-planner",
        "prometheus",
    ):
        assert f"- {service_name}" in compose


def test_portainer_profile_uses_required_host_paths_and_packaged_monitoring_images() -> (
    None
):
    compose = DEPLOY_COMPOSE_PATH.read_text(encoding="utf-8")
    local_compose = LOCAL_COMPOSE_PATH.read_text(encoding="utf-8")
    workflow = PUBLISH_WORKFLOW_PATH.read_text(encoding="utf-8")
    smoke_script = SMOKE_SCRIPT_PATH.read_text(encoding="utf-8")

    for variable in (
        "STARLINK_APP_DATA_PATH",
        "STARLINK_ROUTE_DATA_PATH",
        "STARLINK_PROMETHEUS_DATA_PATH",
    ):
        assert f"${{{variable}:?Set" in compose
    assert "type: bind" in compose
    assert "../monitoring/" not in compose
    assert "ghcr.io/bcl1713/starlink-dashboard/prometheus:" in compose
    assert "prom/prometheus:v3.5.0" in local_compose
    assert "prom/prometheus:latest" not in local_compose
    assert "branches: [dev]" in workflow
    assert "type=sha,format=long,prefix=sha-" in workflow
    assert "org.opencontainers.image.source" in workflow
    assert "org.opencontainers.image.revision" in workflow
    assert "docker compose" in smoke_script
    assert "docker build" in smoke_script
    assert "/health" in smoke_script
    assert "/-/ready" in smoke_script
    assert "/api/v2/missions" in smoke_script
    assert "http://mission-planner/api/v2/missions" in smoke_script


def test_local_developer_compose_contract_remains_separate() -> None:
    local_compose = LOCAL_COMPOSE_PATH.read_text(encoding="utf-8")

    assert "context: ./backend/starlink-location/" in local_compose
    assert "env_file: .env" in local_compose
    assert "container_name: starlink-location" in local_compose


def test_backend_compose_healthchecks_allow_observed_cold_start() -> None:
    expected_healthcheck = """    healthcheck:
      test: [\"CMD\", \"curl\", \"-f\", \"http://localhost:8000/health\"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 90s"""

    for compose_path in (LOCAL_COMPOSE_PATH, DEPLOY_COMPOSE_PATH):
        assert expected_healthcheck in compose_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "filename", ["portainer-ghcr-compose.yml", "portainer-forge-dev-compose.yml"]
)
def test_deployment_has_private_worker_with_same_tag_and_shared_state(
    tmp_path: Path, filename: str
):
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    env.update(
        STARLINK_IMAGE_TAG="sha-" + "a" * 40,
        STARLINK_APP_DATA_PATH=str(tmp_path / "app"),
        STARLINK_ROUTE_DATA_PATH=str(tmp_path / "routes"),
        STARLINK_PROMETHEUS_DATA_PATH=str(tmp_path / "prometheus"),
        STARLINK_BIND_IP="127.0.0.1",
    )
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(REPO_ROOT / "deployment" / filename),
            "config",
            "--format",
            "json",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    config = json.loads(result.stdout)
    services = config["services"]
    worker = services["gfs-worker"]
    api = services["starlink-location"]
    assert (
        worker["image"]
        == "ghcr.io/bcl1713/starlink-dashboard/gfs-worker:sha-" + "a" * 40
    )
    assert (
        not worker.get("profiles") and "build" not in worker and "ports" not in worker
    )
    assert set(worker["networks"]) == {"starlink-net"}
    assert worker["restart"] == "no" and worker["user"] == "1000:1000"
    assert worker["cpus"] == 1.0 and int(worker["mem_limit"]) == 1024**3
    assert worker["init"] and worker["stop_grace_period"] == "15s"
    api_mounts = {v["target"]: v for v in api["volumes"]}
    worker_mounts = {v["target"]: v for v in worker["volumes"]}
    for path in ("/app/data/gfs", "/app/data/gfs-mailbox"):
        assert api_mounts[path]["type"] == worker_mounts[path]["type"] == "volume"
        assert api_mounts[path]["source"] == worker_mounts[path]["source"]
        assert (
            api["environment"][
                "GFS_ARTIFACT_PATH" if path.endswith("/gfs") else "GFS_MAILBOX_PATH"
            ]
            == path
        )
        assert (
            worker["environment"][
                "GFS_ARTIFACT_PATH" if path.endswith("/gfs") else "GFS_MAILBOX_PATH"
            ]
            == path
        )
    assert api_mounts["/app/data/gfs"]["read_only"]
    settings = worker_mounts["/app/data/settings"]
    assert settings["read_only"] and settings["source"] == str(
        tmp_path / "app/settings"
    )
    assert (
        worker["environment"]["AVIATION_SETTINGS_PATH"]
        == "/app/data/settings/aviation-weather.json"
    )
    assert {v["source"] for v in worker["volumes"] if v["type"] == "volume"} == set(
        config["volumes"]
    )


def test_smoke_builds_worker_and_removes_its_disposable_volumes(tmp_path: Path):
    sha = "a" * 40
    result, calls = run_smoke_with_command_doubles(tmp_path, sha)
    assert result.returncode == 0, result.stderr
    worker_builds = [
        c
        for c in calls
        if c[0] == "build"
        and "--file" in c
        and c[c.index("--file") + 1].endswith("Dockerfile.gfs")
    ]
    assert len(worker_builds) == 1
    build = worker_builds[0]
    assert build[build.index("--build-arg") + 1] == "ACCEPTANCE_CANDIDATE_SHA=" + sha
    assert (
        build[build.index("--tag") + 1]
        == "ghcr.io/bcl1713/starlink-dashboard/gfs-worker:sha-" + sha
    )
    teardown = next(c for c in calls if c[0] == "compose" and "down" in c)
    assert "--volumes" in teardown


def test_smoke_rejects_missing_worker_heartbeat(tmp_path: Path):
    result, calls = run_smoke_with_command_doubles(tmp_path, "a" * 40, worker_status=1)
    assert result.returncode != 0
    probes = [c for c in calls if "exec" in c and any("GfsMailbox" in arg for arg in c)]
    assert probes
    assert len(probes) <= 15
    assert any("down" in c and "--volumes" in c for c in calls)
