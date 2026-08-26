from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOY_COMPOSE_PATH = REPO_ROOT / "deployment" / "portainer-ghcr-compose.yml"
LOCAL_COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
PUBLISH_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish-ghcr.yml"
SMOKE_SCRIPT_PATH = REPO_ROOT / "tools" / "smoke-portainer-profile.sh"


def test_portainer_profile_uses_ghcr_images_and_external_proxy_network() -> None:
    compose = DEPLOY_COMPOSE_PATH.read_text(encoding="utf-8")

    assert "ghcr.io/bcl1713/starlink-dashboard/" in compose
    assert "build:" not in compose
    assert "proxy:" in compose
    assert "external: true" in compose


def test_portainer_profile_preserves_pins_and_release_validation() -> None:
    compose = DEPLOY_COMPOSE_PATH.read_text(encoding="utf-8")
    local_compose = LOCAL_COMPOSE_PATH.read_text(encoding="utf-8")
    workflow = PUBLISH_WORKFLOW_PATH.read_text(encoding="utf-8")
    smoke_script = SMOKE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "prom/prometheus:v3.5.0" in compose
    assert "grafana/grafana:12.0.2" in compose
    assert "../monitoring/prometheus/prometheus.yml" in compose
    assert "../monitoring/grafana/provisioning" in compose
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
    assert "exec -T grafana env" in smoke_script
    assert "GF_PLUGINS_PREINSTALL=grafana-clock-panel,yesoreyeram-infinity-datasource@3.11.1" in smoke_script
    assert "/health" in smoke_script
    assert "/-/ready" in smoke_script
    assert "/api/v2/missions" in smoke_script
