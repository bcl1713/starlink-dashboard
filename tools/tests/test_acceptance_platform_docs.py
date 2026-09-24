from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DOC = PROJECT_ROOT / "docs/operations/acceptance-platform.md"
V2_DOC = PROJECT_ROOT / "docs/missions/v2-mission-retirement-acceptance.md"
MISSION_INDEX = PROJECT_ROOT / "docs/missions/README.md"


def test_platform_doc_requires_health_fingerprint() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")

    assert "health fingerprint" in text.lower()
    assert "environment_blocked" in text
    assert "one-build" in text.lower()
    assert "cached diagnostics" in text.lower()
    assert "final fresh-image evidence" in text.lower()
    assert "npm ci" not in text


def test_v2_doc_names_product_journey_not_browser_settings() -> None:
    text = V2_DOC.read_text(encoding="utf-8")

    assert "Create New Mission" in text
    assert "v2-activation-route.kml" in text
    assert "starlink-location" in text
    assert "mission-planner" in text
    assert "--remote-debugging-port" not in text
    assert "npm ci" not in text
    assert "Docker" not in text
    assert "Xvfb" not in text


def test_mission_index_links_v2_acceptance_contract() -> None:
    assert "v2-mission-retirement-acceptance.md" in MISSION_INDEX.read_text(
        encoding="utf-8"
    )
