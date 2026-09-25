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
        "observed utc build start/end timestamps",
        "monotonic elapsed duration",
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


def test_platform_doc_prescribes_ordered_final_browser_recovery_workflow() -> None:
    guide = " ".join(PLATFORM_DOC.read_text(encoding="utf-8").split())

    health = (
        "Run `health` and checksum-verify its sealed fingerprint and evidence manifest."
    )
    static = "Run `static` only after that health validation succeeds."
    final = (
        "Issue `final` through one tracked runner process with a 1800-second "
        "monitored budget and durable stdout and stderr capture."
    )
    runner_ownership = (
        "The runner, not a caller, owns the headed Xvfb and loopback CDP browser "
        "resources, its task-owned profile, and pre-journey native display/card metrics."
    )
    diagnostics = (
        "On failure, inspect the runner's sealed diagnostic logs at "
        "`adapter.stdout.log` and `adapter.stderr.log` in the final evidence root."
    )
    recovery = (
        "After an interruption, inspect the final build ledger, inspected image "
        "identities, and task-owned resources."
    )
    authorization = "obtain explicit authorization from a human operator before one recovery attempt."
    cleanup = "Verify runner cleanup after the attempt without deleting volumes."

    for required in (
        health,
        static,
        final,
        runner_ownership,
        diagnostics,
        recovery,
        authorization,
        cleanup,
        "The tracked runner is the only final-browser operational authority.",
        "Callers must not hand-launch a headless browser as final acceptance evidence.",
    ):
        assert required in guide

    assert (
        guide.index(health)
        < guide.index(static)
        < guide.index(final)
        < guide.index(runner_ownership)
        < guide.index(diagnostics)
        < guide.index(recovery)
        < guide.index(authorization)
        < guide.index(cleanup)
    )


def test_platform_doc_defines_bounded_startup_and_interrupt_cleanup() -> None:
    guide = " ".join(PLATFORM_DOC.read_text(encoding="utf-8").split())

    assert (
        "fixed 120-second deadline for `docker compose up -d --no-build --wait`"
        in guide
    )
    assert "retains Compose output and classifies startup as failed" in guide
    assert "classifies `SIGINT` and `SIGTERM` as final-run failures" in guide
    assert "drains Compose resources, browser/Xvfb processes and listeners" in guide
    assert "task browser profile, and the generated task root" in guide


def test_platform_doc_defines_content_aware_final_build_supervision() -> None:
    guide = " ".join(PLATFORM_DOC.read_text(encoding="utf-8").split())

    for required in (
        "lockfile inputs are unchanged",
        "exact candidate SHA after dependency installation",
        "`--pull`",
        "600 seconds without meaningful BuildKit progress",
        "1800-second total deadline",
        "`build_stalled`",
        "`build_deadline_exceeded`",
        "neither outcome authorizes automatic retry",
        "fresh health/static and operator approval",
        "never reaches no-build startup or final authority",
    ):
        assert required in guide
    assert "--no-cache" not in guide


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


def test_v2_documentation_separates_route_relative_poi_eligibility_from_eta_timing() -> None:
    text = " ".join(V2_DOC.read_text(encoding="utf-8").split())

    assert "Upcoming POI visibility derives from active-route position" in text
    assert "separate visible body rows for `KAAA` and `KBBB`" in text
    assert "ETA remains anticipated/estimated metadata" in text
    assert (
        "Before planned departure, anticipated ETA is calendar-based. After a missed "
        "planned departure but before actual departure, planned route durations are "
        "re-anchored at now. Once in flight, ETA is estimated from the current route "
        "position; POI visibility remains route-relative."
    ) in text


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
