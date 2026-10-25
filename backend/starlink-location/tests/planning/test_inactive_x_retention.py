"""Inactive X configuration survives planning without requiring X-only anchors."""

import json

import pytest

from app.mission.models import AARWindow, XTransition
from app.mission.planning.inputs import build_inputs
from app.mission.planning.models import (
    AnchoredSwap,
    GenerateProposal,
    PlanningLock,
    PreviewDraft,
    SaveDraft,
    SaveReviewed,
)
from app.mission.planning.types import RouteAnchor

from . import test_transport_availability_parent as parent

service = parent.service
prepared = parent.prepared


def retained_draft(view, kind):
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    if kind == "unresolved":
        draft.unresolved_x_transitions = [
            XTransition(
                id="retained-unresolved",
                latitude=12,
                longitude=12,
                target_satellite_id="RETAINED-X",
            )
        ]
    else:
        anchor = RouteAnchor(
            route_id="retired-route",
            content_hash="f" * 64,
            segment_index=999,
            fraction=0,
            occurrence_id="old-occurrence",
            source_time=view.expected_legs[0].leg.departure_time,
            latitude=12,
            longitude=12,
        )
        draft.swaps = [
            AnchoredSwap(
                id="retained-swap", target_satellite_id="RETAINED-X", anchor=anchor
            )
        ]
        draft.locks = [
            PlanningLock(
                id="retained-lock",
                swap_id="retained-swap",
                target_satellite_id="RETAINED-X",
                anchor=anchor,
            )
        ]
    return draft


@pytest.mark.parametrize("kind", ["unresolved", "stale-anchor"])
def test_inactive_x_preview_generate_and_review_retain_configuration(prepared, kind):
    service, view = parent.disabled_parent(prepared)
    draft = retained_draft(view, kind)
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    assert view.expected_legs[0].errors == []
    evaluation = service.preview(
        view.mission.id,
        "card-1",
        PreviewDraft(expected_revision=view.revision, draft=draft),
    )
    assert evaluation.intervals
    assert all(i.physical_x_state == "offline" for i in evaluation.intervals)
    assert any(i.physical_ka_state == "available" for i in evaluation.intervals)
    assert any(i.physical_ku_state == "available" for i in evaluation.intervals)
    proposal = service.proposals.generate(
        view.mission.id,
        "card-1",
        GenerateProposal(
            expected_revision=view.revision,
            input_identity=view.expected_legs[0].input_identity,
        ),
    )
    assert proposal.retained_current_draft
    assert proposal.proposed_draft.swaps == draft.swaps
    assert proposal.proposed_draft.locks == draft.locks
    assert (
        proposal.proposed_draft.unresolved_x_transitions
        == draft.unresolved_x_transitions
    )
    published = service.save_reviewed(
        view.mission.id,
        "card-1",
        SaveReviewed(
            expected_revision=view.revision,
            input_identity=view.expected_legs[0].input_identity,
            evaluation_identity=evaluation.context.input_identity,
            satellite_plan_confirmed=False,
            no_ars_confirmed=True,
        ),
    )
    saved = published.expected_legs[0].leg.draft
    assert saved.swaps == draft.swaps
    assert saved.locks == draft.locks
    assert saved.unresolved_x_transitions == draft.unresolved_x_transitions
    installed = published.mission.legs[0]
    assert installed.transports.planning_inputs.satellites == ()
    structural = json.loads(installed.transports.planning_inputs.structural_draft_json)
    assert structural["locks"] == [x.model_dump(mode="json") for x in draft.locks]
    assert structural["unresolved_x_transitions"] == [
        x.model_dump(mode="json") for x in draft.unresolved_x_transitions
    ]
    assert [x.anchor for x in installed.transports.x_transitions] == [
        x.anchor for x in draft.swaps
    ]
    # Restoring eligibility requires resolution of the retained X configuration.
    leg = published.expected_legs[0].leg
    from app.mission.availability_context import expected_snapshot

    availability = expected_snapshot(published.mission, leg).model_copy(
        update={"planned": (("X", True), ("Ka", True), ("Ku", True))}
    )
    with pytest.raises(ValueError):
        inputs = build_inputs(
            leg,
            saved,
            service.store.route_manager,
            service.store.poi_manager,
            service.store.planning_constraints_provider(),
            availability=availability,
        )
        from app.mission.planning.grid import build_context

        build_context(inputs, saved)


def test_disabled_x_keeps_unresolved_ar_and_route_validation(prepared):
    service, view = parent.disabled_parent(prepared)
    leg = view.expected_legs[0].leg
    draft = retained_draft(view, "unresolved")
    draft.unresolved_aar_windows = [
        AARWindow(id="unresolved-ar", start_waypoint_name="A", end_waypoint_name="B")
    ]
    with pytest.raises(ValueError, match="AR"):
        build_inputs(
            leg,
            draft,
            service.store.route_manager,
            service.store.poi_manager,
            service.store.planning_constraints_provider(),
        )
    draft.unresolved_aar_windows = []
    leg.route = None
    with pytest.raises(ValueError, match="bound route"):
        build_inputs(
            leg,
            draft,
            service.store.route_manager,
            service.store.poi_manager,
            service.store.planning_constraints_provider(),
        )


def test_partially_available_x_still_requires_retained_transition_resolution(prepared):
    from app.mission.availability_context import expected_snapshot
    from app.mission.availability_models import FailureWindow, Transport
    from app.mission.timeline_builder.calculator import derive_mission_window

    service, view = prepared
    leg = view.expected_legs[0].leg
    draft = retained_draft(view, "unresolved")
    route = service.store.route_manager.get_route(leg.route.route_id)
    start, end = derive_mission_window(route)
    availability = expected_snapshot(view.mission, leg).model_copy(
        update={
            "failures": (
                FailureWindow(
                    transport=Transport.X, start=start, end=start + (end - start) / 2
                ),
            )
        }
    )
    with pytest.raises(ValueError, match="legacy X"):
        build_inputs(
            leg,
            draft,
            service.store.route_manager,
            service.store.poi_manager,
            service.store.planning_constraints_provider(),
            availability=availability,
        )
