"""Exact schedule optimum measured against exhaustive canonical preparation."""

import importlib.util
import json

import pytest

from app.mission.planning.grid import build_context
from app.mission.planning.inputs import structural_draft
from app.mission.planning.models import AccessConfirmation, PlanningLock

from .cases import canonical_evaluation, exhaustive_schedules, schedule_key, timed_swap
from .test_policy import scenario


def optimizer():
    assert importlib.util.find_spec(
        "app.mission.planning.optimizer"
    ), "Exact optimizer is missing"
    from app.mission.planning.optimizer import optimize

    return optimize


def configured(monkeypatch, seconds=180, buffer=0.25, **changes):
    inputs, draft, _, *_ = scenario(monkeypatch, seconds=seconds, **changes)
    draft.access_confirmation = AccessConfirmation(
        satellite_ids=draft.permitted_satellite_ids, confirmed=True
    )
    config = json.loads(inputs.constraints_json)
    config["transition_buffer_minutes"] = buffer
    inputs = inputs.model_copy(update={"constraints_json": json.dumps(config)})
    return inputs, draft


def context_for(inputs, draft):
    inputs = inputs.model_copy(
        update={
            "structural_draft_json": json.dumps(
                structural_draft(draft), default=lambda v: v.isoformat()
            )
        }
    )
    return inputs, build_context(inputs, draft)


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("lock_case", ["none", "initial", "swap", "overlap"])
def test_exact_score_equals_all_small_canonical_schedules(
    monkeypatch, enabled, lock_case
):
    optimize = optimizer()
    inputs, draft = configured(monkeypatch, starshield_enabled=enabled)
    if lock_case == "initial":
        draft.locks = [
            PlanningLock(id="initial", kind="initial", target_satellite_id="SOUTH")
        ]
    elif lock_case in ("swap", "overlap"):
        draft.swaps = [timed_swap(inputs, 60, "SOUTH")]
        if lock_case == "overlap":
            draft.swaps.append(timed_swap(inputs, 70, "WEST"))
        draft.locks = [
            PlanningLock(
                id=s.id,
                swap_id=s.id,
                target_satellite_id=s.target_satellite_id,
                anchor=s.anchor,
            )
            for s in draft.swaps
        ]
    inputs, context = context_for(inputs, draft)
    scores = []
    for candidate in exhaustive_schedules(inputs, draft, context):
        result = canonical_evaluation(inputs, candidate, context)
        scores.append(
            (result.outage_seconds, result.swap_count, schedule_key(inputs, candidate))
        )
    result = optimize(inputs, draft, context)
    candidate = result.proposed_draft
    score = (
        result.candidate_evaluation.outage_seconds,
        result.candidate_evaluation.swap_count,
        schedule_key(inputs, candidate),
    )
    assert score == min(scores)
    assert (
        result.candidate_evaluation.outage_seconds
        <= result.baseline_evaluation.outage_seconds
    )
    assert candidate.locks == draft.locks
    assert optimize(inputs, draft, context).proposed_draft == candidate
    assert (
        canonical_evaluation(inputs, candidate, context) == result.candidate_evaluation
    )


def test_full_buffer_erases_short_benefit_and_no_initial_uses_best_constant(
    monkeypatch,
):
    optimize = optimizer()
    inputs, draft = configured(monkeypatch, seconds=180, buffer=15)
    draft.initial_x_satellite_id = None
    inputs, context = context_for(inputs, draft)
    result = optimize(inputs, draft, context)
    assert result.proposed_draft.initial_x_satellite_id in draft.permitted_satellite_ids
    assert result.proposed_draft.swaps == []
    assert (
        result.baseline_evaluation.outage_seconds
        == result.candidate_evaluation.outage_seconds
    )


def test_unconfirmed_or_ineligible_and_infeasible_lock_do_not_mutate(monkeypatch):
    optimize = optimizer()
    inputs, draft = configured(monkeypatch)
    inputs, context = context_for(inputs, draft)
    before = draft.model_dump_json()
    draft.access_confirmation = None
    with pytest.raises(ValueError, match="access"):
        optimize(inputs, draft, context)
    draft.access_confirmation = AccessConfirmation(
        satellite_ids=draft.permitted_satellite_ids, confirmed=True
    )
    draft.locks = [
        PlanningLock(id="bad", kind="initial", target_satellite_id="EXCLUDED")
    ]
    inputs, context = context_for(inputs, draft)
    bad = draft.model_dump_json()
    with pytest.raises(ValueError, match="permitted|lock"):
        optimize(inputs, draft, context)
    assert draft.model_dump_json() == bad
    assert before != bad


def test_generated_buffer_can_overlap_locked_union_and_win(monkeypatch):
    inputs, draft = configured(monkeypatch, seconds=180, buffer=0.5)
    locked = timed_swap(inputs, 60, "SOUTH")
    draft.swaps = [locked, timed_swap(inputs, 75, "WEST")]
    draft.locks = [
        PlanningLock(
            id="lock",
            swap_id=locked.id,
            target_satellite_id="SOUTH",
            anchor=locked.anchor,
        )
    ]
    inputs, context = context_for(inputs, draft)
    result = optimizer()(inputs, draft, context)
    expected = []
    for candidate in exhaustive_schedules(inputs, draft, context):
        value = canonical_evaluation(inputs, candidate, context)
        expected.append(
            (value.outage_seconds, value.swap_count, schedule_key(inputs, candidate))
        )
    score = (
        result.candidate_evaluation.outage_seconds,
        result.candidate_evaluation.swap_count,
        schedule_key(inputs, result.proposed_draft),
    )
    assert score == min(expected)
    assert result.candidate_evaluation.outage_seconds == 75
    assert len(result.proposed_draft.swaps) == 2
    assert result.proposed_draft.swaps[0] == locked


def test_cancellation_and_shutdown_terminate_reap_workers(tmp_path):
    import multiprocessing
    import threading

    from app.mission.planning import deadlines

    from .test_deadlines import _slow_started

    before = {p.pid for p in multiprocessing.active_children()}
    cancel = threading.Event()
    timer = threading.Timer(0.8, cancel.set)
    timer.start()
    try:
        with pytest.raises(deadlines.PlanningWorkerError, match="cancel"):
            deadlines.run_bounded(
                _slow_started, (str(tmp_path / "cancel"),), 30, cancel_event=cancel
            )
    finally:
        timer.cancel()
        timer.join()
    assert {p.pid for p in multiprocessing.active_children()} == before
    timer = threading.Timer(0.8, deadlines.shutdown_workers)
    timer.start()
    try:
        with pytest.raises(deadlines.PlanningWorkerError, match="cancel|shutdown"):
            deadlines.run_bounded(_slow_started, (str(tmp_path / "shutdown"),), 30)
    finally:
        timer.cancel()
        timer.join()
        deadlines.start_workers()
    assert {p.pid for p in multiprocessing.active_children()} == before


def test_same_instant_incompatible_locks_rejected_without_mutation(monkeypatch):
    inputs, draft = configured(monkeypatch)
    first = timed_swap(inputs, 60, "SOUTH")
    a = PlanningLock(id="a", anchor=first.anchor, target_satellite_id="SOUTH")
    b = PlanningLock(id="b", anchor=first.anchor, target_satellite_id="WEST")
    before = draft.model_dump_json()
    with pytest.raises(ValueError, match="Conflicting"):
        type(draft).model_validate({**draft.model_dump(), "locks": [a, b]})
    assert draft.model_dump_json() == before


@pytest.mark.parametrize(
    "enabled,locked", [(True, False), (True, True), (False, False)]
)
def test_alternating_real_geometry_requires_complete_pre_swap_buffer_cost(
    monkeypatch, enabled, locked
):
    from app.mission.planning.inputs import build_inputs
    from app.satellites.catalog import Satellite
    from app.satellites.rules import ConstraintConfig

    inputs, draft, _, _, manager, pois, leg = scenario(
        monkeypatch, seconds=180, starshield_enabled=enabled
    )
    route = manager.get_route("owned")
    original = route.points[0]
    from datetime import timedelta

    from .test_policy import START

    route.points = [
        original.model_copy(
            update={
                "sequence": i,
                "latitude": 10,
                "longitude": lon,
                "occurrence_id": f"p{i}",
                "expected_arrival_time": START + timedelta(seconds=60 * i),
            }
        )
        for i, lon in enumerate([0, 0.01, 0, 0.01])
    ]
    from app.satellites.catalog import get_satellite_catalog

    catalog = get_satellite_catalog(read_only=True)
    catalog.add_satellite(Satellite("EAST", "X", longitude=30))
    draft.permitted_satellite_ids = ("WEST", "EAST")
    draft.initial_x_satellite_id = "WEST"
    draft.access_confirmation = AccessConfirmation(
        satellite_ids=draft.permitted_satellite_ids, confirmed=True
    )
    inputs = build_inputs(
        leg, draft, manager, pois, ConstraintConfig(transition_buffer_minutes=0.05)
    )
    if locked:
        fixed = timed_swap(inputs, 60, "EAST")
        draft.swaps = [fixed]
        draft.locks = [
            PlanningLock(
                id="fixed",
                swap_id=fixed.id,
                anchor=fixed.anchor,
                target_satellite_id="EAST",
            )
        ]
    inputs, context = context_for(inputs, draft)
    scores = []
    for candidate in exhaustive_schedules(inputs, draft, context):
        value = canonical_evaluation(inputs, candidate, context)
        scores.append(
            (value.outage_seconds, value.swap_count, schedule_key(inputs, candidate))
        )
    result = optimizer()(inputs, draft, context)
    score = (
        result.candidate_evaluation.outage_seconds,
        result.candidate_evaluation.swap_count,
        schedule_key(inputs, result.proposed_draft),
    )
    assert score == min(scores)
    if enabled and not locked:
        assert result.candidate_evaluation.swap_count == 2
        assert result.candidate_evaluation.outage_seconds == 12


def test_unchanged_manual_incumbent_can_beat_generated_domain(monkeypatch):
    inputs, draft = configured(monkeypatch, seconds=180, buffer=0.5)
    draft.locks = [
        PlanningLock(id="initial", kind="initial", target_satellite_id="SOUTH")
    ]
    draft.swaps = [timed_swap(inputs, 5, "SOUTH"), timed_swap(inputs, 10, "WEST")]
    inputs, context = context_for(inputs, draft)
    current = canonical_evaluation(inputs, draft, context)
    assert current.outage_seconds == 40
    generated_cost = min(
        canonical_evaluation(inputs, c, context).outage_seconds
        for c in exhaustive_schedules(inputs, draft, context)
    )
    assert generated_cost > current.outage_seconds
    result = optimizer()(inputs, draft, context)
    assert result.candidate_evaluation.outage_seconds == current.outage_seconds
    assert result.retained_current_draft
    assert result.proposed_draft.swaps == draft.swaps
    assert result.proposed_draft.locks == draft.locks
    assert optimizer()(inputs, draft, context).proposed_draft == result.proposed_draft


def test_compatible_same_instant_locked_swaps_keep_both_ids(monkeypatch):
    inputs, draft = configured(monkeypatch, buffer=0.25)
    draft.swaps = [
        timed_swap(inputs, 60, "WEST", id="first"),
        timed_swap(inputs, 60, "WEST", id="second"),
    ]
    draft.locks = [
        PlanningLock(
            id=s.id,
            swap_id=s.id,
            anchor=s.anchor,
            target_satellite_id=s.target_satellite_id,
        )
        for s in draft.swaps
    ]
    inputs, context = context_for(inputs, draft)
    result = optimizer()(inputs, draft, context)
    assert [s.id for s in result.proposed_draft.swaps] == ["first", "second"]
    assert result.candidate_evaluation.swap_count == 2


def test_optimizer_preserves_finite_poi_latitude_snapshot(monkeypatch):
    inputs, draft = configured(monkeypatch)
    inputs = inputs.model_copy(
        update={
            "satellites": tuple(
                s.model_copy(update={"latitude": 2}) for s in inputs.satellites
            )
        }
    )
    inputs, context = context_for(inputs, draft)
    result = optimizer()(inputs, draft, context)
    assert result.state == "ready"


def test_generated_anchor_on_effective_splice_uses_accepted_source(monkeypatch):
    from datetime import timedelta

    from app.mission.models import ManualAARTrack, ManualRouteSplice
    from app.mission.planning.inputs import build_inputs
    from app.mission.planning.match import resolve_anchor
    from app.mission.planning.optimizer import generated_swap
    from app.models.route import ParsedRoute
    from app.satellites.rules import ConstraintConfig

    inputs, draft, _, _, manager, pois, leg = scenario(monkeypatch, seconds=7200)
    draft.manual_aar_tracks = [
        ManualAARTrack(
            id="track",
            name="Deviation",
            points=[
                {"latitude": 10.0025, "longitude": 0.001},
                {"latitude": 10.0075, "longitude": 0.001},
            ],
        )
    ]
    draft.manual_route_splice = ManualRouteSplice(
        enabled_track_id="track", speed_knots=450
    )
    inputs = build_inputs(leg, draft, manager, pois, ConstraintConfig())
    time = inputs.start_time + timedelta(seconds=1830)
    swap = generated_swap(inputs, time, "WEST")
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    assert swap.anchor.route_id == leg.route.route_id
    assert swap.anchor.content_hash == leg.route.content_hash
    assert resolve_anchor(swap.anchor, route) == time
    draft.swaps = [swap]
    inputs, context = context_for(inputs, draft)
    assert canonical_evaluation(inputs, draft, context).swap_count == 1


def test_canonical_disagreement_fails_with_specific_model_error(monkeypatch):
    import app.mission.planning.optimizer as module

    inputs, draft = configured(monkeypatch)
    inputs, context = context_for(inputs, draft)
    original = module._canonical

    def disagree(*args):
        result = original(*args)
        return result.model_copy(update={"outage_seconds": result.outage_seconds + 1})

    monkeypatch.setattr(module, "_canonical", disagree)
    before = draft.model_dump_json()
    with pytest.raises(ValueError) as failure:
        module.optimize(inputs, draft, context)
    assert failure.value.code == "planning_model_consistency"
    assert draft.model_dump_json() == before
