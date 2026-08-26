from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_COMPOSE_PATH = REPO_ROOT / "deployment" / "portainer-ghcr-compose.yml"
LOCAL_COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
PUBLISH_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish-ghcr.yml"
SMOKE_SCRIPT_PATH = REPO_ROOT / "tools" / "smoke-portainer-profile.sh"


def test_portainer_profile_uses_immutable_ghcr_images_and_stable_proxy_aliases() -> None:
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


def test_portainer_profile_uses_required_host_paths_and_packaged_monitoring_images() -> None:
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
    assert "yesoreyeram-infinity-datasource@3.11.1" in compose
    assert "branches: [dev]" in workflow
    assert "type=sha,format=long,prefix=sha-" in workflow
    assert "org.opencontainers.image.source" in workflow
    assert "org.opencontainers.image.revision" in workflow
    assert "docker compose" in smoke_script
    assert "docker build" in smoke_script
    assert "GF_PLUGINS_PREINSTALL=grafana-clock-panel,yesoreyeram-infinity-datasource@3.11.1" in smoke_script
    assert "/health" in smoke_script
    assert "/-/ready" in smoke_script
    assert "/api/v2/missions" in smoke_script
    assert "http://mission-planner/api/v2/missions" in smoke_script


def test_local_developer_compose_contract_remains_separate() -> None:
    local_compose = LOCAL_COMPOSE_PATH.read_text(encoding="utf-8")

    assert "build: ./backend/starlink-location/" in local_compose
    assert "env_file: .env" in local_compose
    assert "container_name: starlink-location" in local_compose
