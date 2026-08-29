import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
INFINITY_DATASOURCE_PATH = (
    REPO_ROOT / "monitoring" / "grafana" / "provisioning" / "datasources" / "infinity.yml"
)
DATASOURCE_PROVISIONING_DIR = INFINITY_DATASOURCE_PATH.parent
EXPECTED_INSTALL = (
    "GF_INSTALL_PLUGINS="
    "grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1"
)


def test_grafana_synchronously_installs_pinned_infinity_datasource() -> None:
    compose = COMPOSE_PATH.read_text(encoding="utf-8")

    assert EXPECTED_INSTALL in compose
    assert "GF_PLUGINS_PREINSTALL" not in compose


def test_grafana_infinity_datasource_has_stable_proxy_uid() -> None:
    datasource = INFINITY_DATASOURCE_PATH.read_text(encoding="utf-8")

    assert "    uid: infinity" in datasource
    assert "    url: http://starlink-location:8000" in datasource
    assert "    access: proxy" in datasource


def test_grafana_does_not_provision_unsupported_jsonapi_datasources() -> None:
    provisioning_files = [
        *DATASOURCE_PROVISIONING_DIR.glob("*.yml"),
        *DATASOURCE_PROVISIONING_DIR.glob("*.yaml"),
    ]

    for provisioning_file in provisioning_files:
        datasource = provisioning_file.read_text(encoding="utf-8")
        assert not re.search(r"^\s*type:\s*jsonapi\s*(?:#.*)?$", datasource, re.MULTILINE), (
            provisioning_file
        )
