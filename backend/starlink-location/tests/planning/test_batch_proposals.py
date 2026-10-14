"""Applying proposals persists selected drafts once and publishes no executable leg."""

import pytest

from app.mission.planning.errors import PlanningFailure
from app.mission.planning.models import (
    ApplyBatchProposals,
    BatchProposalEntry,
    GenerateProposal,
    SaveDraft,
)

from . import test_proposals

prepared = test_proposals.prepared
service = test_proposals.service


def selected(prepared, tmp_path, monkeypatch):
    from app.mission.planning.models import AcceptRouteBinding

    from .test_match import kml_fixture

    service, view = prepared
    source = service.preview_route(
        view.mission.id,
        "card-2",
        kml_fixture(tmp_path)
        .read_bytes()
        .replace(b"<name>P</name>", b"<name>SECOND</name>"),
        view.revision,
        "second.kml",
    )
    view = service.accept_route(
        view.mission.id,
        "card-2",
        AcceptRouteBinding(
            expected_revision=view.revision,
            preview_id=source.preview_id,
            discrepancy_acknowledgments=[e.code for e in source.discrepancy_errors],
        ),
    )
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.no_ars_confirmed = True
    view = service.store.save_draft(
        view.mission.id,
        "card-2",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    draft = view.expected_legs[1].leg.draft.model_copy(deep=True)
    draft.access_confirmation = view.expected_legs[
        0
    ].leg.draft.access_confirmation.model_copy(deep=True)
    view = service.store.save_draft(
        view.mission.id,
        "card-2",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    monkeypatch.setattr(
        "app.mission.planning.proposals.run_bounded",
        lambda fn, args, seconds: fn(*args),
    )
    api = service.proposals
    entries = []
    for card in view.expected_legs[:2]:
        proposal = api.generate(
            view.mission.id,
            card.leg.id,
            GenerateProposal(
                expected_revision=view.revision, input_identity=card.input_identity
            ),
        )
        entries.append(
            BatchProposalEntry(
                leg_id=card.leg.id,
                proposal_id=proposal.id,
                input_identity=card.input_identity,
            )
        )
    return (
        api,
        view,
        ApplyBatchProposals(
            expected_revision=view.revision,
            entries=entries,
            idempotency_key="apply-once",
        ),
    )


def test_batch_apply_persists_without_publication(prepared, tmp_path, monkeypatch):
    api, view, request = selected(prepared, tmp_path, monkeypatch)
    before = {
        entry.proposal_id: api._path(view.mission.id, entry.proposal_id).read_bytes()
        for entry in request.entries
    }
    applied = api.apply_batch(view.mission.id, request)
    assert applied.revision == view.revision + 1
    assert applied.mission.legs == []
    reloaded = api.store.read(view.mission.id)
    assert [card.computation_status for card in reloaded.expected_legs[:2]] == [
        "applied",
        "applied",
    ]
    assert reloaded == applied
    assert api.apply_batch(view.mission.id, request).revision == applied.revision
    assert {
        entry.proposal_id: api._path(view.mission.id, entry.proposal_id).read_bytes()
        for entry in request.entries
    } == before
    with pytest.raises(PlanningFailure):
        api.apply_batch(
            view.mission.id, request.model_copy(update={"entries": request.entries[:1]})
        )


def test_one_stale_proposal_prevents_partial_apply(prepared, tmp_path, monkeypatch):
    api, view, request = selected(prepared, tmp_path, monkeypatch)
    draft = view.expected_legs[1].leg.draft.model_copy(deep=True)
    draft.starshield_enabled = False
    changed = api.store.save_draft(
        view.mission.id,
        "card-2",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    fresh = request.model_copy(update={"expected_revision": changed.revision})
    before = [card.leg.draft for card in changed.expected_legs]
    with pytest.raises(PlanningFailure) as error:
        api.apply_batch(view.mission.id, fresh)
    assert error.value.status_code == 409
    assert [
        card.leg.draft for card in api.store.read(view.mission.id).expected_legs
    ] == before
    assert api.store.read(view.mission.id).mission.legs == []
