"""One rechecked, idempotent draft transaction for selected immutable proposals."""

import hashlib

from app.mission import storage

from .errors import PlanningFailure, conflict
from .identity import planning_identity
from .store import leg_identity


def _selection(api, mission_id, request):
    mission, manifest = api.store._load(mission_id)
    if manifest.revision != request.expected_revision:
        raise conflict()
    captured = []
    for entry in request.entries:
        _, _, leg = api.store.checked(
            mission_id, entry.leg_id, request.expected_revision, entry.input_identity
        )
        reference = next(
            (
                ref
                for ref in manifest.proposal_refs
                if ref.id == entry.proposal_id and ref.leg_id == entry.leg_id
            ),
            None,
        )
        if reference is None:
            raise PlanningFailure(
                404, "proposal_not_found", "Selected proposal is unavailable"
            )
        if api.status(leg, reference, manifest.revision, mission=mission) != "ready":
            raise conflict("A selected proposal changed; refresh and compare again")
        captured.append((entry, reference.model_copy(deep=True)))
    return mission, manifest, captured


def apply_batch(api, mission_id, request):
    if not request.entries or len({entry.leg_id for entry in request.entries}) != len(
        request.entries
    ):
        raise PlanningFailure(
            422,
            "proposal_selection_required",
            "Choose distinct legs with current proposals",
        )
    key = hashlib.sha256(request.idempotency_key.encode()).hexdigest()
    identity = planning_identity(
        {
            "entries": sorted(
                (entry.model_dump() for entry in request.entries),
                key=lambda entry: entry["leg_id"],
            )
        }
    )
    with storage.get_active_leg_lock():
        mission, manifest = api.store._load(mission_id)
        previous = manifest.proposal_applications.get(key)
        if previous is not None:
            if previous != identity:
                raise conflict("Application key was used for a different selection")
            return api.store._view(mission, manifest)
        _, _, captured = _selection(api, mission_id, request)
    proposals = []
    for entry, reference in captured:
        proposal = api._payload(mission_id, reference)
        if proposal.proposed_draft is None:
            raise conflict("Selected proposal has no feasible schedule")
        proposals.append(
            (entry, reference, proposal.proposed_draft.model_copy(deep=True))
        )
    with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
        mission, manifest = api.store._load(mission_id)
        previous = manifest.proposal_applications.get(key)
        if previous is not None:
            if previous != identity:
                raise conflict("Application key was used for a different selection")
            return api.store._view(mission, manifest)
        _, _, fresh = _selection(api, mission_id, request)
        if [reference for _, reference in fresh] != [
            reference for _, reference in captured
        ]:
            raise conflict("A selected proposal changed during application")
        for entry, reference, draft in proposals:
            leg = next(leg for leg in manifest.expected_legs if leg.id == entry.leg_id)
            leg.draft = draft
            leg.review = None
            for ref in manifest.proposal_refs:
                if ref.leg_id == leg.id:
                    ref.state = "stale"
            applied = next(
                ref for ref in manifest.proposal_refs if ref.id == reference.id
            )
            applied.state = "applied"
            applied.applied_input_identity = leg_identity(leg)
            for historical in manifest.proposals:
                if historical.input_identity == entry.input_identity:
                    historical.state = "stale"
        manifest.proposal_applications[key] = identity
        manifest.revision += 1
        return api.store.persist(mission, manifest)
