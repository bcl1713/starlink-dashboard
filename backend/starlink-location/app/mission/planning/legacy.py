"""Reconcile ordinary managed PUT into drafts with revision-safe publication."""

from uuid import uuid4

from app.mission import storage
from app.mission.timeline_preparation import prepare_mission_timeline
from app.models.poi import POI
from app.services.poi.manager import _route_geometry_hash

from .errors import PlanningFailure, conflict
from .evaluate import evaluate_context
from .grid import build_context
from .inputs import build_inputs, draft_to_mission_leg
from .journal import json_bytes
from .models import AnchoredSwap
from .proposals import environment_identity


def reconcile(card, installed, incoming):
    draft = card.draft.model_copy(deep=True)
    changed = False
    if (
        "initial_ka_satellite_ids" in incoming.transports.model_fields_set
        and incoming.transports.initial_ka_satellite_ids
        != installed.transports.initial_ka_satellite_ids
    ):
        raise PlanningFailure(
            422,
            "initial_ka_selection_unsupported",
            "Managed planning does not support changing initial Ka selection; "
            "preserve the installed IDs and edit Ka outage windows instead",
        )
    for name in (
        "initial_x_satellite_id",
        "starshield_enabled",
        "ka_outages",
        "ku_overrides",
        "manual_aar_tracks",
        "manual_route_splice",
    ):
        if name in incoming.transports.model_fields_set:
            value = getattr(incoming.transports, name)
            if value != getattr(installed.transports, name):
                if name == "starshield_enabled" and value is None:
                    raise PlanningFailure(
                        422,
                        "starshield_enablement_required",
                        "Explicit Starshield enablement is required",
                    )
                setattr(draft, name, value)
                changed = True
    if (
        "adjusted_departure_time" in incoming.model_fields_set
        and incoming.adjusted_departure_time != installed.adjusted_departure_time
    ):
        draft.adjusted_departure_time = incoming.adjusted_departure_time
        changed = True
    transitions = incoming.transports.x_transitions
    if (
        "x_transitions" in incoming.transports.model_fields_set
        and transitions != installed.transports.x_transitions
    ):
        old = {swap.id: swap for swap in draft.swaps}
        accepted, pending = [], []
        for transition in transitions:
            previous = old.get(transition.id)
            anchor = transition.anchor
            if (
                anchor is None
                and previous is not None
                and (transition.latitude, transition.longitude)
                == (previous.anchor.latitude, previous.anchor.longitude)
            ):
                anchor = previous.anchor
            if anchor is None or (transition.latitude, transition.longitude) != (
                anchor.latitude,
                anchor.longitude,
            ):
                pending.append(transition.model_copy(deep=True))
                if previous is not None:
                    accepted.append(previous)
            else:
                accepted.append(
                    AnchoredSwap(
                        id=transition.id,
                        target_satellite_id=transition.target_satellite_id,
                        target_beam_id=transition.target_beam_id,
                        anchor=anchor,
                        origin=previous.origin if previous is not None else "manual",
                    )
                )
        draft.swaps = accepted
        draft.unresolved_x_transitions = pending
        changed = True
    if (
        "aar_windows" in incoming.transports.model_fields_set
        and incoming.transports.aar_windows != installed.transports.aar_windows
    ):
        draft.unresolved_aar_windows = [
            row.model_copy(deep=True) for row in incoming.transports.aar_windows
        ]
        if not incoming.transports.aar_windows:
            draft.ar_corrections = [
                row.model_copy(
                    update={
                        "match_status": "excluded",
                        "exclusion_note": "Removed by ordinary leg edit; confirm exclusion during review",
                        "confirmed": False,
                    }
                )
                for row in (draft.ar_corrections or card.ar_rows)
            ]
        draft.no_ars_confirmed = False
        changed = True
    if changed:
        draft.evaluation_context = None
    return draft, changed


def update_leg(service, mission_id, installed_id, incoming, revision, identity):
    store = service.store
    if revision is None or identity is None:
        raise conflict(
            "Managed edits require the current planning revision and input identity; reload"
        )
    with storage.get_active_leg_lock():
        mission, manifest = store._load(mission_id)
        card = next(
            (
                c
                for c in manifest.expected_legs
                if c.installed_leg_id == installed_id and not c.retired
            ),
            None,
        )
        if card is None:
            raise PlanningFailure(404, "leg_not_found", "Managed leg not found")
        store.checked(mission_id, card.id, revision, identity, allow_active=True)
        installed = next(l for l in mission.legs if l.id == installed_id)
        if incoming.id != installed_id:
            raise PlanningFailure(422, "leg_id_mismatch", "Leg ID must match the URL")
        if incoming.route_id != installed.route_id:
            raise conflict("Use staged route upload to replace a managed route")
        draft, changed = reconcile(card, installed, incoming)
        if changed:
            store.checked(mission_id, card.id, revision, identity)
        candidate = card.model_copy(deep=True)
        candidate.draft = draft
        constraints = store.planning_constraints_provider()
        environment = (
            environment_identity(store, candidate, constraints) if changed else None
        )
        output = installed.model_copy(deep=True)
        for name in ("name", "description"):
            if name in incoming.model_fields_set:
                setattr(output, name, getattr(incoming, name))
    artifacts = None
    if (
        changed
        and not draft.unresolved_x_transitions
        and not draft.unresolved_aar_windows
    ):
        inputs = build_inputs(
            candidate, draft, store.route_manager, store.poi_manager, constraints
        )
        context = build_context(inputs, draft)
        evaluation = evaluate_context(inputs, draft, context)
        if not evaluation.errors:
            projected = draft_to_mission_leg(
                inputs, draft, context, leg_id=installed_id
            )
            projected.transports.initial_ka_satellite_ids = list(
                installed.transports.initial_ka_satellite_ids
            )
            output.transports = projected.transports
            output.adjusted_departure_time = projected.adjusted_departure_time
            artifacts = prepare_mission_timeline(
                output,
                store.route_manager,
                store.poi_manager,
                parent_mission_id=mission_id,
                constraint_config=constraints,
            )
    files = {}
    pois = None
    if artifacts is not None:
        files[storage.get_leg_timeline_path(installed_id, mission_id).resolve()] = (
            json_bytes(artifacts.timeline.model_dump(mode="json"))
        )
        geometry = _route_geometry_hash(artifacts.route)
        pois = {}
        for value in artifacts.generated_pois:
            poi = POI(
                id=str(uuid4()),
                **value.model_dump(),
                generated_source="mission-timeline",
                planned_route_segment_index=value._route_segment_index,
                planned_route_geometry_hash=geometry
            )
            pois[poi.id] = poi.model_dump(mode="json")
            pois[poi.id].update(
                generated_source="mission-timeline",
                planned_route_segment_index=value._route_segment_index,
                planned_route_geometry_hash=geometry,
            )
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        mission, manifest, current = store.checked(
            mission_id, card.id, revision, identity, allow_active=not changed
        )
        if changed:
            try:
                fresh = environment_identity(
                    store, candidate, store.planning_constraints_provider()
                )
            except (ValueError, PlanningFailure) as exc:
                raise conflict("Planning dependencies changed; reload") from exc
            if fresh != environment:
                raise conflict("Planning dependencies changed; reload")
            current.draft = draft
            current.review = None
            for reference in manifest.proposal_refs:
                reference.state = "stale"
            for proposal in manifest.proposals:
                proposal.state = "stale"
        else:
            # Activation does not change planning CAS. Merge metadata into the
            # freshly loaded installed leg while holding the publication gate.
            output = next(
                leg for leg in mission.legs if leg.id == installed_id
            ).model_copy(deep=True)
            for name in ("name", "description"):
                if name in incoming.model_fields_set:
                    setattr(output, name, getattr(incoming, name))
        files[storage.get_mission_leg_file_path(mission_id, installed_id).resolve()] = (
            json_bytes(output.model_dump(mode="json"))
        )
        manifest.revision += 1
        mission.legs = [output if l.id == installed_id else l for l in mission.legs]
        store.persist(
            mission,
            manifest,
            files=files,
            poi_scope=(
                {"mission_id": mission_id, "route_ids": [output.route_id]}
                if pois is not None
                else None
            ),
            pois=pois,
        )
    return {
        "leg": output.model_dump(),
        "warnings": (
            [
                "Plan changes need review. Unresolved inputs are saved in the draft; the installed plan is retained."
            ]
            if changed and artifacts is None
            else None
        ),
    }
