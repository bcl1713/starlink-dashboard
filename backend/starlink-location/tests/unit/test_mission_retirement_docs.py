"""Documentation contract for the Mission V2 retirement boundary."""

import re
import sys
from pathlib import Path

import pytest


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
LEGACY_MISSION_PATH = re.compile(r"/api/missions(?:\b|/)")
LEGACY_REMOVAL_NOTICE = re.compile(
    r"`/api/missions` has been removed and now returns 404(?:[.;])"
)
ACTIVATION_POST = re.compile(
    r"POST\s+/api/v2/missions(?:/[A-Za-z0-9_{}-]+)*/activate\b"
)
SUPPORTED_ACTIVATION_POST = "POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate"


def _assert_legacy_mission_paths_are_removal_notices(text):
    normalized_text = " ".join(text.split())
    legacy_path_count = len(LEGACY_MISSION_PATH.findall(normalized_text))
    removal_notice_count = len(LEGACY_REMOVAL_NOTICE.findall(normalized_text))
    assert legacy_path_count == removal_notice_count


def test_maintained_mission_docs_do_not_publish_legacy_api_examples():
    for path in MAINTAINED_MISSION_DOCS:
        _assert_legacy_mission_paths_are_removal_notices(path.read_text())


def test_overview_api_docs_enumerate_all_final_states():
    text = (REPOSITORY_ROOT / "docs/api/endpoints/overview-upcoming-pois.md").read_text()
    for state in OVERVIEW_STATES:
        assert f"`{state}`" in text


def test_mission_docs_publish_the_only_supported_activation_route():
    activation_posts = [
        activation_post
        for path in MAINTAINED_MISSION_DOCS
        for activation_post in ACTIVATION_POST.findall(path.read_text())
    ]
    assert activation_posts
    assert set(activation_posts) == {SUPPORTED_ACTIVATION_POST}


@pytest.mark.parametrize(
    "legacy_path",
    (
        "/api/missions",
        "/api/missions/{mission_id}/legs/{leg_id}",
    ),
)
def test_legacy_removal_notice_does_not_allow_runnable_legacy_examples(
    tmp_path, monkeypatch, legacy_path
):
    document = tmp_path / "mission.md"
    document.write_text(
        "The legacy endpoint was removed and now returns 404.\n"
        "```bash\n"
        f"curl -X GET http://localhost:8000{legacy_path}\n"
        "```\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "MAINTAINED_MISSION_DOCS", (document,))

    with pytest.raises(AssertionError):
        test_maintained_mission_docs_do_not_publish_legacy_api_examples()


def test_activation_contract_rejects_an_alternative_v2_activation_post(
    tmp_path, monkeypatch
):
    mission_readme = tmp_path / "docs/missions/README.md"
    mission_readme.parent.mkdir(parents=True)
    mission_readme.write_text(
        "POST /api/v2/missions/{mission_id}/legs/{leg_id}/activate\n"
        "POST /api/v2/missions/{mission_id}/activate\n"
    )
    monkeypatch.setattr(sys.modules[__name__], "MAINTAINED_MISSION_DOCS", (mission_readme,))

    with pytest.raises(AssertionError):
        test_mission_docs_publish_the_only_supported_activation_route()
