"""Retained planning sources are protected through real storage and endpoints."""

import asyncio
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.api.routes.delete import delete_route
from app.mission import storage
from app.mission.planning.models import LegHistory

from . import test_store
from .test_store import bind, create

service = test_store.service


@pytest.mark.parametrize(
    "reference", ["draft", "retired", "history", "binding", "route_history"]
)
def test_route_delete_preserves_every_retained_reference(service, tmp_path, reference):
    view, _ = create(service)
    view = bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    leg = manifest.expected_legs[0]
    route_id = leg.route.route_id
    if reference == "retired":
        leg.retired = True
        for item in manifest.expected_legs[1:]:
            item.ordinal -= 1
    elif reference == "history":
        manifest.leg_history = [
            LegHistory(leg=leg.model_copy(deep=True), revision=1, reason="revision")
        ]
        leg.route = None
        manifest.route_bindings = []
    elif reference in {"binding", "route_history"}:
        setattr(
            manifest,
            reference if reference == "route_history" else "route_bindings",
            [leg.route],
        )
        leg.route = None
    service.store.persist(mission, manifest)
    manager = service.store.route_manager
    manager._active_route_id = route_id
    runtime = Mock()
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with pytest.raises(HTTPException) as raised:
        asyncio.run(delete_route(route_id, manager, service.store.poi_manager, runtime))
    assert raised.value.status_code == 409
    assert "mission" in raised.value.detail["action"].lower()
    runtime.runtime.cancel.assert_not_called()
    assert manager.get_route(route_id) is not None
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


def test_source_closure_keeps_all_accepted_revisions(service, tmp_path):
    from app.mission.planning.sources import source_closure

    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    assert {s.kind for s in source_closure(mission, manifest)} == {
        "itinerary_pdf",
        "route_kml",
    }
    assert source_closure(mission, manifest) == tuple(manifest.source_revisions)


def test_owned_delete_preserves_legacy_shared_route(service, tmp_path):
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.routes_v2 import delete_mission_endpoint

    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    route = manifest.expected_legs[0].route
    foreign = Mission(
        id="foreign",
        name="Foreign",
        legs=[
            MissionLeg(
                id="foreign-leg",
                name="Foreign",
                route_id=route.route_id,
                transports=TransportConfig(initial_x_satellite_id="SOUTH"),
            )
        ],
    )
    storage.save_mission_v2(foreign)
    source = next(s for s in manifest.source_revisions if s.id == route.source_id)
    original = service.sources.path(source).read_bytes()
    asyncio.run(
        delete_mission_endpoint(
            mission.id, service.store.route_manager, service.store.poi_manager
        )
    )
    assert storage.load_mission_v2(mission.id) is None
    assert service.sources.path(source).read_bytes() == original
    assert storage.load_mission_v2(foreign.id) == foreign

    assert all(
        not service.sources.path(s).exists()
        for s in manifest.source_revisions
        if s.kind == "itinerary_pdf"
    )


def test_delete_failure_reports_exact_remaining_owned_paths_and_retries(
    service, tmp_path, monkeypatch
):
    from pathlib import Path

    from app.mission.routes_v2 import delete_mission_endpoint

    view, _ = create(service)
    view = bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    pdf = service.sources.path(
        next(s for s in manifest.source_revisions if s.kind == "itinerary_pdf")
    )
    original = Path.unlink

    def deny_pdf(path, *args, **kwargs):
        if path == pdf:
            raise PermissionError("injected permission failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", deny_pdf)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            delete_mission_endpoint(
                mission.id, service.store.route_manager, service.store.poi_manager
            )
        )
    assert raised.value.status_code == 503
    assert raised.value.detail["retryable"] is True
    assert raised.value.detail["remaining_paths"] == [str(pdf)]
    assert storage.load_mission_v2(mission.id) is not None
    monkeypatch.setattr(Path, "unlink", original)
    asyncio.run(
        delete_mission_endpoint(
            mission.id, service.store.route_manager, service.store.poi_manager
        )
    )
    assert not any(
        service.sources.path(source).exists() for source in manifest.source_revisions
    )
    assert list((service.sources.root / "inventory").glob("*.json")) == []


def test_release_rejects_forged_pdf_ownership(service):
    from app.mission.planning.errors import PlanningFailure

    view, _ = create(service)
    _, manifest = service.store._load(view.mission.id)
    source = manifest.source_revisions[0]
    forged = source.model_copy(update={"owner": "other-mission"})
    with pytest.raises((ValueError, PlanningFailure)):
        service.sources.release_owned("other-mission", (forged,))
    assert service.sources.path(source).exists()


def test_owned_delete_removes_only_its_slide_cache_entries(service):
    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import default_store

    view, _ = create(service)
    cache = default_store()
    cache.request(view.mission.id, "owned", "digest", b"inputs")
    cache.request("foreign", "other", "digest", b"foreign inputs")
    before = cache.records("foreign")
    asyncio.run(
        delete_mission_endpoint(
            view.mission.id, service.store.route_manager, service.store.poi_manager
        )
    )
    assert cache.records(view.mission.id) == {}
    assert cache.records("foreign") == before


def test_release_rejects_symlink_alias_even_with_identical_bytes(service):
    view, _ = create(service)
    _, manifest = service.store._load(view.mission.id)
    source = manifest.source_revisions[0]
    path = service.sources.path(source)
    foreign = path.with_name("foreign.pdf")
    foreign.write_bytes(path.read_bytes())
    path.unlink()
    path.symlink_to(foreign)
    with pytest.raises(ValueError):
        service.sources.release_owned(view.mission.id, (source,))
    assert foreign.read_bytes() == b"synthetic pdf"


def test_owned_delete_removes_verified_imported_endpoints_only(service, tmp_path):
    import zipfile

    from app.mission.planning.packages import commit_package, stage_package
    from app.mission.routes_v2 import _endpoint_marker, delete_mission_endpoint
    from app.models.poi import POICreate

    from .test_packages import archive

    # A saved installed leg creates durable package endpoint ownership markers.
    view, _ = create(service)
    view = bind(service, tmp_path)
    from app.mission.models import MissionLeg, TransportConfig

    mission, manifest = service.store._load(view.mission.id)
    leg = MissionLeg(
        id="saved",
        name="Saved",
        route_id=manifest.expected_legs[0].route.route_id,
        transports=TransportConfig(initial_x_satellite_id="SOUTH"),
    )
    mission.legs = [leg]
    manifest.expected_legs[0].installed_leg_id = leg.id
    service.store.persist(
        mission,
        manifest,
        files={
            storage.get_mission_leg_file_path(
                mission.id, leg.id
            ): leg.model_dump_json().encode()
        },
    )
    with archive(service, mission.id) as handle, zipfile.ZipFile(handle) as zf:
        plan = stage_package(zf, None, service.sources)
    imported = commit_package(plan, None)
    manager = service.store.poi_manager
    endpoints = manager.list_pois(mission_id=imported.mission.id)
    assert len(endpoints) == 2
    manual = POICreate(
        name="Manual",
        latitude=0,
        longitude=0,
        mission_id=imported.mission.id,
        route_id=imported.mission.legs[0].route_id,
    )
    manual = manager.create_poi(manual)
    foreign = POICreate(
        name="Foreign",
        latitude=0,
        longitude=0,
        mission_id="foreign",
        route_id=imported.mission.legs[0].route_id,
        description=_endpoint_marker(leg.id, "arrival"),
    )
    foreign = manager.create_poi(foreign)
    asyncio.run(
        delete_mission_endpoint(
            imported.mission.id, service.store.route_manager, manager
        )
    )
    assert all(manager.get_poi(poi.id) is None for poi in endpoints)
    assert manager.get_poi(manual.id) == manual
    assert manager.get_poi(foreign.id) == foreign


def test_standalone_unreferenced_legacy_route_delete_remains_compatible(service):
    from app.models.poi import POICreate

    from .test_match import kml_fixture

    manager = service.store.route_manager
    path = kml_fixture(manager.routes_dir)
    manager._load_route_file(str(path))
    route_id = path.stem
    assert manager.get_route(route_id) is not None
    assert manager.activate_route(route_id)
    poi = service.store.poi_manager.create_poi(
        POICreate(name="Legacy marker", latitude=0, longitude=0, route_id=route_id)
    )
    asyncio.run(delete_route(route_id, manager, service.store.poi_manager, None))
    assert manager.get_active_route_id() is None
    assert manager.get_route(route_id) is None
    assert service.store.poi_manager.get_poi(poi.id) is None
    assert not path.exists()
