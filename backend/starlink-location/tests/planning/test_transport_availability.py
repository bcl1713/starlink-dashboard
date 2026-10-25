"""Transport eligibility is shared by planning and canonical timeline preparation."""

from datetime import timedelta
from types import SimpleNamespace

import pytest

from app.mission.availability import resolved_leg_availability
from app.mission.availability_models import AvailabilityChange, MissionAvailability
from app.mission.models import Mission, MissionLeg, MissionLegTimeline, TransportConfig
from app.mission.planning.evaluate import evaluate_context, timeline_segments
from app.mission.planning.grid import build_context
from app.mission.planning.inputs import (
    build_inputs,
    draft_to_mission_leg,
    input_identity,
)
from app.mission.planning.optimizer import optimize
from app.mission.planning.review import validate_review
from app.mission.pop_continuity import capabilities_from_timeline
from app.mission.timeline_preparation import prepare_mission_timeline
from app.satellites.catalog import SatelliteCatalog
from app.satellites.rules import ConstraintConfig
from app.services.pop.continuity import project_call_continuity
from tests.unit.test_pop_continuity import forecast

from .test_policy import START, scenario


def prepared(
    monkeypatch, defaults=None, history=(), seconds=120, empty=False, **draft_changes
):
    _, draft, _, _, manager, pois, card = scenario(monkeypatch, seconds=seconds)
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="owned",
        transports=TransportConfig(initial_x_satellite_id="SOUTH"),
    )
    mission = Mission(
        id="mission",
        name="Mission",
        legs=[leg],
        availability=MissionAvailability(
            revision=3, defaults=defaults or {}, history=history
        ),
    )
    snapshot = resolved_leg_availability(mission, leg)
    if empty:
        draft.permitted_satellite_ids = ()
        draft.initial_x_satellite_id = None
    for field, value in draft_changes.items():
        setattr(draft, field, value)
    inputs = build_inputs(
        card, draft, manager, pois, ConstraintConfig(), availability=snapshot
    )
    return inputs, draft, build_context(inputs, draft), manager, pois, snapshot


def test_unavailable_x_needs_no_satellites(monkeypatch):
    inputs, draft, context, manager, pois, snapshot = prepared(
        monkeypatch, {"X": False}, empty=True
    )
    monkeypatch.setattr(
        "app.mission.planning.evaluate.look_angles",
        lambda *a: pytest.fail("Unavailable X must not need geometry"),
    )
    evaluation = evaluate_context(inputs, draft, context)
    assert all(i.physical_x_state == "offline" for i in evaluation.intervals)
    proposal = optimize(inputs, draft, context)
    assert proposal.proposed_draft.swaps == []
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="leg")
    artifacts = prepare_mission_timeline(
        leg,
        manager,
        pois,
        discover_coverage=False,
        satellite_catalog=SatelliteCatalog(),
        availability=snapshot,
    )
    assert artifacts.planning_evaluation == evaluation


@pytest.mark.parametrize("managed", [False, True])
def test_availability_applies_to_legacy_and_managed_timelines(monkeypatch, managed):
    inputs, draft, context, manager, pois, snapshot = prepared(
        monkeypatch, {"X": False, "Ka": False, "Ku": False}, empty=True
    )
    leg = (
        draft_to_mission_leg(inputs, draft, context, leg_id="leg")
        if managed
        else MissionLeg(
            id="leg",
            name="Leg",
            route_id="owned",
            transports=TransportConfig(initial_x_satellite_id=""),
        )
    )
    artifacts = prepare_mission_timeline(
        leg, manager, pois, discover_coverage=False, availability=snapshot
    )
    assert all(
        s.x_state == s.ka_state == s.ku_state == "offline"
        for s in artifacts.timeline.segments
    )
    assert all(
        s.x == s.ka == s.starshield == "unavailable"
        for s in artifacts.call_capabilities.spans
    )
    assert (
        artifacts.timeline.call_continuity.planned_communications_outage_seconds == 120
    )


def test_failure_splits_interval_without_rewriting_past(monkeypatch):
    failure = START + timedelta(seconds=37)
    inputs, draft, context, *_ = prepared(
        monkeypatch,
        history=(
            AvailabilityChange(
                id="fail", transport="Ka", unavailable=True, effective_at=failure
            ),
        ),
    )
    assert failure in context.boundaries
    evaluation = evaluate_context(inputs, draft, context)
    assert all(
        i.physical_ka_state == ("available" if i.start_time < failure else "offline")
        for i in evaluation.intervals
    )
    original, *_ = prepared(monkeypatch)
    assert input_identity(inputs) != input_identity(original)


def test_disabled_starshield_releases_concurrency_only_x(monkeypatch):
    inputs, draft, context, *_ = prepared(monkeypatch, {"Ku": False})
    result = evaluate_context(inputs, draft, context)
    assert all(
        i.policy_x_state == "available" and i.policy_ku_state == "offline"
        for i in result.intervals
    )
    assert any("x_aft_cone" in i.raw_constraints for i in result.intervals)


@pytest.mark.parametrize("ka_available", [False, True])
def test_failed_x_cannot_protect_pop_window(monkeypatch, ka_available):
    inputs, draft, context, *_ = prepared(
        monkeypatch, {"X": False, "Ka": ka_available}, seconds=1200
    )
    timeline = MissionLegTimeline(
        mission_leg_id="leg",
        segments=timeline_segments(evaluate_context(inputs, draft, context), "leg"),
    )
    # Explicit failure must survive missing evidence fallback.
    timeline.statistics["_call_capability_evidence"] = {"x": False, "ka": ka_available}
    spans = capabilities_from_timeline(timeline)
    assert all(s.x == "unavailable" and not s.x_concurrency_only for s in spans)
    result = project_call_continuity(
        forecast(START + timedelta(minutes=10)),
        spans,
        start_utc=inputs.start_time,
        end_utc=inputs.end_time,
    )
    assert result.pop_call_outage_seconds == (0 if ka_available else 600)


def test_all_transports_unavailable_is_saveable(monkeypatch):
    inputs, draft, context, _, _, _ = prepared(
        monkeypatch, {"X": False, "Ka": False, "Ku": False}, empty=True
    )
    evaluation = evaluate_context(inputs, draft, context)
    draft.no_ars_confirmed = True
    card = SimpleNamespace(draft=draft, ar_rows=[], ar_section_status="empty")
    request = SimpleNamespace(
        satellite_plan_confirmed=False,
        confirmed_ar_ids=[],
        excluded_ar_ids=[],
        no_ars_confirmed=True,
    )
    validate_review(
        card,
        request,
        evaluation,
        availability=inputs.availability,
        start=inputs.start_time,
        end=inputs.end_time,
    )
    assert evaluation.errors == []


def test_x_failure_covering_half_open_leg_needs_no_geometry_at_arrival(monkeypatch):
    _, _, _, manager, pois, snapshot = prepared(
        monkeypatch,
        history=(
            AvailabilityChange(
                id="fail", transport="X", unavailable=True, effective_at=START
            ),
            AvailabilityChange(
                id="restore",
                transport="X",
                unavailable=False,
                effective_at=START + timedelta(seconds=120),
            ),
        ),
    )
    leg = MissionLeg(
        id="leg",
        name="Leg",
        route_id="owned",
        transports=TransportConfig(initial_x_satellite_id="retained-assignment"),
    )
    monkeypatch.setattr(
        "app.mission.timeline_builder.events._resolve_satellite_longitude",
        lambda *args: pytest.fail("Arrival belongs to the next half-open interval"),
    )
    artifacts = prepare_mission_timeline(
        leg, manager, pois, discover_coverage=False, availability=snapshot
    )
    assert all(s.x_state == "offline" for s in artifacts.timeline.segments)


def test_unavailable_x_keeps_inactive_lock_without_an_initial_selection(monkeypatch):
    from app.mission.planning.models import PlanningLock

    lock = PlanningLock(
        id="restore-later", kind="initial", target_satellite_id="retained-satellite"
    )
    inputs, draft, context, *_ = prepared(
        monkeypatch, {"X": False}, empty=True, locks=[lock]
    )
    result = evaluate_context(inputs, draft, context)
    proposal = optimize(inputs, draft, context)
    assert all(i.physical_x_state == "offline" for i in result.intervals)
    assert proposal.proposed_draft.initial_x_satellite_id is None
    assert proposal.proposed_draft.locks == [lock]
    assert proposal.proposed_draft.swaps == []


@pytest.mark.parametrize("replaced_before_restore", [False, True])
def test_swap_during_failure_is_validated_over_its_assignment_window(
    monkeypatch, replaced_before_restore
):
    from app.mission.planning.grid import validate_context
    from app.mission.planning.match import _candidates
    from app.mission.planning.models import AnchoredSwap
    from app.models.route import ParsedRoute

    inputs, draft, _, manager, pois, snapshot = prepared(
        monkeypatch,
        history=(
            AvailabilityChange(
                id="fail",
                transport="X",
                unavailable=True,
                effective_at=START + timedelta(seconds=20),
            ),
            AvailabilityChange(
                id="restore",
                transport="X",
                unavailable=False,
                effective_at=START + timedelta(seconds=80),
            ),
        ),
    )
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    draft.swaps = [
        AnchoredSwap(
            id="retained",
            target_satellite_id="MISSING",
            anchor=_candidates(START + timedelta(seconds=40), "second", route)[0],
        )
    ]
    if replaced_before_restore:
        draft.swaps.append(
            AnchoredSwap(
                id="usable",
                target_satellite_id="SOUTH",
                anchor=_candidates(START + timedelta(seconds=60), "second", route)[0],
            )
        )
    _, _, _, _, _, _, card = scenario(monkeypatch)
    inputs = build_inputs(
        card, draft, manager, pois, ConstraintConfig(), availability=snapshot
    )
    context = build_context(inputs, draft)
    if replaced_before_restore:
        result = evaluate_context(inputs, draft, context)
        assert result.intervals
        assert all(
            i.satellite_id == "SOUTH"
            for i in result.intervals
            if i.start_time >= START + timedelta(seconds=80)
        )
    else:
        with pytest.raises(ValueError, match="permitted position snapshot"):
            validate_context(inputs, draft, context)
