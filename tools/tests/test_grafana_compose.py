import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
INFINITY_DATASOURCE_PATH = (
    REPO_ROOT
    / "monitoring"
    / "grafana"
    / "provisioning"
    / "datasources"
    / "infinity.yml"
)
DATASOURCE_PROVISIONING_DIR = INFINITY_DATASOURCE_PATH.parent
EXPECTED_INSTALL = (
    "GF_INSTALL_PLUGINS=" "grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1"
)


def test_grafana_synchronously_installs_pinned_infinity_datasource() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    environment = compose["services"]["grafana"]["environment"]

    install_entries = [
        entry for entry in environment if entry.split("=", 1)[0] == "GF_INSTALL_PLUGINS"
    ]
    assert install_entries == [EXPECTED_INSTALL]
    assert not any(
        entry.split("=", 1)[0] == "GF_PLUGINS_PREINSTALL" for entry in environment
    )


@pytest.mark.parametrize(
    "plugin_entry",
    [
        "      - GF_INSTALL_PLUGINS=grafana-clock-panel,yesoreyeram-infinity-datasource 3.11.1\n",
        (
            "      - GF_INSTALL_PLUGINS=grafana-clock-panel,yesoreyeram-infinity-datasource\n"
            "        3.11.1\n"
        ),
    ],
    ids=["single-line", "wrapped"],
)
def test_grafana_plugin_contract_is_independent_of_yaml_line_wrapping(
    plugin_entry: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(
        "services:\n"
        "  other:\n"
        "    environment:\n"
        "      - GF_PLUGINS_PREINSTALL=unrelated\n"
        "  grafana:\n"
        "    environment:\n"
        f"{plugin_entry}",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "COMPOSE_PATH", compose_path)

    test_grafana_synchronously_installs_pinned_infinity_datasource()


def test_grafana_rejects_conflicting_duplicate_plugin_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    compose_path = tmp_path / "docker-compose.yml"
    compose_path.write_text(
        "services:\n"
        "  grafana:\n"
        "    environment:\n"
        f"      - {EXPECTED_INSTALL}\n"
        "      - GF_INSTALL_PLUGINS=wrong\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys.modules[__name__], "COMPOSE_PATH", compose_path)

    with pytest.raises(AssertionError):
        test_grafana_synchronously_installs_pinned_infinity_datasource()


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
        assert not re.search(
            r"^\s*type:\s*jsonapi\s*(?:#.*)?$", datasource, re.MULTILINE
        ), provisioning_file
