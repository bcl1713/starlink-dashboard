"""Read-only evaluation and validated preparation for reviewed publication."""

from dataclasses import replace
from uuid import uuid4

from app.mission import storage
from app.mission.timeline_preparation import prepare_mission_timeline

from .errors import PlanningFailure, conflict
from .evaluate import evaluate_context
from .grid import build_context
from .inputs import build_inputs, draft_to_mission_leg
from .proposals import environment_identity
from .store import selection_errors


def validate_review(leg, request, evaluation=None):
    draft = leg.draft
    rows = draft.ar_corrections or leg.ar_rows
    confirmed = {row.id for row in rows if row.match_status != "excluded"}
    excluded = {row.id for row in rows if row.match_status == "excluded"}
    invalid = (
        selection_errors(draft)
        or draft.starshield_enabled is None
        or not request.satellite_plan_confirmed
        or not draft.initial_x_satellite_id
        or leg.ar_section_status == "unrecognized"
        or set(request.confirmed_ar_ids) != confirmed
        or set(request.excluded_ar_ids) != excluded
        or len(request.confirmed_ar_ids) != len(confirmed)
        or len(request.excluded_ar_ids) != len(excluded)
        or any(
            not row.confirmed or row.match_status != "matched"
            for row in rows
            if row.match_status != "excluded"
        )
        or (not confirmed and not (draft.no_ars_confirmed and request.no_ars_confirmed))
        or (confirmed and request.no_ars_confirmed)
    )
    if invalid:
        raise PlanningFailure(
            422,
            "review_incomplete",
            "Confirm AR windows or exclusions, no-AR status, satellite access and the satellite plan before saving",
        )
    if evaluation is not None:
        if evaluation.errors:
            raise PlanningFailure(
                422,
                "review_incomplete",
                "Resolve provisional planning inputs before saving",
            )
        if (
            evaluation.outage_seconds or evaluation.backup_gaps
        ) and not request.gap_acknowledged:
            raise PlanningFailure(
                422,
                "gap_acknowledgment_required",
                "Acknowledge X-band outages and backup gaps before saving",
            )


def preview(service, mission_id, leg_id, request):
    store = service.store
    with storage.get_active_leg_lock():
        _, _, source = store.checked(mission_id, leg_id, request.expected_revision)
        leg = source.model_copy(deep=True)
        leg.draft = request.draft.model_copy(deep=True)
        if request.ar_section_status is not None:
            leg.ar_section_status = request.ar_section_status
        constraints = store.planning_constraints_provider()
        environment = environment_identity(store, leg, constraints)
    inputs = build_inputs(
        leg, leg.draft, store.route_manager, store.poi_manager, constraints
    )
    context = build_context(inputs, leg.draft)
    evaluation = evaluate_context(inputs, leg.draft, context)
    if not evaluation.errors:
        from .map_review import check_prepared_map

        candidate = draft_to_mission_leg(
            inputs,
            leg.draft,
            context,
            leg_id=leg.installed_leg_id or leg.id,
            name=f"{leg.departure_airport}–{leg.arrival_airport}",
        )
        artifacts = prepare_mission_timeline(
            candidate,
            store.route_manager,
            store.poi_manager,
            parent_mission_id=mission_id,
            constraint_config=constraints,
            capture_x_conditions=True,
        )
        evaluation.map_diagnostics = list(
            check_prepared_map(candidate, artifacts, constraints, store.poi_manager)
        )
    with storage.get_active_leg_lock():
        store.checked(mission_id, leg_id, request.expected_revision)
        if (
            environment_identity(store, leg, store.planning_constraints_provider())
            != environment
        ):
            raise conflict("Planning dependencies changed; preview again")
    return evaluation


def prepare_reviewed_leg(service, mission_id, leg_id, request):
    store = service.store
    leg, constraints, environment, _ = service.proposals._snapshot(
        mission_id, leg_id, request
    )
    validate_review(leg, request)
    inputs = build_inputs(
        leg, leg.draft, store.route_manager, store.poi_manager, constraints
    )
    context = build_context(inputs, leg.draft)
    evaluation = evaluate_context(inputs, leg.draft, context)
    validate_review(leg, request, evaluation)
    installed = draft_to_mission_leg(
        inputs,
        leg.draft,
        context,
        leg_id=leg.installed_leg_id or str(uuid4()),
        name=f"{leg.departure_airport}–{leg.arrival_airport}",
    )
    if leg.installed_leg_id:
        with storage.get_active_leg_lock():
            parent, _, _ = store.checked(
                mission_id, leg_id, request.expected_revision, request.input_identity
            )
            previous = next(
                item for item in parent.legs if item.id == leg.installed_leg_id
            )
            installed.transports.initial_ka_satellite_ids = list(
                previous.transports.initial_ka_satellite_ids
            )
            installed = previous.model_copy(
                deep=True,
                update={
                    "route_id": installed.route_id,
                    "transports": installed.transports,
                    "adjusted_departure_time": installed.adjusted_departure_time,
                    "is_active": False,
                },
            )
    artifacts = prepare_mission_timeline(
        installed,
        store.route_manager,
        store.poi_manager,
        parent_mission_id=mission_id,
        constraint_config=constraints,
        capture_x_conditions=True,
    )
    if artifacts.planning_evaluation != evaluation:
        raise conflict("Canonical timeline changed; preview again")
    service.proposals._recheck(mission_id, leg_id, request, environment)
    from .map_review import check_prepared_map

    diagnostics = check_prepared_map(
        installed, artifacts, constraints, store.poi_manager
    )
    if diagnostics:
        problem = diagnostics[0]
        raise PlanningFailure(422, problem.code, problem.message, action=problem.action)
    artifacts = replace(artifacts, validated_leg=installed)

    from .publication import PreparedReviewedLeg

    return PreparedReviewedLeg(
        leg_id,
        request.model_copy(deep=True),
        artifacts,
        evaluation,
        request.input_identity,
        environment,
        tuple(diagnostics),
    )


def save_reviewed(service, mission_id, leg_id, request):
    from .models import PublishReviewedBatch, ReviewedLegRequest
    from .publication import publish_reviewed_batch

    return publish_reviewed_batch(
        service,
        mission_id,
        PublishReviewedBatch(
            expected_revision=request.expected_revision,
            entries=[ReviewedLegRequest(leg_id=leg_id, review=request)],
            idempotency_key=request.idempotency_key or str(uuid4()),
        ),
    )
