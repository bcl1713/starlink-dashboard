"""Shared physical capability and Prefer Starshield operating projection."""

import json
from datetime import timedelta

from app.mission.models import (
    TimelineSegment,
    TimelineStatus,
    Transport,
    TransportState,
)
from app.mission.timeline_builder.calculator import (
    RouteTemporalProjector,
    generate_timeline_samples,
)
from app.models.route import ParsedRoute
from app.satellites.geometry import is_in_azimuth_range, look_angles
from app.satellites.rules import ConstraintConfig

from .grid import swap_times, validate_context
from .models import (
    BackupGap,
    EvaluationInterval,
    PlanningDraft,
    PlanningError,
    PlanningEvaluation,
    PlanningInputs,
)
from .types import EvaluationContext


def active(spans, time):
    return [span for span in spans if span.start_time <= time < span.end_time]


def operating_x_state(raw_constraints, physical_state, ku_usable):
    """Concurrency alone releases when Ku cannot operate; hard blocks remain."""
    shutdown = "x_aft_cone" in raw_constraints and ku_usable
    return ("offline" if shutdown else physical_state), shutdown


def evaluate_context(
    inputs: PlanningInputs, draft: PlanningDraft, context: EvaluationContext
) -> PlanningEvaluation:
    validate_context(inputs, draft, context)
    route = ParsedRoute.model_validate_json(inputs.route_json)
    projector = RouteTemporalProjector(route, inputs.start_time, inputs.end_time)
    config = ConstraintConfig(**json.loads(inputs.constraints_json))
    samples = generate_timeline_samples(projector, None, boundaries=context.boundaries)
    assignments = sorted(
        zip(swap_times(inputs, draft), draft.swaps), key=lambda x: x[0]
    )
    positions = {p.satellite_id: p for p in inputs.satellites}
    buffer = timedelta(minutes=config.transition_buffer_minutes)
    intervals = []
    for sample, end, height in zip(
        samples, context.boundaries[1:], context.height_profile
    ):
        t = sample.timestamp
        selected = draft.initial_x_satellite_id
        for time, swap in assignments:
            if time <= t:
                selected = swap.target_satellite_id
        sat = positions[selected]
        azimuth, elevation = look_angles(
            sample.latitude, sample.longitude, height.height_meters, sat.longitude
        )
        if sample.heading is None:
            raise ValueError("Route heading is unavailable for shared X geometry")
        relative = (azimuth - sample.heading) % 360
        raw, physical, policy = [], [], []
        if is_in_azimuth_range(
            relative, config.normal_azimuth_min, config.normal_azimuth_max
        ):
            raw.append("x_aft_cone")
        if elevation < config.elevation_min_degrees:
            raw.append("x_elevation")
            physical.append("x_elevation")
        if active(inputs.ar_windows, t) and is_in_azimuth_range(
            relative, config.aar_azimuth_min, config.aar_azimuth_max
        ):
            raw.append("x_ar_cone")
            physical.append("x_ar_cone")
        physical.extend(s.reason for s in active(inputs.overlays, t))
        physical.extend(
            f"swap:{swap.id}"
            for time, swap in assignments
            if time - buffer <= t < time + buffer
        )
        raw.extend(r for r in physical if r not in raw)
        physical_x = "degraded" if physical else "available"
        ku = "offline" if active(inputs.ku_outages, t) else "available"
        ka = (
            "offline"
            if active(inputs.ka_outages, t)
            else "degraded" if active(inputs.ka_coverage_windows, t) else "available"
        )
        physical.extend(s.reason for s in active(inputs.ka_coverage_windows, t))
        effective_ku = ku if inputs.starshield_enabled else "offline"
        effective_x, shutdown = operating_x_state(
            raw, physical_x, effective_ku == "available"
        )
        if shutdown:
            policy.append("prefer_starshield:x_aft_cone")
        if not inputs.starshield_enabled:
            policy.append("starshield_disabled")
        physical.extend(
            s.reason
            for s in (*active(inputs.ka_outages, t), *active(inputs.ku_outages, t))
        )
        intervals.append(
            EvaluationInterval(
                start_time=t,
                end_time=end,
                satellite_id=selected,
                latitude=sample.latitude,
                longitude=sample.longitude,
                altitude_meters=height.height_meters,
                heading_degrees=sample.heading,
                raw_constraints=raw,
                physical_x_state=physical_x,
                physical_ka_state=ka,
                physical_ku_state=ku,
                policy_x_state=effective_x,
                policy_ka_state=ka,
                policy_ku_state=effective_ku,
                physical_reasons=physical,
                policy_reasons=policy,
                safety_reasons=[s.reason for s in active(inputs.safety_windows, t)],
            )
        )
    cost = sum(
        (i.end_time - i.start_time).total_seconds()
        for i in intervals
        if i.policy_x_state != "available"
    )
    longest_outage = run = 0.0
    for interval in intervals:
        run = (
            run + (interval.end_time - interval.start_time).total_seconds()
            if interval.policy_x_state != "available"
            else 0.0
        )
        longest_outage = max(longest_outage, run)
    gaps = []
    for i in intervals:
        # One available transport has connectivity but no backup. Safety advice
        # stays separate from this RF operating-state estimate.
        if (
            sum(
                s == "available"
                for s in (i.policy_x_state, i.policy_ka_state, i.policy_ku_state)
            )
            < 2
        ):
            reasons = list(dict.fromkeys([*i.physical_reasons, *i.policy_reasons]))
            if gaps and gaps[-1].end_time == i.start_time:
                gaps[-1].end_time = i.end_time
                gaps[-1].reasons = list(dict.fromkeys([*gaps[-1].reasons, *reasons]))
            else:
                gaps.append(
                    BackupGap(
                        start_time=i.start_time, end_time=i.end_time, reasons=reasons
                    )
                )
    return PlanningEvaluation(
        context=context,
        intervals=intervals,
        outage_seconds=cost,
        swap_count=len(draft.swaps),
        longest_gap_seconds=longest_outage,
        backup_gaps=gaps,
        errors=[
            PlanningError(code="unresolved_ar", message=x) for x in inputs.unresolved
        ],
    )


def timeline_segments(evaluation, mission_id):
    result = []
    for index, i in enumerate(evaluation.intervals):
        states = {
            Transport.X: i.policy_x_state,
            Transport.KA: i.policy_ka_state,
            Transport.KU: i.policy_ku_state,
        }
        impacted = [t for t, s in states.items() if s != "available"]
        status = (
            TimelineStatus.CRITICAL
            if len(impacted) > 1
            else (
                TimelineStatus.DEGRADED
                if impacted
                else TimelineStatus.SOF if i.safety_reasons else TimelineStatus.NOMINAL
            )
        )
        reasons = [*i.physical_reasons, *i.policy_reasons, *i.safety_reasons]
        if "x_aft_cone" in i.raw_constraints:
            reasons.append("X-Ku Conflict")
        result.append(
            TimelineSegment(
                id=f"{mission_id}-planning-{index}",
                start_time=i.start_time,
                end_time=i.end_time,
                status=status,
                x_state=TransportState(i.policy_x_state),
                ka_state=TransportState(i.policy_ka_state),
                ku_state=TransportState(i.policy_ku_state),
                impacted_transports=impacted,
                reasons=reasons,
                metadata={
                    "planning_policy": "prefer_starshield_v1",
                    "planning_interval": i.model_dump(mode="json"),
                    "transport_constraints": {"X": i.raw_constraints},
                    "policy_x_shutdown": "prefer_starshield:x_aft_cone"
                    in i.policy_reasons,
                },
            )
        )
    return result
