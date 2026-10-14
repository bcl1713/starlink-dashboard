"""Batch staging and one binding transaction, with disposable synthetic sources."""

import pytest

from app.mission.planning.errors import PlanningFailure
from app.mission.planning.models import (
    AcceptBatchRoutes,
    BatchRouteAssignment,
    SaveDraft,
)

from . import test_store
from .test_match import kml_fixture

service = test_store.service


def stage(service, tmp_path):
    from app.mission.planning.intake import preview_routes

    view, _ = test_store.create(service)
    data = kml_fixture(tmp_path).read_bytes()
    return view, preview_routes(
        service, view.mission.id, [("leg-1.kml", data)], view.revision
    )


def test_batch_requires_unambiguous_assignments(service, tmp_path):
    from app.mission.planning.intake import accept_routes

    view, preview = stage(service, tmp_path)
    attachment = preview.attachments[0]
    # These identical expected airport/time windows cannot be guessed by filename.
    assert attachment.suggested_leg_id is None
    assert len(attachment.candidates) == 3
    assert service.store.read(view.mission.id) == view
    with pytest.raises(PlanningFailure):
        accept_routes(
            service,
            view.mission.id,
            AcceptBatchRoutes(
                expected_revision=view.revision,
                preview_id=preview.preview_id,
                assignments=[],
            ),
        )
    selected = attachment.candidates[0]
    saved = accept_routes(
        service,
        view.mission.id,
        AcceptBatchRoutes(
            expected_revision=view.revision,
            preview_id=preview.preview_id,
            assignments=[
                BatchRouteAssignment(
                    attachment_id=attachment.attachment_id,
                    leg_id=selected.leg_id,
                    discrepancy_acknowledgments=[
                        e.code for e in selected.discrepancy_errors
                    ],
                )
            ],
        ),
    )
    assert saved.revision == view.revision + 1
    assert saved.expected_legs[0].leg.route is not None
    assert saved.mission.legs == []


def test_batch_acceptance_is_atomic(service, tmp_path):
    from app.mission.planning.intake import accept_routes, preview_routes

    view, _ = test_store.create(service)
    data = kml_fixture(tmp_path).read_bytes()
    preview = preview_routes(
        service,
        view.mission.id,
        [
            ("one.kml", data),
            ("two.kml", data.replace(b"<name>P</name>", b"<name>DIFFERENT</name>")),
        ],
        view.revision,
    )
    request = AcceptBatchRoutes(
        expected_revision=view.revision,
        preview_id=preview.preview_id,
        assignments=[
            BatchRouteAssignment(
                attachment_id=a.attachment_id,
                leg_id=f"card-{n}",
                discrepancy_acknowledgments=[
                    e.code for e in a.candidates[n - 1].discrepancy_errors
                ],
            )
            for n, a in enumerate(preview.attachments, 1)
        ],
    )
    paths = {
        str(p): p.read_bytes()
        for root in [service.store.root, service.store.route_manager.routes_dir]
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    original = service.store.journal.commit

    def fail(*args, **kwargs):
        raise OSError("simulated journal failure")

    service.store.journal.commit = fail
    with pytest.raises(OSError):
        accept_routes(service, view.mission.id, request)
    assert {
        str(p): p.read_bytes()
        for root in [service.store.root, service.store.route_manager.routes_dir]
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    } == paths
    service.store.journal.commit = original
    changed = service.store.save_draft(
        view.mission.id,
        "card-3",
        SaveDraft(
            expected_revision=view.revision, draft=view.expected_legs[2].leg.draft
        ),
    )
    with pytest.raises(PlanningFailure) as error:
        accept_routes(service, view.mission.id, request)
    assert error.value.status_code == 409
    assert all(
        card.leg.route is None
        for card in service.store.read(view.mission.id).expected_legs
    )
    assert service.store.read(view.mission.id) == changed


def test_batch_parses_once_and_preserves_invalid_duplicate_controls(
    service, tmp_path, monkeypatch
):
    from app.mission.planning import intake

    view, _ = test_store.create(service)
    data = kml_fixture(tmp_path).read_bytes()
    real = intake.run_bounded
    calls = []

    def parse(fn, args, seconds):
        calls.append(args)
        return real(fn, args, seconds)

    monkeypatch.setattr(intake, "run_bounded", parse)
    preview = intake.preview_routes(
        service,
        view.mission.id,
        [("misleading.kml", data), ("same.kml", data), ("invalid.kml", b"broken")],
        view.revision,
    )
    assert len(calls) == 2  # duplicate never launches another parser
    assert preview.attachments[1].errors[0].code == "duplicate_route_upload"
    assert preview.attachments[2].errors
    assert all(
        card.leg.route is None
        for card in service.store.read(view.mission.id).expected_legs
    )


def test_unique_evidence_suggests_and_success_commits_one_batch(
    service, tmp_path, monkeypatch
):
    from app.mission.planning.intake import accept_routes, preview_routes

    view, _ = test_store.create(service)
    mission, manifest = service.store._load(view.mission.id)
    from .test_match import utc

    for leg in manifest.expected_legs:
        leg.departure_time = utc("09:00:00")
        leg.arrival_time = utc("12:00:00")
    manifest.expected_legs[1].departure_airport = "CCCC"
    manifest.expected_legs[1].arrival_airport = "DDDD"
    manifest.expected_legs[2].departure_airport = "EEEE"
    manifest.expected_legs[2].arrival_airport = "FFFF"
    view = service.store.persist(mission, manifest)
    data = kml_fixture(tmp_path).read_bytes()
    other = data.replace(b"AAAA", b"CCCC").replace(b"BBBB", b"DDDD")
    preview = preview_routes(
        service,
        view.mission.id,
        [("WRONG-Leg-2.kml", data), ("WRONG-Leg-1.kml", other)],
        view.revision,
    )
    assert preview.attachments[0].departure_airport == "AAAA"
    assert preview.attachments[0].source_departure_time == utc("09:00:00")
    assert preview.attachments[0].source_arrival_time == utc("12:00:00")
    assert [item.suggested_leg_id for item in preview.attachments] == [
        "card-1",
        "card-2",
    ]
    commit = service.store.journal.commit
    calls = []

    def once(*args, **kwargs):
        calls.append(args)
        return commit(*args, **kwargs)

    monkeypatch.setattr(service.store.journal, "commit", once)
    saved = accept_routes(
        service,
        view.mission.id,
        AcceptBatchRoutes(
            expected_revision=view.revision,
            preview_id=preview.preview_id,
            assignments=[
                BatchRouteAssignment(
                    attachment_id=item.attachment_id, leg_id=item.suggested_leg_id
                )
                for item in preview.attachments
            ],
        ),
    )
    assert len(calls) == 1
    assert saved.revision == view.revision + 1
    assert saved.mission.legs == []
    assert all(card.leg.route for card in saved.expected_legs[:2])
    assert all(not card.leg.review for card in saved.expected_legs)
    assert not service.sources.preview_path(preview.preview_id).exists()
    for item in preview.attachments:
        assert service.sources.resolve_profile(item.attachment_id) == "planning_v1"


def test_cancel_batch_preserves_previously_accepted_sources(service, tmp_path):
    from app.mission.planning.intake import discard_routes, preview_routes

    view, _ = test_store.create(service)
    view = test_store.bind(service, tmp_path)
    route = view.expected_legs[0].leg.route
    path = service.sources.routes_dir / f"{route.route_id}.kml"
    before = path.read_bytes()
    preview = preview_routes(
        service, view.mission.id, [("replace.kml", before)], view.revision
    )
    discard_routes(service, view.mission.id, preview.preview_id)
    assert not service.sources.preview_path(preview.preview_id).exists()
    assert path.read_bytes() == before
    assert service.store.read(view.mission.id) == view


from . import test_proposals

prepared = test_proposals.prepared


def test_batch_replacement_retains_prior_installed_plan_and_corrections(
    prepared, tmp_path
):
    from app.mission.planning.intake import accept_routes, preview_routes

    from .test_reviewed_save import confirmed, review

    service, view = confirmed(prepared)
    view = service.save_reviewed(view.mission.id, "card-1", review(view))
    before = view.mission.legs[0].model_copy(deep=True)
    from app.mission import storage

    artifact_paths = [
        storage.get_mission_leg_file_path(view.mission.id, before.id),
        storage.get_leg_timeline_path(before.id, view.mission.id),
    ]
    original_artifacts = {path: path.read_bytes() for path in artifact_paths}
    card = view.expected_legs[0].leg
    old_source = service.sources.routes_dir / f"{card.route.route_id}.kml"
    data = old_source.read_bytes().replace(b"<name>P</name>", b"<name>DIFFERENT</name>")
    preview = preview_routes(
        service, view.mission.id, [("replacement.kml", data)], view.revision
    )
    item = preview.attachments[0]
    candidate = next(c for c in item.candidates if c.leg_id == card.id)
    saved = accept_routes(
        service,
        view.mission.id,
        AcceptBatchRoutes(
            expected_revision=view.revision,
            preview_id=preview.preview_id,
            assignments=[
                BatchRouteAssignment(
                    attachment_id=item.attachment_id,
                    leg_id=card.id,
                    discrepancy_acknowledgments=[
                        e.code for e in candidate.discrepancy_errors
                    ],
                )
            ],
        ),
    )
    assert saved.mission.legs[0].model_dump(mode="json") == before.model_dump(
        mode="json"
    )
    assert {path: path.read_bytes() for path in artifact_paths} == original_artifacts
    assert not saved.mission.legs[0].is_active
    updated = saved.expected_legs[0].leg
    assert updated.review is None
    assert updated.draft.ar_corrections == card.draft.ar_corrections
    assert updated.draft.locks == card.draft.locks
    assert updated.draft.starshield_enabled == card.draft.starshield_enabled
    assert old_source.is_file()
    manifest = service.store._load(view.mission.id)[1]
    assert manifest.leg_history[-1].installed_leg.model_dump(
        mode="json"
    ) == before.model_dump(mode="json")
    assert manifest.route_history[-1] == card.route
