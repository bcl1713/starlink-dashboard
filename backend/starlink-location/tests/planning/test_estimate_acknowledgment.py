"""Best-estimate planning results do not require a disclaimer acknowledgment."""

from types import SimpleNamespace

from app.mission.planning.review import validate_review

from . import test_reviewed_save

prepared = test_reviewed_save.prepared
service = test_reviewed_save.service


def test_outages_and_backup_gaps_do_not_require_acknowledgment(prepared):
    planner, view = test_reviewed_save.confirmed(prepared)
    request = test_reviewed_save.review(planner, view, gap_acknowledged=False)
    validate_review(
        view.expected_legs[0].leg,
        request,
        SimpleNamespace(errors=[], outage_seconds=120, backup_gaps=[object()]),
    )
