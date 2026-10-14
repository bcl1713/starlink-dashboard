"""Final map review uses the same customer overview eligibility and diagnoses."""

from dataclasses import replace

import pytest

from tests.unit.test_map_real_input_boundaries import boundary

from . import test_proposals
from .test_reviewed_save import confirmed, review, snapshot

prepared = test_proposals.prepared
service = test_proposals.service


def test_map_review_reports_actionable_unsupported_input():
    from app.mission.planning import map_review

    captured, projected, _ = boundary("map-density-two")
    errors = map_review.check_map_review(
        replace(captured, effective_route_json=None), projected
    )
    assert errors[0].code == "map_route_missing"
    assert errors[0].action and errors[0].field == "route"


@pytest.mark.parametrize("name", ["map-density-one", "map-density-three"])
def test_dense_overview_is_supported_in_final_review(name):
    from app.mission.planning import map_review

    captured, projected, _ = boundary(name)
    assert map_review.check_map_review(captured, projected) == ()


def test_preview_reports_map_limit_before_publication(prepared, monkeypatch):
    from app.mission.planning import map_review
    from app.mission.planning.models import PlanningError, PreviewDraft

    service, view = prepared
    problem = PlanningError(
        code="map_route_point_limit",
        message="Review route sampling",
        field="route",
        action="Import a supported route",
    )
    monkeypatch.setattr(map_review, "check_map_review", lambda *args: (problem,))
    result = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft(
            expected_revision=view.revision, draft=view.expected_legs[0].leg.draft
        ),
    )
    assert getattr(result, "map_diagnostics", None) == [problem]


def test_unsupported_map_cannot_silently_publish(prepared, monkeypatch):
    from app.mission.planning import map_review
    from app.mission.planning.errors import PlanningFailure
    from app.mission.planning.models import PlanningError

    service, view = confirmed(prepared)
    problem = PlanningError(
        code="map_route_point_limit",
        message="Review route sampling",
        field="route",
        action="Import a supported route",
    )
    monkeypatch.setattr(map_review, "check_map_review", lambda *args: (problem,))
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.save_reviewed(view.mission.id, "card-1", review(service, view))
    assert error.value.status_code == 422
    assert error.value.error.code == problem.code
    assert snapshot(service) == before
