from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
EXPECTED_INSTALL = (
    "GF_INSTALL_PLUGINS="
    "grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1"
)


def test_grafana_synchronously_installs_pinned_infinity_datasource() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert EXPECTED_INSTALL in compose
    assert "GF_PLUGINS_PREINSTALL" not in compose
