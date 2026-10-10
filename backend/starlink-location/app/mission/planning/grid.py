"""Persisted nonrecursive candidate/boundary grid shared by every schedule."""

import json
from datetime import timedelta

from app.mission.timeline_builder.calculator import RouteTemporalProjector
from app.models.route import ParsedRoute

from .identity import planning_identity
from .inputs import input_identity, structural_draft
from .match import resolve_anchor
from .models import PlanningDraft, PlanningInputs
from .types import EvaluationContext, HeightProfilePoint


def _route(inputs):
    return ParsedRoute.model_validate_json(inputs.route_json)


def swap_times(inputs, draft):
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    return [resolve_anchor(s.anchor, route) for s in draft.swaps]


def height_at(inputs, sample, projector=None):
    from app.mission.timeline_builder.utils import DEFAULT_CRUISE_ALTITUDE_M

    active = [
        span
        for span in inputs.ar_windows
        if span.start_time <= sample.timestamp < span.end_time
        and span.height_meters is not None
    ]
    heights = {s.height_meters for s in active}
    if len(heights) > 1:
        raise ValueError("Overlapping AR windows specify conflicting heights")
    if active:
        return HeightProfilePoint(
            timestamp=sample.timestamp,
            height_meters=active[0].height_meters,
            source="confirmed_ar",
            assumption=active[0].assumption,
        )
    # Prefer a valid route endpoint before falling back to cruise height.
    projector = projector or RouteTemporalProjector(
        _route(inputs), inputs.start_time, inputs.end_time
    )
    route = projector.route
    distance = sample.distance_meters
    index = next(
        (i for i, d in enumerate(projector.cumulative_distances[1:]) if distance < d),
        len(route.points) - 2,
    )
    a, b = route.points[max(index, 0) : max(index, 0) + 2]
    valid = [p.altitude for p in (a, b) if p.altitude is not None and p.altitude >= 0]
    if not valid:
        return HeightProfilePoint(
            timestamp=sample.timestamp,
            height_meters=DEFAULT_CRUISE_ALTITUDE_M,
            source="cruise_fallback",
            assumption=f"Missing or unusable route height: {DEFAULT_CRUISE_ALTITUDE_M:g} m cruise fallback",
        )
    return HeightProfilePoint(
        timestamp=sample.timestamp,
        height_meters=sample.altitude if len(valid) == 2 else valid[0],
        source="route",
        assumption=(
            "Missing endpoint height: available route height used"
            if len(valid) == 1
            else None
        ),
    )


def _context(inputs, seeds):
    from app.mission.timeline_builder.calculator import generate_timeline_samples

    start, end = inputs.start_time, inputs.end_time
    route = _route(inputs)
    projector = RouteTemporalProjector(route, start, end)
    candidates = {start, end, *seeds}
    t = start
    while t < end:
        candidates.add(t)
        t += timedelta(seconds=60)
    # All geometry vertices, including interpolated anchors, can change heading/height.
    candidates.update(
        projector.timestamp_for_distance(d) for d in projector.cumulative_distances
    )
    for span in (
        *inputs.ar_windows,
        *inputs.ka_coverage_windows,
        *inputs.overlays,
        *inputs.ka_outages,
        *inputs.ku_outages,
        *inputs.safety_windows,
    ):
        candidates.update(
            (max(start, min(end, span.start_time)), max(start, min(end, span.end_time)))
        )
    candidates = sorted(t for t in candidates if start <= t <= end)
    buffer = timedelta(
        minutes=json.loads(inputs.constraints_json)["transition_buffer_minutes"]
    )
    boundaries = sorted(
        {
            *candidates,
            *(
                max(start, min(end, t + offset))
                for t in candidates
                for offset in (-buffer, buffer)
            ),
        }
    )
    identity = planning_identity(
        {
            "inputs": input_identity(inputs),
            "seeds": seeds,
            "candidates": candidates,
            "boundaries": boundaries,
        }
    )
    samples = generate_timeline_samples(projector, None, boundaries=boundaries)
    heights = [height_at(inputs, s, projector) for s in samples]
    assumptions = list(
        dict.fromkeys(
            [*inputs.assumptions, *(h.assumption for h in heights if h.assumption)]
        )
    )
    return EvaluationContext(
        input_identity=identity,
        seed_times=sorted(set(seeds)),
        candidate_times=candidates,
        boundaries=boundaries,
        source_hashes={
            "route": route.content_hash,
            "inputs": input_identity(inputs),
            "constraints": planning_identity(json.loads(inputs.constraints_json)),
            "coverage": planning_identity(
                {"coverage": json.loads(inputs.coverage_json)}
            ),
            "satellite_positions": planning_identity({"positions": inputs.satellites}),
        },
        height_profile=heights,
        assumptions=assumptions,
    )


def build_context(inputs: PlanningInputs, draft: PlanningDraft) -> EvaluationContext:
    if draft.evaluation_context is not None:
        try:
            validate_context(inputs, draft, draft.evaluation_context)
            return draft.evaluation_context.model_copy(deep=True)
        except ValueError:
            pass
    seeds = sorted(set(swap_times(inputs, draft)))
    return _context(inputs, seeds)


def validate_context(inputs, draft, context):
    if context is None:
        raise ValueError("Planning requires a persisted evaluation context")
    # A missing corrections list may mean the input builder inherited itinerary rows.
    current = structural_draft(draft)
    stored = json.loads(inputs.structural_draft_json)
    if not current["ar_corrections"]:
        current["ar_corrections"] = stored["ar_corrections"]
    if planning_identity(current) != planning_identity(stored):
        raise ValueError("Structural planning inputs changed; rebuild input snapshot")
    if context != _context(inputs, context.seed_times):
        raise ValueError("Evaluation context is stale or inconsistent")
    times = swap_times(inputs, draft)
    if any(t not in context.candidate_times for t in times):
        raise ValueError("Manual swap timing changed; create a new evaluation context")
    permitted = {s.satellite_id for s in inputs.satellites}
    if draft.initial_x_satellite_id not in permitted or any(
        s.target_satellite_id not in permitted for s in draft.swaps
    ):
        raise ValueError("Selected satellite is not in the permitted position snapshot")
    at = {}
    for t, s in zip(times, draft.swaps):
        if t in at and at[t] != s.target_satellite_id:
            raise ValueError("Conflicting satellite assignments at one instant")
        at[t] = s.target_satellite_id
    route = ParsedRoute.model_validate_json(inputs.anchor_route_json)
    for lock in draft.locks:
        if lock.kind == "initial":
            valid = draft.initial_x_satellite_id == lock.target_satellite_id
        else:
            valid = (
                at.get(resolve_anchor(lock.anchor, route)) == lock.target_satellite_id
            )
        if not valid:
            raise ValueError("Selected schedule violates a manual lock")
