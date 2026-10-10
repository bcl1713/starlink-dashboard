"""Synthetic revisions exercise real immutable source storage."""

from datetime import timedelta

import pytest

from app.mission.planning.errors import PlanningFailure
from app.mission.planning.match import _candidates, resolve_anchor
from app.mission.planning.models import (
    AcceptRouteBinding,
    AnchoredSwap,
    PlanningLock,
    SaveDraft,
)

from . import test_proposals
from .test_match import kml_fixture
from .test_reviewed_save import confirmed, review
from .test_reviewed_save import snapshot as source_snapshot

prepared = test_proposals.prepared
service = test_proposals.service


def snapshot(service):
    path = service.store.poi_manager.pois_file
    return {**source_snapshot(service), str(path): path.read_bytes()}


def replacement(service, view, tmp_path):
    return service.preview_route(
        view.mission.id,
        "card-1",
        kml_fixture(tmp_path)
        .read_bytes()
        .replace(b"<name>P</name>", b"<name>RENAMED</name>"),
        view.revision,
        "renamed.kml",
    )


def accept(service, view, preview):
    return service.accept_route(
        view.mission.id,
        "card-1",
        AcceptRouteBinding(
            expected_revision=view.revision,
            preview_id=preview.preview_id,
            discrepancy_acknowledgments=[e.code for e in preview.discrepancy_errors],
        ),
    )


def test_changed_waypoint_names_retain_old_anchors_and_locks(prepared, tmp_path):
    service, view = confirmed(prepared)
    route = service.store.route_manager.get_route(
        view.expected_legs[0].leg.route.route_id
    )
    anchor = _candidates(route.points[1].expected_arrival_time, "second", route)[0]
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.swaps = [AnchoredSwap(id="manual", target_satellite_id="WEST", anchor=anchor)]
    draft.locks = [
        PlanningLock(
            id="lock", swap_id="manual", target_satellite_id="WEST", anchor=anchor
        )
    ]
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    before = saved.mission.legs[0].model_copy(deep=True)
    staged = replacement(service, saved, tmp_path)
    assert staged.old_source_hash == saved.expected_legs[0].leg.route.content_hash
    assert set(staged.unresolved_lock_ids) == {"lock"}
    assert service.store.read(view.mission.id).mission.legs[0] == before
    accepted = accept(service, saved, staged)
    assert accepted.mission.legs[0] == before
    assert accepted.expected_legs[0].leg.draft.locks == draft.locks
    assert accepted.expected_legs[0].leg.draft.swaps == draft.swaps
    with pytest.raises((PlanningFailure, ValueError)):
        service.save_reviewed(view.mission.id, "card-1", review(accepted))


def test_departure_adjustment_is_preserved_once(prepared, tmp_path):
    service, view = confirmed(prepared)
    route = service.store.route_manager.get_route(
        view.expected_legs[0].leg.route.route_id
    )
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    draft.adjusted_departure_time = route.source_departure_time + timedelta(hours=16)
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    preview = replacement(service, saved, tmp_path)
    assert preview.adjusted_departure_time == draft.adjusted_departure_time
    accepted = accept(service, saved, preview)
    card = accepted.expected_legs[0].leg
    new_route = service.store.route_manager.get_route(card.route.route_id)
    anchor = _candidates(
        new_route.points[1].expected_arrival_time, "second", new_route
    )[0]
    assert resolve_anchor(
        anchor, new_route, card.draft.adjusted_departure_time
    ) == anchor.source_time + timedelta(hours=16)
    assert accepted.mission.legs == saved.mission.legs


def test_cancel_stale_and_failed_replacement_preserve_installed_state(
    prepared, tmp_path
):
    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    before_preview = service.store.read(view.mission.id)
    staged = replacement(service, saved, tmp_path)
    assert service.store.read(view.mission.id) == before_preview
    before = snapshot(service)
    from app.services.kml_parser import KMLParseError

    with pytest.raises(KMLParseError):
        service.preview_route(view.mission.id, "card-1", b"not KML", saved.revision)
    assert snapshot(service) == before
    newer = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(
            expected_revision=saved.revision, draft=saved.expected_legs[0].leg.draft
        ),
    )
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        accept(service, saved, staged)
    assert error.value.status_code == 409
    assert snapshot(service) == before
    assert service.store.read(view.mission.id).revision == newer.revision
    assert service.store.read(view.mission.id).mission.legs == newer.mission.legs


def revision_preview(
    service, view, monkeypatch, *, legs=None, source_revision=2, data=b"revision two"
):
    from datetime import datetime, timedelta, timezone

    from app.mission.planning.models import ItineraryData, ItineraryPreview

    incoming = legs or [
        c.leg.model_copy(
            update={
                "route": None,
                "draft": None,
                "review": None,
                "installed_leg_id": None,
            }
        )
        for c in view.expected_legs
    ]
    incoming = [
        leg.model_copy(
            update={
                "route": None,
                "draft": None,
                "review": None,
                "installed_leg_id": None,
            }
        )
        for leg in incoming
    ]
    parsed = ItineraryData(
        name="Synthetic revised",
        itinerary_revision=source_revision,
        expected_legs=incoming,
    )
    monkeypatch.setattr(
        "app.mission.planning.service.extract_itinerary",
        lambda _: ItineraryPreview(
            preview_id="extracted",
            parsed_values=parsed,
            confirmable=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )
    return service.preview_revision(view.mission.id, data, view.revision)


def revision_request(preview, **changes):
    from app.mission.planning.models import ApplyRevision

    return ApplyRevision(
        **{
            "preview_id": preview.preview_id,
            "expected_revision": preview.expected_revision,
            "input_identity": preview.input_identity,
            "leg_mappings": preview.leg_mappings,
            **changes,
        }
    )


def test_revision_reorder_requires_mapping_when_ambiguous(prepared, monkeypatch):
    service, view = prepared
    preview = revision_preview(service, view, monkeypatch)
    assert preview.unresolved_mappings
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.apply_revision(view.mission.id, revision_request(preview))
    assert error.value.status_code == 422
    assert snapshot(service) == before


def explicit_mappings(view, retired=None):
    from app.mission.planning.models import RevisionLegMapping

    return [
        RevisionLegMapping(
            incoming_leg_id=c.leg.id if c.leg.id != retired else "",
            expected_leg_id=c.leg.id,
            action="retire" if c.leg.id == retired else "retain",
        )
        for c in view.expected_legs
    ]


def test_retirement_archives_leg_but_cannot_retire_active_leg(prepared, monkeypatch):
    from app.mission import storage

    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    preview = revision_preview(
        service,
        saved,
        monkeypatch,
        legs=[
            c.leg.model_copy(update={"ordinal": n})
            for n, c in enumerate(saved.expected_legs[1:], 1)
        ],
    )
    request = revision_request(preview, leg_mappings=explicit_mappings(saved, "card-1"))
    installed = storage.load_mission_v2(saved.mission.id).legs[0]
    original = installed.model_copy(deep=True)
    installed.is_active = True
    path = storage.get_mission_leg_file_path(saved.mission.id, installed.id)
    path.write_text(installed.model_dump_json())
    before = snapshot(service)
    with pytest.raises(PlanningFailure) as error:
        service.apply_revision(saved.mission.id, request)
    assert error.value.status_code == 409
    assert snapshot(service) == before
    path.write_text(original.model_dump_json())
    result = service.apply_revision(saved.mission.id, request)
    assert not result.mission.legs
    assert [c.leg.ordinal for c in result.expected_legs] == [1, 2]
    manifest = service.store._load(saved.mission.id)[1]
    archive = next(x for x in manifest.leg_history if x.reason == "retirement")
    assert archive.installed_leg.id == original.id
    assert archive.leg.draft == saved.expected_legs[0].leg.draft
    assert archive.timeline.mission_leg_id == original.id
    assert not path.exists()
    assert all(
        svc_path.exists()
        for svc_path in [service.sources.path(s) for s in manifest.source_revisions]
    )


def test_identical_revision_is_noop_and_lower_revision_needs_override(
    prepared, monkeypatch
):
    service, view = prepared
    same = revision_preview(service, view, monkeypatch, data=b"synthetic pdf")
    assert same.identical_content
    before = service.store.read(view.mission.id)
    assert (
        service.apply_revision(view.mission.id, revision_request(same)).revision
        == before.revision
    )
    preview = revision_preview(service, view, monkeypatch, source_revision=3)
    saved = service.apply_revision(
        view.mission.id, revision_request(preview, leg_mappings=explicit_mappings(view))
    )
    lower = revision_preview(
        service, saved, monkeypatch, source_revision=2, data=b"revision lower"
    )
    assert lower.lower_revision
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.apply_revision(
            view.mission.id,
            revision_request(lower, leg_mappings=explicit_mappings(saved)),
        )
    assert snapshot(service) == before
    accepted = service.apply_revision(
        view.mission.id,
        revision_request(
            lower, leg_mappings=explicit_mappings(saved), allow_lower_revision=True
        ),
    )
    assert accepted.revision == saved.revision + 1


def test_managed_delete_requires_captured_cas_and_retains_source_closure(prepared):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.mission.dependencies import get_poi_manager, get_route_manager
    from app.mission.routes_v2 import router

    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    app.dependency_overrides[get_route_manager] = lambda: service.store.route_manager
    app.dependency_overrides[get_poi_manager] = lambda: service.store.poi_manager
    path = f"/api/v2/missions/{view.mission.id}/legs/{saved.mission.legs[0].id}"
    before = snapshot(service)
    with TestClient(app) as client:
        assert client.delete(path).status_code == 409
        assert snapshot(service) == before
        assert (
            client.delete(
                path,
                params={
                    "expected_revision": saved.revision - 1,
                    "input_identity": saved.expected_legs[0].input_identity,
                },
            ).status_code
            == 409
        )
        assert snapshot(service) == before
        assert (
            client.delete(
                path,
                params={
                    "expected_revision": saved.revision,
                    "input_identity": saved.expected_legs[0].input_identity,
                },
            ).status_code
            == 204
        )
    result = service.store.read(view.mission.id)
    assert result.mission.legs == []
    assert all(c.leg.installed_leg_id is None for c in result.expected_legs)
    manifest = service.store._load(view.mission.id)[1]
    assert (
        next(
            x for x in manifest.leg_history if x.reason == "retirement"
        ).installed_leg.id
        == saved.mission.legs[0].id
    )
    assert all(service.sources.path(s).exists() for s in manifest.source_revisions)


def test_pure_reorder_preserves_review_context_and_stable_ids(prepared, monkeypatch):
    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    old = saved.expected_legs[0]
    incoming = [
        saved.expected_legs[i].leg.model_copy(update={"ordinal": n})
        for n, i in enumerate([2, 1, 0], 1)
    ]
    preview = revision_preview(service, saved, monkeypatch, legs=incoming)
    result = service.apply_revision(
        saved.mission.id,
        revision_request(preview, leg_mappings=explicit_mappings(saved)),
    )
    retained = next(c for c in result.expected_legs if c.leg.id == "card-1")
    assert retained.leg.ordinal == 3
    assert retained.review_status == "reviewed"
    assert retained.leg.review.saved_at == old.leg.review.saved_at
    assert retained.leg.draft.evaluation_context == old.leg.draft.evaluation_context
    assert retained.leg.installed_leg_id == old.leg.installed_leg_id
    assert result.mission.legs[0].id == saved.mission.legs[0].id
    manifest = service.store._load(saved.mission.id)[1]
    assert old.leg.review in manifest.review_records


def test_revision_stale_race_has_no_source_or_installed_writes(prepared, monkeypatch):
    service, view = prepared
    preview = revision_preview(service, view, monkeypatch)
    original = service.sources.acceptance_files
    after = []

    def raced(*args):
        result = original(*args)
        service.store.save_draft(
            view.mission.id,
            "card-1",
            SaveDraft(
                expected_revision=view.revision, draft=view.expected_legs[0].leg.draft
            ),
        )
        after.append(snapshot(service))
        return result

    monkeypatch.setattr(service.sources, "acceptance_files", raced)
    with pytest.raises(PlanningFailure) as error:
        service.apply_revision(
            view.mission.id,
            revision_request(preview, leg_mappings=explicit_mappings(view)),
        )
    assert error.value.status_code == 409
    assert snapshot(service) == after[0]


def test_retirement_rollback_preserves_plan_timeline_pois_and_sources(
    prepared, monkeypatch
):
    from app.mission.planning import journal

    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    before = snapshot(service)
    pois = service.store.poi_manager.pois_file.read_bytes()
    original = journal.replace_scope
    failed = []

    def interrupted(*args):
        original(*args)
        if not failed:
            failed.append(True)
            raise OSError("Synthetic commit interruption")

    monkeypatch.setattr(journal, "replace_scope", interrupted)
    with pytest.raises(OSError):
        service.retire_managed_leg(
            view.mission.id,
            saved.mission.legs[0].id,
            saved.revision,
            saved.expected_legs[0].input_identity,
        )
    assert snapshot(service) == before
    assert service.store.poi_manager.pois_file.read_bytes() == pois


def test_changed_source_ar_requires_named_resolution_and_retry_does_not_duplicate(
    prepared, monkeypatch
):
    from app.mission.planning.models import ItineraryAR

    service, view = prepared
    mission, manifest = service.store._load(view.mission.id)
    row = ItineraryAR(
        id="ar-stable",
        track="Synthetic AR",
        entry_time="2026-10-25T12:10:00Z",
        exit_time="2026-10-25T12:20:00Z",
        source_time_precision="minute",
        source_altitude=240,
    )
    manifest.expected_legs[0].ar_rows = [row]
    manifest.expected_legs[0].draft.ar_corrections = [
        row.model_copy(
            update={"source_altitude": 250, "confirmed_units": "flight_level"}
        )
    ]
    manifest.itinerary_baseline.expected_legs[0].ar_rows = [row]
    view = service.store.persist(mission, manifest)
    incoming = [c.leg.model_copy(deep=True) for c in view.expected_legs]
    incoming[0].ar_rows = [
        ItineraryAR.model_validate(
            {**row.model_dump(), "id": "new-ar", "source_altitude": 260}
        )
    ]
    preview = revision_preview(service, view, monkeypatch, legs=incoming)
    assert [
        (change.before, change.after)
        for change in preview.changes
        if change.field == "AR Synthetic AR source_altitude"
        and change.expected_leg_id == "card-1"
    ] == [("240.0", "260.0")]
    request = revision_request(preview, leg_mappings=explicit_mappings(view))
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.apply_revision(view.mission.id, request)
    assert snapshot(service) == before
    from app.mission.planning.models import CorrectionResolution

    request.correction_resolutions = [
        CorrectionResolution(conflict_id="card-1:card-1:ar:ar-stable", action="retain")
    ]
    from app.mission.planning.models import ApplyRevision

    request = ApplyRevision.model_validate(request.model_dump())
    saved = service.apply_revision(view.mission.id, request)
    corrected = saved.expected_legs[0].leg.draft.ar_corrections
    assert (
        len(corrected) == 1
        and corrected[0].id == "ar-stable"
        and corrected[0].source_altitude == 250
    )
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.apply_revision(view.mission.id, request)
    assert snapshot(service) == before


def test_revision_baseline_keeps_raw_source_separate_from_accepted_corrections(
    prepared, monkeypatch
):
    service, view = prepared
    preview = revision_preview(service, view, monkeypatch)
    correction = preview.parsed_values.model_copy(deep=True)
    correction.expected_legs[0].departure_airport = "CORRECTED"
    request = revision_request(
        preview, leg_mappings=explicit_mappings(view), itinerary=correction
    )
    saved = service.apply_revision(view.mission.id, request)
    baseline = service.store._load(view.mission.id)[1].itinerary_baseline
    assert saved.expected_legs[0].leg.departure_airport == "CORRECTED"
    assert (
        baseline.expected_legs[0].departure_airport
        == preview.parsed_values.expected_legs[0].departure_airport
    )


def test_managed_legacy_route_upload_stages_without_replacing_installed_plan(
    prepared, tmp_path
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.mission.dependencies import get_poi_manager, get_route_manager
    from app.mission.routes_v2 import router

    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    app.dependency_overrides[get_route_manager] = lambda: service.store.route_manager
    app.dependency_overrides[get_poi_manager] = lambda: service.store.poi_manager
    path = f"/api/v2/missions/{view.mission.id}/legs/{saved.mission.legs[0].id}/route"
    with TestClient(app) as client:
        before = snapshot(service)
        missing = client.put(
            path,
            files={"file": ("replacement.kml", kml_fixture(tmp_path).read_bytes())},
        )
        assert missing.status_code == 409
        assert snapshot(service) == before
        staged = client.put(
            path,
            params={"expected_revision": saved.revision},
            files={"file": ("replacement.kml", kml_fixture(tmp_path).read_bytes())},
        )
        assert (
            staged.status_code == 200
            and staged.json()["expected_revision"] == saved.revision
        )
    assert service.store.read(view.mission.id) == saved


def test_unchanged_ar_evidence_keeps_review_identity(prepared, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app.mission.planning.models import ItineraryAR, ItineraryPreview
    from app.mission.planning.revisions import preview_revision as diff
    from app.mission.planning.revisions import reconcile
    from app.mission.planning.store import leg_identity

    service, view = prepared
    _, manifest = service.store._load(view.mission.id)
    row = ItineraryAR(
        id="ar",
        track="SYNTH",
        entry_time="2026-10-25T12:10:00Z",
        exit_time="2026-10-25T12:20:00Z",
        source_time_precision="minute",
        source_page=1,
        source_text="old layout",
    )
    manifest.expected_legs[0].ar_rows = [row]
    manifest.itinerary_baseline.expected_legs[0].ar_rows = [row]
    old_identity = leg_identity(manifest.expected_legs[0])
    incoming = manifest.itinerary_baseline.model_copy(deep=True)
    incoming.expected_legs[0].ar_rows = [
        row.model_copy(
            update={"id": "new", "source_page": 2, "source_text": "new layout"}
        )
    ]
    preview = diff(
        manifest,
        ItineraryPreview(
            preview_id="p",
            parsed_values=incoming,
            confirmable=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )
    revised = reconcile(
        manifest,
        preview,
        revision_request(preview, leg_mappings=explicit_mappings(view)),
    )
    assert leg_identity(revised.expected_legs[0]) == old_identity
    assert revised.itinerary_baseline.expected_legs[0].ar_rows[0].source_page == 2


def test_retired_history_ids_never_reappear_as_unmanaged_order(prepared):
    from app.mission.planning.order import project_leg_order

    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    installed = saved.mission.legs[0].id
    service.retire_managed_leg(
        view.mission.id,
        installed,
        saved.revision,
        saved.expected_legs[0].input_identity,
    )
    manifest = service.store._load(view.mission.id)[1]
    assert project_leg_order(manifest, (installed,)).executable_ids == ()


def test_accepted_replacement_only_reviewed_save_installs_new_route(prepared, tmp_path):
    service, view = confirmed(prepared)
    service.save_reviewed(view.mission.id, "card-1", review(view))
    saved = service.store.read(view.mission.id)
    preview = replacement(service, saved, tmp_path)
    accepted = accept(service, saved, preview)
    assert accepted.mission.legs[0].route_id == saved.mission.legs[0].route_id
    installed = service.save_reviewed(view.mission.id, "card-1", review(accepted))
    assert installed.mission.legs[0].id == saved.mission.legs[0].id
    assert installed.mission.legs[0].route_id == preview.binding.route_id
    assert service.sources.path(
        service.store._load(view.mission.id)[1].source_revisions[1]
    ).exists()


def test_revision_http_uses_real_synthetic_pdf_and_typed_private_source_separation(
    prepared,
):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.mission.planning.routes import router

    from .test_extract import synthetic_pdf

    service, view = prepared
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    path = f"/api/v2/missions/planning/missions/{view.mission.id}"
    with TestClient(app) as client:
        result = client.post(
            path + "/itinerary-previews",
            data={"expected_revision": view.revision},
            files={"file": ("synthetic.pdf", synthetic_pdf())},
        )
        assert result.status_code == 200, result.text
        assert "owned_relative_path" not in result.text
        preview = result.json()
        assert preview["parsed_values"]["expected_legs"]
        request = {
            "preview_id": preview["preview_id"],
            "expected_revision": view.revision,
            "input_identity": preview["input_identity"],
            "leg_mappings": [],
        }
        before = snapshot(service)
        invalid = client.post(path + "/revision", json=request)
        assert invalid.status_code == 422
        assert snapshot(service) == before
        request["expected_revision"] -= 1
        assert client.post(path + "/revision", json=request).status_code == 409
        assert snapshot(service) == before


def test_historical_missing_baseline_requires_explicit_uncertainty_acknowledgement(
    prepared, monkeypatch
):
    from app.mission.planning.models import CorrectionResolution, PlanningManifest

    service, view = prepared
    mission, manifest = service.store._load(view.mission.id)
    historical = manifest.storage_record()
    historical.pop("itinerary_baseline")
    historical.pop("leg_history")
    manifest = PlanningManifest.model_validate(historical)
    assert manifest.itinerary_baseline is None and manifest.leg_history == []
    view = service.store.persist(mission, manifest)
    preview = revision_preview(service, view, monkeypatch)
    assert preview.previous_source_revision is None
    selected = [
        issue
        for issue in preview.conflicts
        if issue.id == f"{issue.expected_leg_id}:{issue.expected_leg_id}:baseline"
    ]
    assert len(selected) == len(view.expected_legs)
    assert all(issue.allowed_actions == ["retain"] for issue in selected)
    request = revision_request(preview, leg_mappings=explicit_mappings(view))
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.apply_revision(view.mission.id, request)
    assert snapshot(service) == before
    request.correction_resolutions = [
        CorrectionResolution(conflict_id=issue.id, action="retain")
        for issue in selected
    ]
    saved = service.apply_revision(view.mission.id, request)
    assert [card.leg.draft for card in saved.expected_legs] == [
        card.leg.draft for card in view.expected_legs
    ]
    assert [card.leg.id for card in saved.expected_legs] == [
        card.leg.id for card in view.expected_legs
    ]


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_pdf_ar_occurrences_never_guess_correction_owner(service, reverse):
    from io import BytesIO

    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import DecodedStreamObject, NameObject

    from app.mission.planning.models import ConfirmItinerary, CorrectionResolution
    from app.mission.planning.revisions import row_pairs

    from .test_extract import synthetic_pdf

    original = service.preview_itinerary(synthetic_pdf(), "synthetic.pdf")
    view = service.create(
        ConfirmItinerary(
            preview_id=original.preview_id,
            itinerary=original.parsed_values,
            idempotency_key="duplicate-occurrence",
        )
    )
    card = view.expected_legs[0]
    draft = card.leg.draft.model_copy(deep=True)
    draft.ar_corrections = [r.model_copy(deep=True) for r in card.leg.ar_rows]
    old = draft.ar_corrections[0]
    old.source_altitude = 250
    old.confirmed_units = "flight_level"
    old.confirmed = True
    view = service.store.save_draft(
        view.mission.id,
        card.leg.id,
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    writer = PdfWriter(clone_from=PdfReader(BytesIO(synthetic_pdf())))
    page = writer.pages[0]
    data = page["/Contents"].get_data().replace(b"(GRIZZ-W)", b"(AR106LW)")
    data = data.replace(b"(19:20Z)", b"(14:26Z)").replace(b"(20:33Z)", b"(15:23Z)")
    stream = DecodedStreamObject()
    stream.set_data(data)
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    preview = service.preview_revision(
        view.mission.id, output.getvalue(), view.revision
    )
    assert preview.confirmable and not preview.field_errors
    incoming = preview.parsed_values.expected_legs[0]
    if reverse:
        incoming.ar_rows.reverse()
    pairs, removed = row_pairs(card.leg.ar_rows, incoming.ar_rows)
    assert old.id in {r.id for r in removed}
    assert all(prior is None for prior, row in pairs if row.track == old.track)
    mappings = {
        (m.expected_leg_id, m.incoming_leg_id)
        for m in preview.leg_mappings
        if m.action == "retain"
    }
    conflicts = [
        c
        for c in preview.conflicts
        if any(c.id.startswith(f"{o}:{i}:") for o, i in mappings)
    ]
    assert any(
        c.row_id == old.id and c.allowed_actions == ["retain", "remove"]
        for c in conflicts
    )
    request = revision_request(preview)
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.apply_revision(view.mission.id, request)
    assert snapshot(service) == before
    request.correction_resolutions = [
        CorrectionResolution(conflict_id=c.id, action="retain") for c in conflicts
    ]
    # Corrected extraction may reorder rows, but cannot decide their old occurrence IDs.
    request.itinerary = preview.parsed_values
    saved = service.apply_revision(view.mission.id, request)
    rows = saved.expected_legs[0].leg.draft.ar_corrections
    kept = next(r for r in rows if r.id == old.id)
    assert kept.source_altitude == 250 and kept.confirmed_units == "flight_level"
    assert not kept.confirmed
    new = [r for r in rows if r.track == old.track and r.id != old.id]
    assert len(new) == 2 and len({r.id for r in rows}) == len(rows)
    assert all(not r.confirmed and r.confirmed_units is None for r in new)
    before = snapshot(service)
    with pytest.raises(PlanningFailure):
        service.apply_revision(view.mission.id, request)
    assert snapshot(service) == before


@pytest.mark.parametrize("source_changed", [False, True])
def test_revision_three_way_metadata_preserves_or_resolves_accepted_corrections(
    prepared, monkeypatch, source_changed
):
    from app.mission.planning.models import CorrectionResolution

    service, view = prepared
    mission, manifest = service.store._load(view.mission.id)
    manifest.itinerary_baseline.name = "Original source"
    manifest.itinerary_baseline.aircraft = "Source aircraft"
    manifest.itinerary_baseline.call_sign = "Source call"
    mission.name = "Operator mission"
    mission.metadata["itinerary"] = {
        "name": mission.name,
        "aircraft": "Operator aircraft",
        "call_sign": "Operator call",
        "itinerary_revision": 1,
    }
    view = service.store.persist(mission, manifest)
    raw = manifest.itinerary_baseline.model_copy(deep=True)
    raw.itinerary_revision = 2
    if source_changed:
        raw.name = "Changed source"
        raw.aircraft = "Changed aircraft"
        raw.call_sign = "Changed call"
    from datetime import datetime, timezone

    from app.mission.planning.models import ItineraryPreview

    monkeypatch.setattr(
        "app.mission.planning.service.extract_itinerary",
        lambda _: ItineraryPreview(
            preview_id="source",
            parsed_values=raw,
            confirmable=True,
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ),
    )
    preview = service.preview_revision(
        view.mission.id, b"metadata source revision", view.revision
    )
    assert preview.accepted_metadata.name == "Operator mission"
    issues = [c for c in preview.conflicts if c.expected_leg_id is None]
    request = revision_request(preview, leg_mappings=explicit_mappings(view))
    if source_changed:
        assert {c.field for c in issues} == {"name", "aircraft", "call_sign"}
        assert all(c.allowed_actions == ["retain", "use_source"] for c in issues)
        assert {
            (c.field, c.before, c.after)
            for c in preview.changes
            if c.expected_leg_id is None and c.field != "itinerary_revision"
        } == {
            ("name", "Operator mission", "Changed source"),
            ("aircraft", "Operator aircraft", "Changed aircraft"),
            ("call_sign", "Operator call", "Changed call"),
        }
        before = snapshot(service)
        with pytest.raises(PlanningFailure):
            service.apply_revision(view.mission.id, request)
        assert snapshot(service) == before
        request.correction_resolutions = [
            CorrectionResolution(
                conflict_id=c.id,
                action="use_source" if c.field == "aircraft" else "retain",
            )
            for c in issues
        ]
    else:
        assert not issues
    saved = service.apply_revision(view.mission.id, request)
    assert saved.mission.name == "Operator mission"
    assert saved.mission.metadata["itinerary"]["aircraft"] == (
        "Changed aircraft" if source_changed else "Operator aircraft"
    )
    assert saved.mission.metadata["itinerary"]["call_sign"] == "Operator call"
    baseline = service.store._load(view.mission.id)[1].itinerary_baseline
    assert (baseline.name, baseline.aircraft, baseline.call_sign) == (
        raw.name,
        raw.aircraft,
        raw.call_sign,
    )


@pytest.mark.parametrize("changed_field", ["source_altitude", "entry_time"])
@pytest.mark.parametrize("excluded", [False, True])
@pytest.mark.parametrize("accepted_source_matches", [False, True])
def test_use_source_merges_only_changed_ar_fields_into_saved_operator_data(
    prepared, monkeypatch, changed_field, excluded, accepted_source_matches
):
    from app.mission.planning.models import CorrectionResolution, ItineraryAR

    service, view = prepared
    route = service.store.route_manager.get_route(
        view.expected_legs[0].leg.route.route_id
    )
    start = _candidates(route.points[1].expected_arrival_time, "second", route)[0]
    end = _candidates(route.points[3].expected_arrival_time, "second", route)[0]
    row = ItineraryAR(
        id="old-ar",
        track="SYNTH",
        entry_time=start.source_time,
        exit_time=end.source_time,
        source_time_precision="second",
        source_altitude=210,
    )
    untouched = row.model_copy(update={"id": "untouched", "track": "OTHER"}, deep=True)
    mission, manifest = service.store._load(view.mission.id)
    for leg in (
        manifest.expected_legs[0],
        manifest.itinerary_baseline.expected_legs[0],
    ):
        leg.departure_time = route.points[0].expected_arrival_time
        leg.arrival_time = route.points[-1].expected_arrival_time
    new_value = (
        220.0
        if changed_field == "source_altitude"
        else row.entry_time + timedelta(seconds=60)
    )
    manifest.expected_legs[0].ar_rows = [
        (
            row.model_copy(update={changed_field: new_value}, deep=True)
            if accepted_source_matches
            else row
        ),
        untouched,
    ]
    manifest.itinerary_baseline.expected_legs[0].ar_rows = [row, untouched]
    view = service.store.persist(mission, manifest)
    draft = view.expected_legs[0].leg.draft.model_copy(deep=True)
    corrected = row.model_copy(
        update={
            "source_altitude": 250.0,
            "confirmed_units": "flight_level",
            "start_anchor": start,
            "end_anchor": end,
            "match_status": "excluded" if excluded else "matched",
            "exclusion_note": "Operator decision retained",
            "confirmed": True,
        },
        deep=True,
    )
    other = untouched.model_copy(
        update={
            "confirmed_units": "feet",
            "start_anchor": start,
            "end_anchor": end,
            "match_status": "matched",
            "confirmed": True,
        },
        deep=True,
    )
    draft.ar_corrections = [corrected, other]
    draft.swaps = [
        AnchoredSwap(id="manual-swap", target_satellite_id="WEST", anchor=start)
    ]
    draft.locks = [
        PlanningLock(
            id="manual-lock",
            swap_id="manual-swap",
            target_satellite_id="WEST",
            anchor=start,
        )
    ]
    view = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=view.revision, draft=draft),
    )
    incoming = [c.leg.model_copy(deep=True) for c in view.expected_legs]
    incoming[0].ar_rows[0] = row.model_copy(
        update={changed_field: new_value}, deep=True
    )
    preview = revision_preview(service, view, monkeypatch, legs=incoming)
    request = revision_request(
        preview,
        leg_mappings=explicit_mappings(view),
        correction_resolutions=[
            CorrectionResolution(
                conflict_id="card-1:card-1:ar:old-ar", action="use_source"
            )
        ],
    )
    saved = service.apply_revision(view.mission.id, request)
    final = saved.expected_legs[0].leg.draft
    result = next(r for r in final.ar_corrections if r.id == row.id)
    assert result.confirmed_units == "flight_level"
    assert result.exclusion_note == corrected.exclusion_note
    assert not result.confirmed
    assert result.end_anchor == end
    if changed_field == "source_altitude":
        assert result.source_altitude == 220 and result.start_anchor == start
        assert result.entry_time == corrected.entry_time
        assert result.match_status == corrected.match_status
    else:
        assert result.entry_time == new_value and result.source_altitude == 250
        assert result.start_anchor is None
        assert result.match_status == ("excluded" if excluded else "unresolved")
    assert next(r for r in final.ar_corrections if r.id == other.id) == other
    assert final.swaps == draft.swaps and final.locks == draft.locks
