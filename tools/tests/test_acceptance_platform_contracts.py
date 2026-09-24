import json
from pathlib import Path

import pytest
from acceptance.platform.contracts import load_product_contract
from acceptance.platform.model import RuntimeControl, StaticGroup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
V2_CONTRACT = PROJECT_ROOT / "tools/acceptance/contracts/v2-mission-retirement.toml"


def _write_contract(tmp_path: Path, *, extra: str = "") -> Path:
    path = tmp_path / "contract.toml"
    path.write_text(
        """name = 'example'
services = ['api']
journey_adapter = 'tools/acceptance/journeys/example.mjs'
assets = ['fixtures/example.kml']

[[static_groups]]
name = 'backend'
working_directory = 'backend/api'
commands = ['pytest -q']

[[controls]]
name = 'health'
path = '/health'
expected_status = 200
""" + extra,
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    "key",
    [
        "chrome_path",
        "timeout_seconds",
        "npm_command",
        "docker_command",
        "xvfb_display",
        "cdp_port",
        "evidence_root",
        "retry_count",
        "cleanup_command",
    ],
)
def test_contract_rejects_operational_authority(tmp_path: Path, key: str) -> None:
    path = _write_contract(tmp_path, extra=f"{key} = 'forbidden'\n")

    with pytest.raises(ValueError, match="platform-owned"):
        load_product_contract(path)


@pytest.mark.parametrize(
    "section",
    ["candidate", "browser", "runtime"],
)
def test_contract_rejects_unknown_top_level_sections(
    tmp_path: Path, section: str
) -> None:
    path = _write_contract(tmp_path, extra=f"[{section}]\nvalue = 'forbidden'\n")

    with pytest.raises(ValueError, match="unknown top-level"):
        load_product_contract(path)


@pytest.mark.parametrize(
    "command",
    [
        "npm ci",
        "npx playwright install",
        "pip install pytest",
        "python -m pip install pytest",
        "docker-compose up",
        "env CI=1 docker-compose up",
        "sh -c 'docker-compose up'",
        "black --check . && docker-compose up",
        "env CI=1 npm ci",
        "sh -c 'docker compose up'",
        "black --check . && npx playwright test",
    ],
)
def test_contract_rejects_package_manager_or_install_commands(
    tmp_path: Path, command: str
) -> None:
    path = _write_contract(tmp_path)
    path.write_text(
        path.read_text(encoding="utf-8").replace(
            "commands = ['pytest -q']", f"commands = [{json.dumps(command)}]"
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="platform-owned"):
        load_product_contract(path)


@pytest.mark.parametrize(
    "path_value",
    [
        "/outside/contract.mjs",
        "../escape.kml",
        "assets/../../escape.kml",
        r"C:\outside\route.kml",
        r"assets\..\outside.kml",
    ],
)
def test_contract_rejects_uncontained_repository_paths(
    tmp_path: Path, path_value: str
) -> None:
    path = _write_contract(tmp_path)
    text = path.read_text(encoding="utf-8").replace("fixtures/example.kml", path_value)
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="repository-relative"):
        load_product_contract(path)


def test_v2_contract_has_only_product_authority() -> None:
    contract = load_product_contract(V2_CONTRACT)

    assert contract.services == ("starlink-location", "mission-planner")
    assert contract.assets == (
        Path("docs/missions/acceptance-assets/v2-activation-route.kml"),
    )
    assert len(contract.static_groups) == 2
    assert all(isinstance(group, StaticGroup) for group in contract.static_groups)
    assert contract.static_groups[0].commands == (
        "black --check app tests",
        "ruff check app tests",
        ".venv/bin/python -m pytest -q",
    )
    assert len(contract.controls) == 5
    assert all(isinstance(control, RuntimeControl) for control in contract.controls)
    assert [
        (control.path, control.expected_status) for control in contract.controls
    ] == [
        ("/health", 200),
        ("/", 200),
        ("/api/missions", 404),
        ("/api/missions/test", 404),
        ("/api/v2/missions", 200),
    ]


def test_contract_checksum_is_derived_from_descriptor_safe_source_bytes(
    tmp_path: Path,
) -> None:
    path = _write_contract(tmp_path)
    contract = load_product_contract(path)

    assert (
        contract.checksum == __import__("hashlib").sha256(path.read_bytes()).hexdigest()
    )
    path.write_text(
        path.read_text(encoding="utf-8").replace("/health", "/ready"), encoding="utf-8"
    )

    assert load_product_contract(path).checksum != contract.checksum
