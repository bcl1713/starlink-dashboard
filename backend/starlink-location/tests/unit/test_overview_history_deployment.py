from pathlib import Path


def test_docker_compose_persists_overview_history_settings():
    repository_root = Path(__file__).resolve().parents[4]
    compose = (repository_root / "docker-compose.yml").read_text()
    assert "- ./data/settings:/app/data/settings" in compose


def test_entrypoint_grants_the_app_user_access_to_overview_history_settings():
    repository_root = Path(__file__).resolve().parents[4]
    entrypoint = (
        repository_root / "backend/starlink-location/entrypoint.sh"
    ).read_text()
    assert "  /app/data/settings \\\n" in entrypoint


def test_operator_docs_explain_overview_history_configuration():
    repository_root = Path(__file__).resolve().parents[4]
    environment_example = (repository_root / ".env.example").read_text()
    portainer_runbook = (
        repository_root / "docs/deployment/portainer-ghcr.md"
    ).read_text()
    assert "STARLINK_PROMETHEUS_URL=http://prometheus:9090" in environment_example
    assert "STARLINK_HISTORY_WINDOW_SECONDS=1800" in environment_example
    assert "persisted dashboard selection" in environment_example
    assert "STARLINK_HISTORY_WINDOW_SECONDS" in portainer_runbook
    assert "overview-history.json" in portainer_runbook
