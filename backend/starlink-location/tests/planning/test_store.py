"""Durable drafts and atomic publication, using owned stores only."""

from types import SimpleNamespace

import pytest
from app.mission import storage
from app.mission.models import MissionLeg, MissionLegTimeline, TransportConfig
from app.mission.planning.models import (
    AcceptRouteBinding,
    ConfirmItinerary,
    ExpectedLeg,
    ItineraryData,
    ItineraryPreview,
    PlanningDraft,
    SaveDraft,
    SaveReviewed,
)
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

from .cases import expected_leg_fields
from .test_match import kml_fixture


@pytest.fixture
def service(tmp_path, monkeypatch):
    from app.mission.planning.service import PlanningService
    from app.mission.planning.store import PlanningStore

    manager = RouteManager(tmp_path / "routes")
    store = PlanningStore(
        tmp_path / "missions", manager, POIManager(tmp_path / "pois.json")
    )
    return PlanningService(store)


def create(service, key="create-one"):
    source = service.sources.stage(b"synthetic pdf", "pdf", None, "same.pdf")
    data = ItineraryData(
        name="Synthetic",
        expected_legs=[
            ExpectedLeg(**expected_leg_fields(id=f"card-{n}", ordinal=n))
            for n in (1, 2, 3)
        ],
    )
    preview = ItineraryPreview(
        preview_id=source.id,
        parsed_values=data,
        source=source,
        confirmable=True,
        expires_at=source.expires_at,
    )
    service.sources.save_preview(
        preview.preview_id,
        {
            "kind": "itinerary",
            "preview": preview.model_dump(mode="json"),
            "source": source.storage_record(),
        },
    )
    request = ConfirmItinerary(
        preview_id=preview.preview_id, itinerary=data, idempotency_key=key
    )
    return service.create(request), request


def test_confirm_creates_expected_cards_not_executable_legs(service):
    view, _ = create(service)
    assert view.mission.legs == [] and len(view.expected_legs) == 3
    assert view.revision == 1
    assert "satellite_access_required" in {e.code for e in view.errors}
    assert "owned_relative_path" not in view.model_dump_json()
    stored = storage.load_mission_v2(view.mission.id)
    assert stored.metadata["itinerary_planning"]["source_revisions"][0][
        "owned_relative_path"
    ]


def test_idempotent_create_and_expired_preview(service):
    from app.mission.planning.errors import PlanningFailure

    view, request = create(service)
    assert service.create(request).mission.id == view.mission.id
    _, expired = create(service, "other")
    # Another key cannot replay a consumed preview.
    expired.idempotency_key = "third"
    with pytest.raises(PlanningFailure) as exc:
        service.create(expired)
    assert exc.value.status_code == 409


def test_two_tabs_stale_save_has_no_writes(service):
    from app.mission.planning.errors import PlanningFailure

    view, _ = create(service)
    saved = service.store.save_draft(
        view.mission.id,
        "card-1",
        SaveDraft(expected_revision=1, draft=PlanningDraft(starshield_enabled=False)),
    )
    before = {
        str(p): p.read_bytes()
        for p in service.store.root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with pytest.raises(PlanningFailure) as exc:
        service.store.save_draft(
            view.mission.id,
            "card-1",
            SaveDraft(expected_revision=1, draft=PlanningDraft()),
        )
    assert exc.value.status_code == 409
    assert before == {
        str(p): p.read_bytes()
        for p in service.store.root.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    assert service.store.read(view.mission.id) == saved


def test_accept_upload_assigns_selected_leg_not_filename(service, tmp_path):
    view, _ = create(service)
    data = kml_fixture(tmp_path).read_bytes()
    preview = service.preview_route(
        view.mission.id, "card-3", data, 1, filename="card-1.kml"
    )
    accepted = service.accept_route(
        view.mission.id,
        "card-3",
        AcceptRouteBinding(
            expected_revision=1,
            preview_id=preview.preview_id,
            discrepancy_acknowledgments=[e.code for e in preview.discrepancy_errors],
        ),
    )
    assert accepted.expected_legs[0].leg.route is None
    binding = accepted.expected_legs[2].leg.route
    assert (
        binding.route_id != "card-1"
        and binding.content_hash == preview.binding.content_hash
    )
    assert accepted.mission.legs == []
    assert accepted.expected_legs[2].review_status == "needs_review"
    manager = RouteManager(
        service.store.route_manager.routes_dir,
        profile_resolver=service.sources.resolve_profile,
    )
    manager._load_existing_routes()
    assert manager.get_route(binding.route_id).ingestion_profile == "planning_v1"
    service.sources.descriptor_path(binding.route_id).unlink()
    manager._load_route_file(str(manager.routes_dir / f"{binding.route_id}.kml"))
    assert manager.get_route(binding.route_id) is None


def test_parent_write_preserves_server_manifest_and_other_metadata(service):
    view, _ = create(service)
    parent = storage.load_mission_v2(view.mission.id)
    original = parent.metadata["itinerary_planning"]
    parent.metadata = {
        "unrelated": {"value": 9},
        "itinerary_planning": {"revision": 999},
    }
    storage.save_mission_v2(parent)
    stored = storage.load_mission_v2(parent.id)
    assert stored.metadata["itinerary_planning"] == original
    assert stored.metadata["unrelated"] == {"value": 9}


def bind(service, tmp_path, card="card-1", revision=1):
    view = service.store.read(
        next(
            path.name
            for path in service.store.root.iterdir()
            if (path / "mission.json").exists()
        )
    )
    preview = service.preview_route(
        view.mission.id, card, kml_fixture(tmp_path).read_bytes(), revision
    )
    return service.accept_route(
        view.mission.id,
        card,
        AcceptRouteBinding(
            expected_revision=revision,
            preview_id=preview.preview_id,
            discrepancy_acknowledgments=[e.code for e in preview.discrepancy_errors],
        ),
    )


def artifacts_for(view, card="card-1", installed_id="installed"):
    from app.mission.timeline_preparation import TimelineArtifacts
    from app.models.poi import POICreate

    leg = next(c.leg for c in view.expected_legs if c.leg.id == card)
    installed = MissionLeg(
        id=installed_id,
        name="Synthetic",
        route_id=leg.route.route_id,
        transports=TransportConfig(initial_x_satellite_id="X-1"),
    )
    return TimelineArtifacts(
        route=SimpleNamespace(
            route_id=leg.route.route_id, content_hash=leg.route.content_hash
        ),
        projector=None,
        events=(),
        timeline=MissionLegTimeline(mission_leg_id=installed_id),
        summary=None,
        generated_pois=(
            POICreate(
                name="owned",
                latitude=0,
                longitude=0,
                mission_id=view.mission.id,
                route_id=leg.route.route_id,
                kind="departure",
            ),
        ),
        validated_leg=installed,
    )


@pytest.mark.parametrize("failure_index", [0, 1, 2, 3])
def test_transaction_failure_and_restart_restore_owned_state(
    service, tmp_path, monkeypatch, failure_index
):
    from app.mission.planning import journal

    create(service)
    before = bind(service, tmp_path)
    # Unrelated manual markers must survive rollback and restart.
    from app.models.poi import POICreate

    manual = service.store.poi_manager.create_poi(
        POICreate(name="manual", latitude=1, longitude=1)
    )
    actual = journal.atomic_write
    count = 0

    class Interrupted(BaseException):
        pass

    def interrupt(path, data):
        nonlocal count
        actual(path, data)
        if "journals" not in path.parts and data is not None:
            if count == failure_index:
                raise Interrupted()
            count += 1

    monkeypatch.setattr(journal, "atomic_write", interrupt)
    request = SaveReviewed(
        expected_revision=before.revision,
        input_identity=before.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    with pytest.raises(Interrupted):
        service.store.commit_reviewed(
            before.mission.id, "card-1", request, artifacts_for(before)
        )
    monkeypatch.setattr(journal, "atomic_write", actual)
    # Simulate an unrelated durable writer after interruption, before restart.
    import json

    raw = json.loads(service.store.poi_manager.pois_file.read_bytes())
    foreign = manual.model_copy(update={"id": "foreign-after-crash", "name": "foreign"})
    raw["pois"][foreign.id] = foreign.model_dump(mode="json")
    service.store.poi_manager.pois_file.write_text(json.dumps(raw))
    service.store.recover()
    assert service.store.poi_manager.get_poi(foreign.id) == foreign
    assert service.store.read(before.mission.id) == before
    assert service.store.poi_manager.get_poi(manual.id) == manual
    assert storage.load_mission_timeline("installed", before.mission.id) is None
    assert not list(service.store.journal.directory.glob("*.json"))


def test_review_three_before_one_full_and_stub_load_follow_ordinals(service, tmp_path):
    create(service)
    view = bind(service, tmp_path, "card-3")
    req = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[2].input_identity,
        satellite_plan_confirmed=True,
    )
    service.store.commit_reviewed(
        view.mission.id, "card-3", req, artifacts_for(view, "card-3", "a-leg3")
    )
    view = bind(service, tmp_path, "card-1", 3)
    req = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    service.store.commit_reviewed(
        view.mission.id, "card-1", req, artifacts_for(view, "card-1", "z-leg1")
    )
    for loader in (storage.load_mission_v2, storage.load_mission_metadata_v2):
        mission = loader(view.mission.id)
        assert [leg.id for leg in mission.legs] == ["z-leg1", "a-leg3"]
        order = storage.mission_leg_order(mission)
        assert list(order.numbers.values()) == [1, 3]
        assert order.total_count == 3


def test_manifest_readers_block_during_partial_commit(service, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from app.mission.planning import journal

    create(service)
    before = bind(service, tmp_path)
    written, release, reader_started, reader_done = Event(), Event(), Event(), Event()
    actual = journal.atomic_write

    def pause(path, data):
        actual(path, data)
        if path.name == "mission.json":
            written.set()
            assert release.wait(3)

    monkeypatch.setattr(journal, "atomic_write", pause)

    def read_snapshot():
        reader_started.set()
        with storage.get_active_leg_lock():
            mission = storage.load_mission_v2(before.mission.id)
            timeline = storage.load_mission_timeline("installed", before.mission.id)
            pois = service.store.poi_manager.list_pois(mission_id=before.mission.id)
            from app.mission.slide_cache.persisted_pois import PersistedPOIs

            assert len(PersistedPOIs(service.store.poi_manager).list_pois()) == len(
                pois
            )
        reader_done.set()
        return mission, timeline, pois

    request = SaveReviewed(
        expected_revision=before.revision,
        input_identity=before.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    with ThreadPoolExecutor(2) as workers:
        writer = workers.submit(
            service.store.commit_reviewed,
            before.mission.id,
            "card-1",
            request,
            artifacts_for(before),
        )
        try:
            assert written.wait(3)
            reader = workers.submit(read_snapshot)
            assert reader_started.wait(1)
            assert not reader_done.wait(0.15)
        finally:
            release.set()
        writer.result(timeout=3)
        mission, timeline, pois = reader.result(timeout=3)
    assert [leg.id for leg in mission.legs] == ["installed"]
    assert timeline.mission_leg_id == "installed"
    assert [poi.name for poi in pois] == ["owned"]


def test_unrecovered_journal_blocks_legacy_readers(service):
    view, _ = create(service)
    journal = service.store.journal.directory / "broken.json"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text('{"version":999}')
    for read in (
        lambda: storage.load_mission_v2(view.mission.id),
        lambda: storage.load_mission_timeline("none", view.mission.id),
        lambda: service.store.poi_manager.list_pois(),
    ):
        with pytest.raises(RuntimeError, match="recovery"):
            read()
    journal.unlink()


def test_actual_expiry_removes_only_staged_owned_source(service):
    from datetime import datetime, timedelta, timezone

    from app.mission.planning.errors import PlanningFailure

    source = service.sources.stage(b"synthetic", "pdf", None, "same.pdf")
    source = source.model_copy(
        update={"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    service.sources.save_preview(
        source.id, {"kind": "itinerary", "source": source.storage_record()}
    )
    unrelated = service.sources.stage(b"other", "pdf", None, "same.pdf")
    with pytest.raises(PlanningFailure) as caught:
        service.sources.get_preview(source.id)
    assert caught.value.status_code == 409
    assert caught.value.error.action == "reupload"
    assert not service.sources.path(source).exists()
    assert service.sources.path(unrelated).read_bytes() == b"other"


def test_invalid_selected_satellite_fails_without_mission_write(service):
    from app.mission.planning.errors import PlanningFailure

    _, request = create(service)
    request.idempotency_key = "invalid-satellite"
    request.permitted_satellite_ids = ("missing",)
    with pytest.raises(PlanningFailure) as caught:
        service.create(request)
    assert caught.value.status_code == 422
    assert len(storage.list_mission_metadata_v2()) == 1


def test_active_installed_reference_blocks_draft_write(service, tmp_path):
    from app.mission.planning.errors import PlanningFailure

    create(service)
    view = bind(service, tmp_path)
    request = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    view = service.store.commit_reviewed(
        view.mission.id, "card-1", request, artifacts_for(view)
    )
    parent = storage.load_mission_v2(view.mission.id)
    parent.legs[0].is_active = True
    storage.save_mission_v2(parent)
    with pytest.raises(PlanningFailure) as caught:
        service.store.save_draft(
            view.mission.id,
            "card-1",
            SaveDraft(expected_revision=view.revision, draft=PlanningDraft()),
        )
    assert caught.value.status_code == 409
    assert service.store.read(view.mission.id).revision == view.revision


def test_owned_profile_tampering_evicts_previously_cached_route(service, tmp_path):
    import json

    create(service)
    view = bind(service, tmp_path)
    route_id = view.expected_legs[0].leg.route.route_id
    assert service.store.route_manager.get_route(route_id) is not None
    descriptor = service.sources.descriptor_path(route_id)
    record = json.loads(descriptor.read_bytes())
    record["ingestion_profile"] = "legacy"
    descriptor.write_text(json.dumps(record))
    assert service.store.route_manager.get_route(route_id) is None


def test_route_parse_runs_outside_persistence_lock(service, tmp_path, monkeypatch):
    from app.mission.planning import service as service_module

    view, _ = create(service)
    bounded = service_module.run_bounded

    def checked_parse(*args):
        assert not storage.get_active_leg_lock().is_locked
        return bounded(*args)

    monkeypatch.setattr(service_module, "run_bounded", checked_parse)
    service.preview_route(
        view.mission.id, "card-1", kml_fixture(tmp_path).read_bytes(), view.revision
    )


def test_reviewed_route_replacement_removes_only_prior_generated_scope(
    service, tmp_path
):
    from app.models.poi import POICreate

    create(service)
    view = bind(service, tmp_path)
    request = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    view = service.store.commit_reviewed(
        view.mission.id, "card-1", request, artifacts_for(view)
    )
    previous_route = view.expected_legs[0].leg.route.route_id
    manual = service.store.poi_manager.create_poi(
        POICreate(
            name="manual",
            latitude=1,
            longitude=1,
            mission_id=view.mission.id,
            route_id=previous_route,
        )
    )
    view = bind(service, tmp_path, revision=view.revision)
    request = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    service.store.commit_reviewed(
        view.mission.id, "card-1", request, artifacts_for(view)
    )
    pois = service.store.poi_manager.list_pois(mission_id=view.mission.id)
    assert len([poi for poi in pois if poi.generated_source == "mission-timeline"]) == 1
    assert service.store.poi_manager.get_poi(manual.id) == manual


def test_shared_installed_route_scope_rejected_before_writes(service, tmp_path):
    from app.mission.planning.errors import PlanningFailure

    create(service)
    view = bind(service, tmp_path)
    artifacts = artifacts_for(view)
    parent = storage.load_mission_v2(view.mission.id)
    parent.legs.append(artifacts.validated_leg.model_copy(update={"id": "another-leg"}))
    storage.save_mission_v2(parent)
    before = service.store.read(view.mission.id)
    request = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    with pytest.raises(PlanningFailure) as caught:
        service.store.commit_reviewed(view.mission.id, "card-1", request, artifacts)
    assert caught.value.status_code == 409
    assert service.store.read(view.mission.id) == before


def test_second_poi_manager_reads_and_writes_committed_scope(service, tmp_path):
    from app.models.poi import POICreate

    create(service)
    view = bind(service, tmp_path)
    second = POIManager(service.store.poi_manager.pois_file)
    request = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    service.store.commit_reviewed(
        view.mission.id, "card-1", request, artifacts_for(view)
    )
    assert len(second.list_pois(mission_id=view.mission.id)) == 1
    second.create_poi(POICreate(name="foreign-new", latitude=1, longitude=2))
    assert len(service.store.poi_manager.list_pois()) == 2


def test_reviewed_marker_retains_occurrence_geometry_provenance(service, tmp_path):
    from dataclasses import replace

    from app.services.poi.manager import _route_geometry_hash

    create(service)
    view = bind(service, tmp_path)
    artifacts = artifacts_for(view)
    route = service.store.route_manager.get_route(
        view.expected_legs[0].leg.route.route_id
    )
    artifacts = replace(artifacts, route=route)
    artifacts.generated_pois[0]._route_segment_index = 2
    artifacts.generated_pois[0].longitude = 1
    artifacts.generated_pois[0].kind = "x_band_warning_start"
    request = SaveReviewed(
        expected_revision=view.revision,
        input_identity=view.expected_legs[0].input_identity,
        satellite_plan_confirmed=True,
    )
    service.store.commit_reviewed(view.mission.id, "card-1", request, artifacts)
    service.store.poi_manager.reload_pois()
    marker = service.store.poi_manager.list_pois(mission_id=view.mission.id)[0]
    assert marker.planned_route_segment_index == 2
    assert marker.planned_route_geometry_hash == _route_geometry_hash(route)
    service.store.poi_manager.calculate_poi_projections(route)
    projected = service.store.poi_manager.get_poi(marker.id)
    assert projected.projected_waypoint_index == 2


def test_unknown_preview_is_404_while_expired_preview_remains_409(service):
    from datetime import datetime, timedelta, timezone
    from uuid import uuid4

    from app.mission.planning.errors import PlanningFailure

    with pytest.raises(PlanningFailure) as missing:
        service.sources.get_preview(str(uuid4()))
    assert missing.value.status_code == 404
    source = service.sources.stage(b"synthetic", "pdf", None, "test.pdf")
    source = source.model_copy(
        update={"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    service.sources.save_preview(
        source.id, {"kind": "itinerary", "source": source.storage_record()}
    )
    for _ in range(2):
        with pytest.raises(PlanningFailure) as expired:
            service.sources.get_preview(source.id)
        assert expired.value.status_code == 409
        assert expired.value.error.action == "reupload"
    assert not service.sources.path(source).exists()
