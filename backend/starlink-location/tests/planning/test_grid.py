from datetime import timedelta

from app.mission.planning.models import AnchoredSwap
from app.mission.planning.types import EvaluationContext, RouteAnchor

from .test_policy import START, planning_api, scenario


def swap(seconds=1830):
    return AnchoredSwap(
        id="swap",
        target_satellite_id="WEST",
        anchor=RouteAnchor(
            route_id="owned",
            content_hash="a" * 64,
            segment_index=0,
            fraction=seconds / 7200,
            occurrence_id=f"segment:0:{seconds/7200:.12g}",
            source_time=START + timedelta(seconds=seconds),
            latitude=10 + 0.01 * seconds / 7200,
            longitude=0,
        ),
    )


def test_unlocked_second_level_swap_has_all_buffer_boundaries(monkeypatch):
    _, _, context, *_ = scenario(monkeypatch, seconds=7200, swaps=[swap()])
    time = START + timedelta(seconds=1830)
    assert {
        START,
        time - timedelta(minutes=15),
        time,
        time + timedelta(minutes=15),
    } <= set(context.boundaries)
    assert time in context.candidate_times
    assert time + timedelta(minutes=15) not in context.candidate_times


def test_context_survives_removing_seed_swap_after_apply(monkeypatch):
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, seconds=7200, swaps=[swap()]
    )
    accepted = draft.model_copy(
        deep=True,
        update={
            "swaps": [],
            "evaluation_context": EvaluationContext.model_validate_json(
                context.model_dump_json()
            ),
        },
    )
    _, grid, _ = planning_api()
    assert grid(inputs, accepted) == context
    assert evaluate(inputs, accepted, context).context.boundaries == context.boundaries


def test_overlap_counts_once(monkeypatch):
    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, seconds=7200, starshield_enabled=False, swaps=[swap(), swap(1860)]
    )
    # [00:15:30,00:45:30) union [00:16:00,00:46:00) is exactly 1830 seconds.
    result = evaluate(inputs, draft, context)
    assert result.outage_seconds == 1830
    assert result.outage_seconds == sum(
        (x.end_time - x.start_time).total_seconds()
        for x in result.intervals
        if x.policy_x_state != "available"
    )


def test_context_enablement_changes_but_confirmations_do_not(monkeypatch):
    from app.mission.planning.store import leg_identity
    from app.satellites.rules import ConstraintConfig

    _inputs, draft, context, _, manager, pois, leg = scenario(monkeypatch)
    build, grid, _ = planning_api()
    original_card = leg_identity(leg)
    draft.no_ars_confirmed = True
    assert (
        grid(build(leg, draft, manager, pois, ConstraintConfig()), draft).input_identity
        == context.input_identity
    )
    leg.draft = draft
    assert leg_identity(leg) != original_card
    draft.starshield_enabled = False
    assert (
        grid(build(leg, draft, manager, pois, ConstraintConfig()), draft).input_identity
        != context.input_identity
    )
    enabled_identity = grid(
        build(leg, draft, manager, pois, ConstraintConfig()), draft
    ).input_identity
    manager.get_route("owned").metadata.description = "Overview hidden"
    assert (
        grid(build(leg, draft, manager, pois, ConstraintConfig()), draft).input_identity
        == enabled_identity
    )


def test_forged_context_and_conflicting_assignments_rejected(monkeypatch):
    import pytest

    inputs, draft, context, evaluate, *_ = scenario(
        monkeypatch, seconds=7200, swaps=[swap()]
    )
    forged = context.model_copy(
        update={"boundaries": context.boundaries[:-2] + context.boundaries[-1:]}
    )
    with pytest.raises(ValueError, match="inconsistent"):
        evaluate(inputs, draft, forged)
    draft.swaps.append(
        swap().model_copy(update={"id": "other", "target_satellite_id": "SOUTH"})
    )
    with pytest.raises(ValueError, match="Conflicting"):
        evaluate(inputs, draft, context)


def test_snapshot_is_immutable_and_context_binds_configuration(monkeypatch):
    import pytest

    from app.mission.planning.grid import build_context
    from app.mission.planning.inputs import build_inputs
    from app.satellites.rules import ConstraintConfig

    inputs, draft, context, evaluate, manager, pois, leg = scenario(monkeypatch)
    with pytest.raises(ValueError):
        inputs.starshield_enabled = False
    with pytest.raises(ValueError):
        inputs.satellites[0].longitude = 22
    changed = build_inputs(
        leg, draft, manager, pois, ConstraintConfig(elevation_min_degrees=20)
    )
    assert build_context(changed, draft).input_identity != context.input_identity
    with pytest.raises(ValueError, match="inconsistent"):
        evaluate(changed, draft, context)
