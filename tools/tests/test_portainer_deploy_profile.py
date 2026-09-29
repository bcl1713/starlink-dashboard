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
    tmp_path: Path, sha: str
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
        "if 'exec' in sys.argv and 'grafana' in sys.argv:\n"
        "    print('GF_INSTALL_PLUGINS=grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1')\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
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
        build = next(call for call in builds if call[-1] == str(REPO_ROOT / product))
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
        "grafana",
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
        "STARLINK_GRAFANA_DATA_PATH",
    ):
        assert f"${{{variable}:?Set" in compose
    assert "type: bind" in compose
    assert "../monitoring/" not in compose
    assert "ghcr.io/bcl1713/starlink-dashboard/prometheus:" in compose
    assert "ghcr.io/bcl1713/starlink-dashboard/grafana:" in compose
    assert "prom/prometheus:v3.5.0" in local_compose
    assert "grafana/grafana:12.0.2" in local_compose
    assert "prom/prometheus:latest" not in local_compose
    assert "grafana/grafana:latest" not in local_compose
    assert (
        "GF_INSTALL_PLUGINS: "
        "grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1" in compose
    )
    assert "GF_PLUGINS_PREINSTALL" not in compose
    assert "yesoreyeram-infinity-datasource 3.11.1" in compose
    assert "branches: [dev]" in workflow
    assert "type=sha,format=long,prefix=sha-" in workflow
    assert "org.opencontainers.image.source" in workflow
    assert "org.opencontainers.image.revision" in workflow
    assert "docker compose" in smoke_script
    assert "docker build" in smoke_script
    assert (
        "GF_INSTALL_PLUGINS=grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1"
        in smoke_script
    )
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
