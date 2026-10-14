"""Prepare all reviewed legs outside commit locks, then publish one batch."""

import hashlib
from dataclasses import dataclass

from app.mission import storage
from app.mission.timeline_preparation import TimelineArtifacts

from .errors import PlanningFailure, conflict
from .identity import planning_identity
from .models import PlanningError, PlanningEvaluation, SaveReviewed


@dataclass(frozen=True)
class PreparedReviewedLeg:
    leg_id: str
    review: SaveReviewed
    artifacts: TimelineArtifacts
    evaluation: PlanningEvaluation
    input_identity: str
    environment_identity: str
    map_diagnostics: tuple[PlanningError, ...]


@dataclass(frozen=True)
class PreparedReviewBatch:
    expected_revision: int
    entries: tuple[PreparedReviewedLeg, ...]


def publication_identity(request):
    entries = [
        {
            "leg_id": entry.leg_id,
            "review": entry.review.model_dump(
                exclude={"expected_revision", "idempotency_key"}
            ),
        }
        for entry in request.entries
    ]
    return planning_identity(
        {"entries": sorted(entries, key=lambda entry: entry["leg_id"])}
    )


def publication_key(request):
    return hashlib.sha256(request.idempotency_key.encode()).hexdigest()


def validate_batch(request):
    if not request.entries or len({entry.leg_id for entry in request.entries}) != len(
        request.entries
    ):
        raise PlanningFailure(
            422,
            "review_selection_required",
            "Choose distinct legs for reviewed publication",
        )
    if any(
        entry.review.expected_revision != request.expected_revision
        for entry in request.entries
    ):
        raise conflict("All reviews must capture the same mission revision")


def prepare_reviewed_batch(service, mission_id, request):
    from .review import prepare_reviewed_leg

    validate_batch(request)
    with storage.get_active_leg_lock():
        for entry in request.entries:
            service.store.checked(
                mission_id,
                entry.leg_id,
                request.expected_revision,
                entry.review.input_identity,
            )
    entries = tuple(
        prepare_reviewed_leg(service, mission_id, entry.leg_id, entry.review)
        for entry in request.entries
    )
    return PreparedReviewBatch(request.expected_revision, entries)


def publish_reviewed_batch(service, mission_id, request):
    validate_batch(request)
    key, identity = publication_key(request), publication_identity(request)
    with storage.get_active_leg_lock():
        mission, manifest = service.store._load(mission_id)
        previous = manifest.reviewed_publications.get(key)
        if previous is not None:
            if previous != identity:
                raise conflict("Publication key was used for different reviewed inputs")
            return service.store._view(mission, manifest)
    prepared = prepare_reviewed_batch(service, mission_id, request)
    return service.store.commit_reviewed_batch(mission_id, request, prepared)
