"""Immutable proposal payloads, live-source validation and revision CAS."""

import hashlib
from dataclasses import asdict
from uuid import UUID, uuid4

from app.mission import storage

from .deadlines import run_bounded
from .errors import PlanningFailure, conflict
from .grid import build_context
from .identity import planning_identity
from .inputs import build_inputs, input_identity, resolve_positions, route_record
from .journal import json_bytes
from .models import PlanningProposal, ProposalReference
from .optimizer import optimize
from .store import leg_identity, selection_errors


def environment_identity(store, leg, constraints):
    """Cheap live dependency capture under the same gate as acceptance/activation.

    No geometry or optimizer work happens here. Hash source bytes so a coverage
    edit during computation is detected even before another sampler is loaded.
    """
    from app.mission.exporter.snapshot_inputs import _coverage_inputs

    if not leg.route or not leg.draft:
        raise ValueError("A bound route and draft are required")
    from .service import PlanningService

    PlanningService(store).validate_selection(leg.draft)
    store.sources.resolve_profile(leg.route.route_id)
    route = store.route_manager.get_route(leg.route.route_id)
    if route is None or route.content_hash != leg.route.content_hash:
        raise ValueError("Bound route is missing or changed")
    return planning_identity(
        {
            "route": route_record(route),
            "positions": resolve_positions(
                leg.draft.permitted_satellite_ids, store.poi_manager
            ),
            "constraints": asdict(constraints),
            "coverage": [(s.name, s.digest) for s in _coverage_inputs()],
        }
    )


class ProposalService:
    def __init__(self, store, constraints_provider=None):
        self.store = store
        if constraints_provider is not None:
            self.constraints_provider = constraints_provider

    @property
    def constraints_provider(self):
        return self.store.planning_constraints_provider

    @constraints_provider.setter
    def constraints_provider(self, provider):
        self.store.planning_constraints_provider = provider

    def _snapshot(self, mission_id, leg_id, request):
        from .service import PlanningService

        with storage.get_active_leg_lock():
            _, manifest, leg = self.store.checked(
                mission_id, leg_id, request.expected_revision, request.input_identity
            )
            if selection_errors(leg.draft):
                raise PlanningFailure(
                    422,
                    "satellite_access_required",
                    "Confirm access to the permitted satellites",
                )
            PlanningService(self.store).validate_selection(leg.draft)
            constraints = self.constraints_provider()
            environment = environment_identity(self.store, leg, constraints)
            snapshot = leg.model_copy(deep=True)
            return snapshot, constraints, environment, manifest

    def _path(self, mission_id, proposal_id):
        try:
            UUID(proposal_id)
        except (ValueError, TypeError):
            raise PlanningFailure(404, "proposal_not_found", "Proposal not found")
        # mission_id is always resolved by _load/checked before this function.
        return (
            self.store.root
            / mission_id
            / "planning"
            / "proposals"
            / f"{proposal_id}.json"
        )

    def _payload(self, mission_id, reference):
        path = self._path(mission_id, reference.id)
        if not path.is_file():
            raise PlanningFailure(
                503,
                "proposal_payload_missing",
                "Proposal storage is unavailable",
                retryable=True,
            )
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != reference.payload_hash:
            raise PlanningFailure(
                503,
                "proposal_payload_changed",
                "Proposal storage is inconsistent",
                retryable=True,
            )
        result = PlanningProposal.model_validate_json(data)
        if (
            result.id != reference.id
            or result.input_identity != reference.input_identity
            or result.expected_revision != reference.expected_revision
        ):
            raise PlanningFailure(
                503,
                "proposal_payload_changed",
                "Proposal reference is inconsistent",
                retryable=True,
            )
        return result

    def status(self, leg, reference, revision):
        if (
            reference.state == "stale"
            or reference.expected_revision != revision
            or reference.input_identity != leg_identity(leg)
        ):
            return "stale"
        try:
            if (
                environment_identity(self.store, leg, self.constraints_provider())
                != reference.environment_identity
            ):
                return "stale"
        except (ValueError, PlanningFailure):
            return "stale"
        return reference.state

    def generate(self, mission_id, leg_id, request, *, cancel_event=None):
        leg, constraints, environment, manifest = self._snapshot(
            mission_id, leg_id, request
        )
        key = (
            hashlib.sha256(request.idempotency_key.encode()).hexdigest()
            if request.idempotency_key
            else None
        )
        if key:
            previous = next(
                (p for p in manifest.proposal_refs if p.idempotency_hash == key), None
            )
            if previous:
                if (
                    previous.leg_id != leg_id
                    or self.status(leg, previous, manifest.revision) != "ready"
                ):
                    raise conflict(
                        "Idempotency key was used for different or stale inputs"
                    )
                return self.get(mission_id, leg_id, previous.id)
        inputs = build_inputs(
            leg,
            leg.draft,
            self.store.route_manager,
            self.store.poi_manager,
            constraints,
        )
        context = build_context(inputs, leg.draft)
        # A capture raced by live configuration must not even launch a solver.
        self._recheck(mission_id, leg_id, request, environment)
        options = {"cancel_event": cancel_event} if cancel_event is not None else {}
        proposal = run_bounded(optimize, (inputs, leg.draft, context), 30, **options)
        if cancel_event is not None and cancel_event.is_set():
            from .deadlines import PlanningWorkerError

            raise PlanningWorkerError("Planning computation cancelled")
        self._recheck(mission_id, leg_id, request, environment)
        fresh = build_inputs(
            leg,
            leg.draft,
            self.store.route_manager,
            self.store.poi_manager,
            self.constraints_provider(),
        )
        if input_identity(fresh) != input_identity(inputs):
            raise conflict("Planning structural inputs changed; recalculate")
        proposal = proposal.model_copy(
            deep=True,
            update={
                "id": str(uuid4()),
                "expected_revision": request.expected_revision,
                "input_identity": request.input_identity,
            },
        )
        data = json_bytes(proposal.model_dump(mode="json"))
        reference = ProposalReference(
            id=proposal.id,
            leg_id=leg_id,
            expected_revision=request.expected_revision,
            input_identity=request.input_identity,
            structural_identity=input_identity(inputs),
            environment_identity=environment,
            payload_hash=hashlib.sha256(data).hexdigest(),
            idempotency_hash=key,
            state=proposal.state,
        )
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, manifest, leg = self._recheck(
                mission_id, leg_id, request, environment
            )
            if key:
                previous = next(
                    (p for p in manifest.proposal_refs if p.idempotency_hash == key),
                    None,
                )
                if previous:
                    if (
                        previous.leg_id != leg_id
                        or self.status(leg, previous, manifest.revision) != "ready"
                    ):
                        raise conflict("Idempotency key was used for different inputs")
                    return self._payload(mission_id, previous)
            if cancel_event is not None and cancel_event.is_set():
                from .deadlines import PlanningWorkerError

                raise PlanningWorkerError("Planning computation cancelled")
            manifest.proposal_refs.append(reference)
            self.store.persist(
                mission, manifest, files={self._path(mission_id, proposal.id): data}
            )
        return proposal

    def _recheck(self, mission_id, leg_id, request, environment):
        with storage.get_active_leg_lock():
            mission, manifest, leg = self.store.checked(
                mission_id, leg_id, request.expected_revision, request.input_identity
            )
            try:
                fresh = environment_identity(
                    self.store, leg, self.constraints_provider()
                )
            except (ValueError, PlanningFailure) as exc:
                raise conflict(
                    "Planning dependencies changed; reload and recalculate"
                ) from exc
            if fresh != environment:
                raise conflict("Planning dependencies changed; reload and recalculate")
            return mission, manifest, leg

    def get(self, mission_id, leg_id, proposal_id):
        with storage.get_active_leg_lock():
            _, manifest = self.store._load(mission_id)
            leg = next(
                (l for l in manifest.expected_legs if l.id == leg_id and not l.retired),
                None,
            )
            ref = next(
                (
                    p
                    for p in manifest.proposal_refs
                    if p.id == proposal_id and p.leg_id == leg_id
                ),
                None,
            )
            if leg is None or ref is None:
                raise PlanningFailure(
                    404, "proposal_not_found", "Proposal not found for this leg"
                )
            result = self._payload(mission_id, ref)
            return result.model_copy(
                update={"state": self.status(leg, ref, manifest.revision)}
            )

    def apply(self, mission_id, leg_id, request):
        # No optimizer call and no writes until all live identities are checked.
        with storage.get_active_leg_lock(), storage.get_mission_lock(mission_id):
            mission, manifest, leg = self.store.checked(
                mission_id, leg_id, request.expected_revision, request.input_identity
            )
            ref = next(
                (
                    p
                    for p in manifest.proposal_refs
                    if p.id == request.proposal_id and p.leg_id == leg_id
                ),
                None,
            )
            if ref is None:
                raise PlanningFailure(
                    404, "proposal_not_found", "Proposal not found for this leg"
                )
            if self.status(leg, ref, manifest.revision) != "ready":
                raise conflict("Proposal inputs changed; recalculate before applying")
            proposal = self._payload(mission_id, ref)
            if proposal.proposed_draft is None:
                raise conflict("Proposal has no feasible schedule")
            leg.draft = proposal.proposed_draft.model_copy(deep=True)
            leg.review = None
            manifest.revision += 1
            for previous in manifest.proposal_refs:
                previous.state = "stale"
            manifest.proposals = [
                p.model_copy(update={"state": "stale"}) for p in manifest.proposals
            ]
            return self.store.persist(mission, manifest)
