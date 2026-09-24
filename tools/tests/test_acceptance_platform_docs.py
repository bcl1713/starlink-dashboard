import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PLATFORM_DOC = PROJECT_ROOT / "docs/operations/acceptance-platform.md"
V2_DOC = PROJECT_ROOT / "docs/missions/v2-mission-retirement-acceptance.md"
MISSION_INDEX = PROJECT_ROOT / "docs/missions/README.md"
V2_CONTRACT = PROJECT_ROOT / "tools/acceptance/contracts/v2-mission-retirement.toml"


def _relative_markdown_targets(path: Path) -> list[Path]:
    links = re.findall(r"\[[^]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8"))
    targets = []
    for link in links:
        target = link.split("#", maxsplit=1)[0]
        if target and not "://" in target:
            targets.append((path.parent / target).resolve())
    return targets


def test_platform_doc_defines_administrative_browser_authority() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for required in (
        "absolute executable path",
        "revision",
        "bundle identifier",
        "creation time",
        "platform-owned browser-store path",
        "package/runtime provenance",
        "verified before launch",
    ):
        assert required in lowered
    for prohibited in ("`npm`", "`npx`", "playwright installer", "inherited `path`"):
        assert prohibited in lowered


def test_platform_doc_defines_complete_health_fingerprint_validation() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    assert "health fingerprint" in lowered
    assert "environment_blocked" in text
    for required in (
        "docker identity",
        "compose identity",
        "capture timestamp",
        "re-verifies the health card",
        "evidence manifest",
    ):
        assert required in lowered


def test_platform_doc_requires_cleanup_before_sealed_public_authority() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")

    staged = text.index("Stage evidence privately")
    cleaned = text.index("Clean task-owned resources and verify cleanup")
    reverified = text.index("Re-verify staged evidence and checksums after cleanup")
    published = text.index("Seal and atomically publish final authority")
    assert staged < cleaned < reverified < published
    assert "discoverable final authority" in text.lower()


def test_platform_doc_defines_restrictive_candidate_provenance() -> None:
    text = PLATFORM_DOC.read_text(encoding="utf-8")
    lowered = " ".join(text.lower().split())

    for required in (
        "candidate sha and ref",
        "lane",
        "profile and contract checksums",
        "health fingerprint",
        "browser identity",
        "journey-adapter checksum",
        "capture start and end timestamps",
        "controls",
        "journey observations",
        "image identity",
        "primary result",
        "cleanup result",
        "maximum evidence claim",
        "0700",
        "0600",
        "sha-qualified root",
    ):
        assert required in lowered


def test_platform_doc_prescribes_final_browser_recovery_workflow() -> None:
    guide = PLATFORM_DOC.read_text(encoding="utf-8")

    for required in (
        "headed Xvfb",
        "900-second",
        "adapter.stdout.log",
        "adapter.stderr.log",
        "explicit authorization",
        "final build ledger",
    ):
        assert required in guide

    lowered = " ".join(guide.lower().split())
    assert "callers must not hand-launch a headless browser" in lowered
    assert "without deleting volumes" in lowered


def test_v2_doc_is_product_only() -> None:
    text = V2_DOC.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "Create New Mission" in text
    assert "v2-activation-route.kml" in text
    assert "starlink-location" in text
    assert "mission-planner" in text
    for excluded in (
        "chrome",
        "chromium",
        "docker",
        "compose",
        "xvfb",
        "cdp",
        "playwright",
        "npm",
        "npx",
        "inherited `path`",
        "timeout",
        "remote-debugging",
    ):
        assert excluded not in lowered


def test_platform_and_v2_document_links_and_kml_asset_resolve() -> None:
    for document in (PLATFORM_DOC, V2_DOC, MISSION_INDEX):
        for target in _relative_markdown_targets(document):
            assert target.is_file(), f"broken link in {document}: {target}"

    contract_text = V2_CONTRACT.read_text(encoding="utf-8")
    asset_match = re.search(r'^assets = \["([^"]+)"\]$', contract_text, re.MULTILINE)
    assert asset_match is not None
    asset = PROJECT_ROOT / asset_match.group(1)
    assert asset.is_file()
    assert asset.name == "v2-activation-route.kml"
    assert asset.resolve() in _relative_markdown_targets(V2_DOC)


def test_mission_index_links_v2_acceptance_contract() -> None:
    assert V2_DOC.resolve() in _relative_markdown_targets(MISSION_INDEX)
