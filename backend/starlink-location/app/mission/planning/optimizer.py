"""Exact DAG search over the shared finite grid, with complete buffer costs.

A node closes one generated window. Its state is the satellite at that right
edge (including mandatory assignments inside the window). An edge integrates
all mandatory assignments between windows. Thus equal node states have exactly
the same future options/costs, proving lexicographic prefix dominance. Only
nonoverlapping generated windows are required; locked overlaps are fixed union.
"""

import json
from bisect import bisect_right
from datetime import timedelta
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from app.models.route import ParsedRoute
from app.satellites.catalog import Satellite, SatelliteCatalog
from app.satellites.rules import ConstraintConfig

from .evaluate import evaluate_context
from .grid import ManualLockViolation, _context, swap_times, validate_context
from .inputs import draft_to_mission_leg, structural_draft
from .match import _anchor, resolve_anchor
from .models import AnchoredSwap, PlanningProposal
from .store import selection_errors


class PlanningModelConsistencyError(ValueError):
    code = "planning_model_consistency"


def schedule_key(inputs, draft):
    return (
        draft.initial_x_satellite_id,
        tuple(
            sorted(
                (t.isoformat(), s.target_satellite_id)
                for t, s in zip(swap_times(inputs, draft), draft.swaps)
            )
        ),
    )


def generated_swap(inputs, time, satellite):
    """Real source occurrence plus elapsed timing also works across a splice."""
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    index = next(
        (
            i
            for i, (a, b) in enumerate(zip(route.points, route.points[1:]))
            if a.expected_arrival_time <= time < b.expected_arrival_time
        ),
        len(route.points) - 2,
    )
    a, b = route.points[index : index + 2]
    fraction = max(
        0,
        min(
            1,
            (time - a.expected_arrival_time).total_seconds()
            / (b.expected_arrival_time - a.expected_arrival_time).total_seconds(),
        ),
    )
    source_time = (
        a.expected_arrival_time
        + (b.expected_arrival_time - a.expected_arrival_time) * fraction
    )
    anchor = _anchor(
        route, index, fraction, source_time, f"segment:{index}:{fraction:.12g}"
    )
    anchor = anchor.model_copy(
        update={
            "timing_mode": "elapsed",
            "elapsed_seconds": (time - inputs.start_time).total_seconds(),
        }
    )
    identity = f"{route.content_hash}:{time.isoformat()}:{satellite}"
    return AnchoredSwap(
        id=str(uuid5(NAMESPACE_URL, identity)),
        target_satellite_id=satellite,
        anchor=anchor,
        origin="generated",
    )


def _mandatory(inputs, draft):
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    permitted = {s.satellite_id for s in inputs.satellites}
    initials = set(permitted)
    fixed = {}
    assignments = {}
    for lock in draft.locks:
        if lock.target_satellite_id not in permitted:
            raise ValueError("Manual lock satellite is not permitted")
        if lock.kind == "initial":
            initials &= {lock.target_satellite_id}
            continue
        time = resolve_anchor(lock.anchor, route)
        if not inputs.start_time <= time < inputs.end_time:
            raise ValueError("Manual lock lies outside the leg")
        if time in assignments and assignments[time] != lock.target_satellite_id:
            raise ValueError("Incompatible manual locks at one instant")
        existing = next((s for s in draft.swaps if s.id == lock.swap_id), None)
        if existing and (
            resolve_anchor(existing.anchor, route) != time
            or existing.target_satellite_id != lock.target_satellite_id
        ):
            raise ValueError("Manual lock disagrees with its swap")
        assignments[time] = lock.target_satellite_id
        swap = existing or AnchoredSwap(
            id=lock.swap_id or lock.id,
            target_satellite_id=lock.target_satellite_id,
            anchor=lock.anchor,
        )
        fixed[swap.id] = (time, swap)
    if not initials:
        raise ValueError("No feasible initial lock assignment")
    # Existing simultaneous assignments retain draft order independently of the
    # lock list. Synthesized lock-only assignments follow in stable ID order.
    original_order = {swap.id: index for index, swap in enumerate(draft.swaps)}
    return sorted(initials), sorted(
        fixed.values(),
        key=lambda item: (
            item[0],
            original_order.get(item[1].id, len(original_order)),
            item[1].id,
        ),
    )


def _canonical(inputs, draft, context):
    from app.mission.timeline_preparation import prepare_mission_timeline

    catalog = SatelliteCatalog()
    positions = {
        sat.satellite_id: SimpleNamespace(
            latitude=sat.latitude, longitude=sat.longitude, icon="X"
        )
        for sat in inputs.satellites
    }
    for sat in inputs.satellites:
        catalog.add_satellite(Satellite(sat.satellite_id, "X", longitude=None))
    pois = SimpleNamespace(find_global_poi_by_name=positions.get)
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    leg = draft_to_mission_leg(inputs, draft, context, leg_id="proposal-validation")
    return prepare_mission_timeline(
        leg,
        SimpleNamespace(get_route=lambda _: route),
        pois,
        discover_coverage=False,
        satellite_catalog=catalog,
        constraint_config=ConstraintConfig(**json.loads(inputs.constraints_json)),
    ).planning_evaluation


def optimize(inputs, draft, context):
    if selection_errors(draft):
        raise ValueError("Confirm access to a nonempty permitted satellite set")
    satellites = sorted(s.satellite_id for s in inputs.satellites)
    if set(satellites) != set(draft.permitted_satellite_ids):
        raise ValueError("Satellite snapshot does not match permitted selection")
    if (
        draft.initial_x_satellite_id
        and draft.initial_x_satellite_id not in satellites
        or any(s.target_satellite_id not in satellites for s in draft.swaps)
    ):
        raise ValueError("Current assignment is not permitted")
    initials, fixed = _mandatory(inputs, draft)
    fixed_times = [t for t, _ in fixed]
    fixed_swaps = [s for _, s in fixed]
    buffer = timedelta(
        minutes=json.loads(inputs.constraints_json)["transition_buffer_minutes"]
    )
    start, end = inputs.start_time, inputs.end_time
    # Validate original C/B and structural identity using one feasible schedule.
    feasible = draft.model_copy(
        deep=True, update={"initial_x_satellite_id": initials[0], "swaps": fixed_swaps}
    )
    validate_context(inputs, feasible, context)

    # Constant-satellite shared evaluations remove only locks to permit sampling
    # every satellite. All physical/policy conditions and original C/B stay fixed.
    sample_draft = draft.model_copy(
        deep=True, update={"locks": [], "swaps": [], "evaluation_context": None}
    )
    sample_inputs = inputs.model_copy(
        update={"structural_draft_json": json.dumps(structural_draft(sample_draft))}
    )
    sample_context = _context(sample_inputs, context.seed_times)
    assert sample_context.boundaries == context.boundaries
    boundaries = context.boundaries
    offsets = {t: i for i, t in enumerate(boundaries)}
    prefixes = {}
    for satellite in satellites:
        sample_draft.initial_x_satellite_id = satellite
        evaluation = evaluate_context(sample_inputs, sample_draft, sample_context)
        prefix = [0.0]
        for interval in evaluation.intervals:
            locked_buffer = any(
                t - buffer <= interval.start_time < t + buffer for t in fixed_times
            )
            cost = (
                (interval.end_time - interval.start_time).total_seconds()
                if locked_buffer or interval.policy_x_state != "available"
                else 0
            )
            prefix.append(prefix[-1] + cost)
        prefixes[satellite] = prefix

    def span_cost(a, b, satellite):
        cost = 0.0
        cursor = a
        index = bisect_right(fixed_times, a)
        for time, swap in fixed[index:]:
            if time >= b:
                break
            cost += (
                prefixes[satellite][offsets[time]]
                - prefixes[satellite][offsets[cursor]]
            )
            cursor, satellite = time, swap.target_satellite_id
        return (
            cost
            + prefixes[satellite][offsets[b]]
            - prefixes[satellite][offsets[cursor]]
        )

    def after_locks(satellite, a, b):
        index = bisect_right(fixed_times, b) - 1
        return (
            fixed[index][1].target_satellite_id
            if index >= 0 and fixed_times[index] >= a
            else satellite
        )

    def key(initial, generated):
        return (
            initial,
            tuple(
                sorted(
                    [(t.isoformat(), s.target_satellite_id) for t, s in fixed]
                    + [(t.isoformat(), s) for t, s in generated]
                )
            ),
        )

    # Records: right edge, current satellite, accumulated cost, initial, generated.
    nodes = [(start, after_locks(s, start, start), 0.0, s, ()) for s in initials]
    candidates = [
        t
        for t in context.candidate_times
        if start < t < end
        and start <= t - buffer
        and t + buffer <= end
        and t not in fixed_times
    ]
    for time in candidates:
        left, right = time - buffer, time + buffer
        # The complete edge cost does not depend on the new target: its whole
        # window is outage. Choose the lexicographically best predecessor once,
        # then fan out targets. This is exact, not a heuristic pruning rule.
        best_prefix = None
        for previous, current, cost, initial, generated in nodes:
            if previous > left:
                continue
            score = (
                cost
                + span_cost(previous, left, current)
                + (right - left).total_seconds(),
                len(generated),
            )
            if (
                best_prefix is None
                or score < best_prefix[0]
                or (
                    score == best_prefix[0]
                    and key(initial, generated) < key(best_prefix[1], best_prefix[2])
                )
            ):
                best_prefix = (score, initial, generated)
        if best_prefix is None:
            continue
        (cost, _), initial, generated = best_prefix
        best = {}
        for target in satellites:
            resulting = after_locks(target, time, right)
            history = (*generated, (time, target))
            if resulting not in best or key(initial, history) < key(
                initial, best[resulting][4]
            ):
                best[resulting] = (right, resulting, cost, initial, history)
        nodes.extend(best.values())
    winner = min(
        nodes,
        key=lambda n: (n[2] + span_cost(n[0], end, n[1]), len(n[4]), key(n[3], n[4])),
    )
    right, current, cost, initial, history = winner
    predicted = cost + span_cost(right, end, current)
    swaps = [*fixed_swaps, *(generated_swap(inputs, t, s) for t, s in history)]
    swaps.sort(
        key=lambda s: resolve_anchor(
            s.anchor, ParsedRoute.model_validate_json(inputs.anchor_route_json)
        )
    )
    candidate = draft.model_copy(
        deep=True,
        update={
            "initial_x_satellite_id": initial,
            "swaps": swaps,
            "evaluation_context": context,
        },
    )
    result = evaluate_context(inputs, candidate, context)
    canonical = _canonical(inputs, candidate, context)
    if result.outage_seconds != predicted or canonical != result:
        raise PlanningModelConsistencyError(
            "Planning model-consistency error: canonical winner differs"
        )
    baseline = None
    baseline_kind = "current"
    if draft.initial_x_satellite_id is not None:
        try:
            baseline = evaluate_context(inputs, draft, context)
        except ManualLockViolation:
            # A standalone lock may not yet be installed in the saved schedule.
            # Only this lock-satisfaction failure excludes the current incumbent;
            # all structural, timing, eligibility, and canonical errors propagate.
            pass
    current_is_valid = baseline is not None
    if not current_is_valid:
        baseline_kind = "lock_feasible" if draft.locks else "best_constant"
        baselines = [
            draft.model_copy(
                deep=True, update={"initial_x_satellite_id": s, "swaps": fixed_swaps}
            )
            for s in initials
        ]
        baseline = min(
            (evaluate_context(inputs, b, context) for b in baselines),
            key=lambda e: (e.outage_seconds, e.swap_count),
        )
    retained = False
    if current_is_valid and (
        baseline.outage_seconds,
        baseline.swap_count,
        schedule_key(inputs, draft),
    ) < (result.outage_seconds, result.swap_count, schedule_key(inputs, candidate)):
        # The one unchanged valid manual schedule is an explicit incumbent. We
        # do not search arbitrary edited overlapping manual schedules.
        candidate = draft.model_copy(deep=True, update={"evaluation_context": context})
        result = baseline
        if _canonical(inputs, candidate, context) != result:
            raise PlanningModelConsistencyError(
                "Planning model-consistency error: canonical incumbent differs"
            )
        retained = True
    return PlanningProposal(
        baseline_kind=baseline_kind,
        retained_current_draft=retained,
        id=str(
            uuid5(NAMESPACE_URL, context.input_identity + repr(key(initial, history)))
        ),
        expected_revision=1,
        input_identity=context.input_identity,
        context=context,
        proposed_draft=candidate,
        baseline_evaluation=baseline,
        candidate_evaluation=result,
        state="ready",
    )
