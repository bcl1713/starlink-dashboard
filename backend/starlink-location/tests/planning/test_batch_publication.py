"""One reviewed-publication commit, with whole-batch recovery and ownership gates."""

import pytest

from app.mission.planning.errors import PlanningFailure
from app.mission.planning.models import (
    PublishReviewedBatch,
    ReviewedLegRequest,
    SaveReviewed,
)

from . import test_batch_proposals
from .test_reviewed_save import snapshot

prepared = test_batch_proposals.prepared
service = test_batch_proposals.service


def ready(prepared, tmp_path, monkeypatch):
    api, view, application = test_batch_proposals.selected(
        prepared, tmp_path, monkeypatch
    )
    view = api.apply_batch(view.mission.id, application)
    return (
        prepared[0],
        view,
        PublishReviewedBatch(
            expected_revision=view.revision,
            idempotency_key="publish-once",
            entries=[
                ReviewedLegRequest(
                    leg_id=card.leg.id,
                    review=SaveReviewed(
                        expected_revision=view.revision,
                        input_identity=card.input_identity,
                        evaluation_identity=card.leg.draft.evaluation_context.input_identity,
                        satellite_plan_confirmed=True,
                        no_ars_confirmed=True,
                        gap_acknowledged=True,
                    ),
                )
                for card in view.expected_legs[:2]
            ],
        ),
    )


def test_invalid_leg_prevents_batch_publication(prepared, tmp_path, monkeypatch):
    service, view, request = ready(prepared, tmp_path, monkeypatch)
    before = snapshot(service)
    request.entries[1].review.satellite_plan_confirmed = False
    with pytest.raises(PlanningFailure):
        service.publish_reviewed_batch(view.mission.id, request)
    assert snapshot(service) == before
    assert service.store.read(view.mission.id).mission.legs == []


def test_published_batch_is_inactive_and_idempotent(prepared, tmp_path, monkeypatch):
    service, view, request = ready(prepared, tmp_path, monkeypatch)
    saved = service.publish_reviewed_batch(view.mission.id, request)
    assert saved.revision == view.revision + 1
    assert len(saved.mission.legs) == 2
    assert all(not leg.is_active for leg in saved.mission.legs)
    assert [card.review_status for card in saved.expected_legs[:2]] == [
        "reviewed",
        "reviewed",
    ]
    before = snapshot(service)
    retry = service.publish_reviewed_batch(view.mission.id, request)
    assert retry.revision == saved.revision
    assert snapshot(service) == before
    from app.mission import storage

    assert len(storage.load_mission_metadata_v2(view.mission.id).legs) == 2


@pytest.mark.parametrize("committed", [False, True])
def test_batch_journal_recovery_is_atomic(prepared, tmp_path, monkeypatch, committed):
    import json

    from app.mission import storage
    from app.mission.planning import journal
    from app.mission.planning.publication import prepare_reviewed_batch

    service, view, request = ready(prepared, tmp_path, monkeypatch)
    artifacts = prepare_reviewed_batch(service, view.mission.id, request)
    original = journal.atomic_write

    class Interrupted(BaseException):
        pass

    writes = []

    def interrupt(path, data):
        original(path, data)
        writes.append(path)
        if committed:
            if (
                path.parent == service.store.journal.directory
                and data is not None
                and json.loads(data)["state"] == "committed"
            ):
                raise Interrupted()
        elif path.parent.name == "legs" and path.suffix == ".json":
            raise Interrupted()

    monkeypatch.setattr(journal, "atomic_write", interrupt)
    with pytest.raises(Interrupted):
        service.store.commit_reviewed_batch(view.mission.id, request, artifacts)
    monkeypatch.setattr(journal, "atomic_write", original)
    service.store.journal.recover()
    service.store.poi_manager.reload_pois()
    stored = storage.load_mission_v2(view.mission.id)
    assert len(stored.legs) == (2 if committed else 0)
    assert all(not leg.is_active for leg in stored.legs)
    assert not list(service.store.journal.directory.glob("*.json"))


def test_stale_binding_rejects_prepared_batch_without_publication(
    prepared, tmp_path, monkeypatch
):
    from app.mission.planning.models import SaveDraft
    from app.mission.planning.publication import prepare_reviewed_batch

    service, view, request = ready(prepared, tmp_path, monkeypatch)
    artifacts = prepare_reviewed_batch(service, view.mission.id, request)
    draft = view.expected_legs[1].leg.draft.model_copy(deep=True)
    draft.starshield_enabled = False
    changed = service.store.save_draft(
        view.mission.id,
        "card-2",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.store.commit_reviewed_batch(view.mission.id, request, artifacts)
    assert error.value.status_code == 409
    assert snapshot(service) == before
    assert service.store.read(view.mission.id).mission.legs == []
    assert changed.expected_legs[1].leg.draft.starshield_enabled is False


def test_foreign_poi_scope_and_duplicate_executable_route_reject_whole_batch(
    prepared, tmp_path, monkeypatch
):
    from dataclasses import replace

    from app.mission.planning.publication import prepare_reviewed_batch

    service, view, request = ready(prepared, tmp_path, monkeypatch)
    batch = prepare_reviewed_batch(service, view.mission.id, request)
    original = batch.entries[1]
    poi = original.artifacts.generated_pois[0].model_copy(
        update={"mission_id": "foreign"}
    )
    corrupted = replace(
        original,
        artifacts=replace(
            original.artifacts,
            generated_pois=(poi, *original.artifacts.generated_pois[1:]),
        ),
    )
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.store.commit_reviewed_batch(
            view.mission.id,
            request,
            replace(batch, entries=(batch.entries[0], corrupted)),
        )
    assert snapshot(service) == before
    bad = original.artifacts.validated_leg.model_copy(
        update={"route_id": batch.entries[0].artifacts.validated_leg.route_id}
    )
    corrupted = replace(
        original, artifacts=replace(original.artifacts, validated_leg=bad)
    )
    with pytest.raises(PlanningFailure):
        service.store.commit_reviewed_batch(
            view.mission.id,
            request,
            replace(batch, entries=(batch.entries[0], corrupted)),
        )
    assert snapshot(service) == before
