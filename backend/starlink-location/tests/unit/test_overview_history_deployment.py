from pathlib import Path


def test_docker_compose_persists_overview_history_settings():
    repository_root = Path(__file__).resolve().parents[4]
    compose = (repository_root / "docker-compose.yml").read_text()
    assert "- ./data/settings:/app/data/settings" in compose
