"""Documentation contract for the Mission V2 retirement boundary."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MAINTAINED_MISSION_DOCS = (
    REPOSITORY_ROOT / "docs/api/endpoints/README.md",
    REPOSITORY_ROOT / "docs/api/endpoints/overview-upcoming-pois.md",
    REPOSITORY_ROOT / "docs/features/overview.md",
    REPOSITORY_ROOT / "docs/missions/README.md",
    REPOSITORY_ROOT / "docs/missions/sop/pre-flight.md",
    REPOSITORY_ROOT / "docs/comm-sop/in-flight-operations.md",
    REPOSITORY_ROOT / "docs/features/mission-planning.md",
    REPOSITORY_ROOT / "docs/troubleshooting/data-issues.md",
    REPOSITORY_ROOT / "docs/reports/analysis-reports/exporter/README.md",
    REPOSITORY_ROOT / "docs/development/release-policy.md",
)
OVERVIEW_STATES = {
    "available",
    "no_active_mission",
    "route_unavailable",
    "inconsistent_active_mission",
    "no_generated_pois",
    "no_upcoming_pois",
    "unavailable",
}


def test_maintained_mission_docs_do_not_publish_legacy_api_examples():
    for path in MAINTAINED_MISSION_DOCS:
        text = path.read_text()
        assert "curl -X POST http://localhost:8000/api/missions" not in text
        assert "/api/missions/active" not in text
        if "/api/missions" in text:
            normalized_text = " ".join(text.split())
            assert "removed" in normalized_text
            assert "returns 404" in normalized_text
            assert text.count("/api/missions") == 1


def test_overview_api_docs_enumerate_all_final_states():
    text = (REPOSITORY_ROOT / "docs/api/endpoints/overview-upcoming-pois.md").read_text()
    for state in OVERVIEW_STATES:
        assert f"`{state}`" in text


def test_mission_docs_publish_the_only_supported_activation_route():
    text = (REPOSITORY_ROOT / "docs/missions/README.md").read_text()
    assert "POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate" in text
