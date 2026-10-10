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


@pytest.mark.parametrize("boundary", ["endpoint", "release"])
def test_owned_delete_rejects_directly_activated_zero_leg_route_before_mutation(
    service, tmp_path, boundary
):
    from app.api.routes.management import activate_route
    from app.mission.planning.errors import PlanningFailure
    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import default_store
    from app.models.poi import POICreate

    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    assert mission.legs == []
    route_id = manifest.expected_legs[0].route.route_id
    manager, pois = service.store.route_manager, service.store.poi_manager
    pois.create_poi(
        POICreate(
            name="Owned marker",
            latitude=0,
            longitude=0,
            mission_id=mission.id,
            route_id=route_id,
        )
    )
    runtime = Mock()
    asyncio.run(activate_route(route_id, manager, pois, runtime))
    runtime.reset_mock()
    cache = default_store()
    cache.request(mission.id, "draft", "digest", b"inputs")
    before_cache = cache.records(mission.id)
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    before_route = manager.get_route(route_id).model_copy(deep=True)
    with pytest.raises((HTTPException, PlanningFailure)) as raised:
        if boundary == "endpoint":
            asyncio.run(delete_mission_endpoint(mission.id, manager, pois, runtime))
        else:
            service.sources.release_owned(mission.id, tuple(manifest.source_revisions))
    assert raised.value.status_code == 409
    detail = (
        raised.value.detail
        if isinstance(raised.value, HTTPException)
        else raised.value.error.model_dump()
    )
    assert "deactivate" in detail["action"].lower()
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    assert manager.get_active_route_id() == route_id
    assert manager.get_route(route_id) == before_route
    assert cache.records(mission.id) == before_cache
    runtime.cancel_owned.assert_not_called()
    runtime.runtime.cancel.assert_not_called()


def test_release_rejects_inventory_parent_alias_before_any_unlink(service, tmp_path):
    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    inventory = service.sources.root / "inventory"
    foreign = tmp_path / "foreign-inventory"
    inventory.rename(foreign)
    inventory.symlink_to(foreign, target_is_directory=True)
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with pytest.raises(ValueError, match="path|alias|symlink"):
        service.sources.release_owned(mission.id, tuple(manifest.source_revisions))
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


def test_mission_delete_retry_survives_removed_parent_metadata(
    service, tmp_path, monkeypatch
):
    import os

    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import default_store

    view, _ = create(service)
    bind(service, tmp_path)
    mission, _ = service.store._load(view.mission.id)
    directory = storage.get_mission_directory(mission.id)
    payload = directory / "planning" / "proposals" / "retained.json"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(b'{"retained":"synthetic deletion fixture"}')
    foreign = tmp_path / "foreign-payload.json"
    foreign.write_bytes(b"foreign")
    cache = default_store()
    cache.request("foreign", "leg", "hash", b"inputs")
    before_cache = cache.records("foreign")
    original = os.unlink

    def fail_payload(path, *args, **kwargs):
        if str(path).endswith(payload.name):
            metadata = storage.get_mission_file_path(mission.id)
            if metadata.exists():
                original(metadata)
            raise PermissionError("injected retained payload cleanup failure")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(os, "unlink", fail_payload)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            delete_mission_endpoint(
                mission.id, service.store.route_manager, service.store.poi_manager
            )
        )
    assert raised.value.status_code == 503
    assert raised.value.detail["retryable"] is True
    assert raised.value.detail["remaining_paths"] == [str(payload)]
    assert not storage.get_mission_file_path(mission.id).exists()
    assert payload.exists()
    monkeypatch.setattr(os, "unlink", original)
    asyncio.run(
        delete_mission_endpoint(
            mission.id, service.store.route_manager, service.store.poi_manager
        )
    )
    assert not directory.exists()
    assert foreign.read_bytes() == b"foreign"
    assert cache.records("foreign") == before_cache
    assert not list((service.sources.root / "deletions").glob("*.json"))


def _failed_deletion(service, tmp_path, monkeypatch):
    from pathlib import Path

    from app.mission.routes_v2 import delete_mission_endpoint

    view, _ = create(service)
    bind(service, tmp_path)
    directory = storage.get_mission_directory(view.mission.id)
    payload = directory / "retained.json"
    payload.write_bytes(b"original retained bytes")
    original = Path.unlink

    def fail(path, *args, **kwargs):
        if path == payload:
            raise PermissionError("injected payload removal failure")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                delete_mission_endpoint(
                    view.mission.id,
                    service.store.route_manager,
                    service.store.poi_manager,
                )
            )
        assert raised.value.status_code == 503
    return view.mission.id, payload


@pytest.mark.parametrize(
    "change",
    [
        "payload",
        "new_file",
        "metadata",
        "owned_poi",
        "cache",
        "version",
        "authority_alias",
    ],
)
def test_delete_retry_rejects_changed_or_new_work_without_mutation(
    service, tmp_path, monkeypatch, change
):
    import json

    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import default_store
    from app.models.poi import POICreate

    owner, payload = _failed_deletion(service, tmp_path, monkeypatch)
    authority = service.sources.root / "deletions" / f"{owner}.json"
    if change == "payload":
        payload.write_bytes(b"replacement work")
    elif change == "new_file":
        payload.with_name("new-work.json").write_bytes(b"new work")
    elif change == "metadata":
        storage.get_mission_file_path(owner).write_bytes(b'{"new":"metadata work"}')
    elif change == "owned_poi":
        service.store.poi_manager.create_poi(
            POICreate(
                name="New generated work", latitude=0, longitude=0, mission_id=owner
            ),
            generated_source="mission-timeline",
        )
    elif change == "cache":
        default_store().request(owner, "new-leg", "new-digest", b"new inputs")
    elif change == "version":
        data = json.loads(authority.read_bytes())
        data["version"] = 2
        authority.write_text(json.dumps(data))
    else:
        foreign = tmp_path / "foreign-authority.json"
        authority.rename(foreign)
        authority.symlink_to(foreign)
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            delete_mission_endpoint(
                owner, service.store.route_manager, service.store.poi_manager
            )
        )
    assert raised.value.status_code in {409, 422}
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


@pytest.mark.parametrize("phase", ["poi", "cache", "directory", "authority"])
def test_delete_retry_covers_every_cleanup_phase_and_preserves_foreign_work(
    service, tmp_path, monkeypatch, phase
):
    import sqlite3
    from contextlib import contextmanager
    from pathlib import Path

    from app.mission.planning import deletion
    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import SlideStore, default_store
    from app.models.poi import POICreate

    view, _ = create(service)
    bind(service, tmp_path)
    owner = view.mission.id
    manager = service.store.poi_manager
    owned = manager.create_poi(
        POICreate(name="Owned", latitude=0, longitude=0, mission_id=owner),
        generated_source="mission-timeline",
    )
    foreign = manager.create_poi(
        POICreate(name="Foreign", latitude=0, longitude=0, mission_id="foreign"),
        generated_source="mission-timeline",
    )
    cache = default_store()
    cache.request(owner, "owned", "hash", b"inputs")
    cache.request("foreign", "foreign", "hash", b"foreign inputs")
    foreign_cache = cache.records("foreign")
    directory = storage.get_mission_directory(owner)
    authority = service.sources.root / "deletions" / f"{owner}.json"
    expected_path = {
        "poi": manager.pois_file,
        "cache": cache.path,
        "directory": directory,
        "authority": authority,
    }[phase]
    with monkeypatch.context() as patch:
        if phase == "poi":
            original = deletion.atomic_write

            def fail(path, data):
                if path == manager.pois_file:
                    raise PermissionError("injected POI cleanup failure")
                return original(path, data)

            patch.setattr(deletion, "atomic_write", fail)
        elif phase == "cache":
            original = SlideStore.connection

            @contextmanager
            def fail(store):
                with original(store) as db:

                    class Proxy:
                        def execute(self, sql, *args):
                            if sql.startswith("DELETE FROM slides"):
                                raise sqlite3.OperationalError(
                                    "injected cache cleanup failure"
                                )
                            return db.execute(sql, *args)

                    yield Proxy()

            patch.setattr(SlideStore, "connection", fail)
        else:
            name = "rmdir" if phase == "directory" else "unlink"
            original = getattr(Path, name)

            def fail(path, *args, **kwargs):
                if path == expected_path:
                    raise PermissionError("injected final cleanup failure")
                return original(path, *args, **kwargs)

            patch.setattr(Path, name, fail)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                delete_mission_endpoint(owner, service.store.route_manager, manager)
            )
        assert raised.value.status_code == 503
        assert raised.value.detail["retryable"] is True
        assert raised.value.detail["remaining_paths"] == [str(expected_path)]
    assert authority.exists()
    assert not storage.get_mission_file_path(owner).exists()
    # An independent writer reuses a formerly owned POI ID for foreign work.
    import json

    from filelock import FileLock

    with FileLock(str(manager.pois_file) + ".lock"):
        data = json.loads(manager.pois_file.read_bytes())
        replacement = foreign.model_dump(mode="json") | {
            "id": owned.id,
            "name": "Foreign replacement",
            "generated_source": None,
        }
        data["pois"][owned.id] = replacement
        manager.pois_file.write_text(json.dumps(data))
    asyncio.run(delete_mission_endpoint(owner, service.store.route_manager, manager))
    assert manager.get_poi(owned.id).name == "Foreign replacement"
    assert not directory.exists()
    assert not authority.exists()
    assert not manager.list_pois(mission_id=owner)
    assert manager.get_poi(foreign.id) == foreign
    assert cache.records(owner) == {}
    assert cache.records("foreign") == foreign_cache


def test_final_cleanup_preserves_new_interleaved_file_and_retry_authority(
    service, monkeypatch
):
    from pathlib import Path

    from app.mission.routes_v2 import delete_mission_endpoint

    view, _ = create(service)
    metadata = storage.get_mission_file_path(view.mission.id)
    foreign = metadata.with_name("new-independent-work.json")
    original = Path.unlink

    def interleaved(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == metadata:
            foreign.write_bytes(b"new independent work")
        return result

    monkeypatch.setattr(Path, "unlink", interleaved)
    with pytest.raises(HTTPException) as raised:
        asyncio.run(
            delete_mission_endpoint(
                view.mission.id, service.store.route_manager, service.store.poi_manager
            )
        )
    assert raised.value.status_code == 409
    assert foreign.read_bytes() == b"new independent work"
    assert (service.sources.root / "deletions" / f"{view.mission.id}.json").exists()


@pytest.mark.parametrize(
    "resource", ["payload", "directory", "authority", "poi", "cache"]
)
def test_retry_preflight_io_failure_is_structured_and_recovers(
    service, tmp_path, monkeypatch, resource
):
    import sqlite3
    from pathlib import Path

    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import SlideStore, default_store

    default_store().request("foreign", "foreign", "hash", b"foreign inputs")
    owner, payload = _failed_deletion(service, tmp_path, monkeypatch)
    authority = service.sources.root / "deletions" / f"{owner}.json"
    target = {
        "payload": payload,
        "directory": payload.parent,
        "authority": authority,
        "poi": service.store.poi_manager.pois_file,
        "cache": default_store().path,
    }[resource]
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with monkeypatch.context() as patch:
        if resource == "cache":
            original = SlideStore.records

            def fail(store, mission):
                if store.path == target:
                    raise sqlite3.OperationalError("temporary cache unavailable")
                return original(store, mission)

            patch.setattr(SlideStore, "records", fail)
        elif resource == "directory":
            original = Path.iterdir

            def fail(path):
                if path == target:
                    raise PermissionError("temporary unreadable directory")
                return original(path)

            patch.setattr(Path, "iterdir", fail)
        else:
            original = Path.read_bytes

            def fail(path):
                if path == target:
                    raise PermissionError("temporary unreadable resource")
                return original(path)

            patch.setattr(Path, "read_bytes", fail)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                delete_mission_endpoint(
                    owner, service.store.route_manager, service.store.poi_manager
                )
            )
        assert raised.value.status_code == 503
        assert raised.value.detail["code"] == "owned_delete_incomplete"
        assert raised.value.detail["retryable"] is True
        assert raised.value.detail["action"] == "retry_delete"
        assert raised.value.detail["remaining_paths"] == [str(target)]
    assert authority.exists()
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    asyncio.run(
        delete_mission_endpoint(
            owner, service.store.route_manager, service.store.poi_manager
        )
    )
    assert not authority.exists()
    assert not storage.get_mission_directory(owner).exists()
    assert default_store().records("foreign")


@pytest.mark.parametrize(
    "resource",
    [
        "metadata",
        "pdf",
        "kml",
        "profile",
        "inventory",
        "payload",
        "directory",
        "poi",
        "cache",
    ],
)
def test_initial_owned_delete_preflight_io_failure_has_no_mutation(
    service, tmp_path, monkeypatch, resource
):
    import builtins
    import sqlite3
    from pathlib import Path

    from app.mission.routes_v2 import delete_mission_endpoint
    from app.mission.slide_cache.store import SlideStore, default_store

    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    source = next(s for s in manifest.source_revisions if s.kind == "route_kml")
    pdf = next(s for s in manifest.source_revisions if s.kind == "itinerary_pdf")
    payload = storage.get_mission_directory(mission.id) / "payload.json"
    payload.write_bytes(b"retained initial payload")
    cache = default_store()
    cache.request(mission.id, "owned", "hash", b"inputs")
    target = {
        "metadata": storage.get_mission_file_path(mission.id),
        "pdf": service.sources.path(pdf),
        "kml": service.sources.routes_dir / f"{source.id}.kml",
        "profile": service.sources.descriptor_path(source.id),
        "inventory": service.sources.root / "inventory" / f"{source.id}.json",
        "payload": payload,
        "directory": payload.parent,
        "poi": service.store.poi_manager.pois_file,
        "cache": cache.path,
    }[resource]
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with monkeypatch.context() as patch:
        if resource == "metadata":
            original_open = builtins.open

            def fail(path, *args, **kwargs):
                if Path(path) == target:
                    raise PermissionError("temporary unreadable mission metadata")
                return original_open(path, *args, **kwargs)

            patch.setattr(builtins, "open", fail)
        elif resource == "cache":

            def fail(store, owner):
                raise sqlite3.OperationalError("temporary cache unavailable")

            patch.setattr(SlideStore, "records", fail)
        elif resource == "directory":
            original = Path.iterdir

            def fail(path):
                if path == target:
                    raise PermissionError("temporary unreadable directory")
                return original(path)

            patch.setattr(Path, "iterdir", fail)
        else:
            original = Path.read_bytes

            def fail(path):
                if path == target:
                    raise PermissionError("temporary unreadable resource")
                return original(path)

            patch.setattr(Path, "read_bytes", fail)
        with pytest.raises(HTTPException) as raised:
            asyncio.run(
                delete_mission_endpoint(
                    mission.id, service.store.route_manager, service.store.poi_manager
                )
            )
        assert raised.value.status_code == 503
        assert raised.value.detail["code"] == "owned_delete_incomplete"
        assert raised.value.detail["retryable"] is True
        assert raised.value.detail["action"] == "retry_delete"
        assert raised.value.detail["remaining_paths"] == [str(target)]
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    assert not list((service.sources.root / "deletions").glob("*.json"))
    asyncio.run(
        delete_mission_endpoint(
            mission.id, service.store.route_manager, service.store.poi_manager
        )
    )
    assert not storage.get_mission_directory(mission.id).exists()


@pytest.mark.parametrize("operation", ["route", "mission", "legacy", "import"])
@pytest.mark.parametrize("fault", ["unreadable", "malformed", "aliased", "leg"])
def test_reference_inventory_fails_closed_before_mutation(
    service, tmp_path, monkeypatch, operation, fault
):
    import builtins
    import zipfile
    from pathlib import Path

    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.planning.errors import PlanningFailure
    from app.mission.planning.packages import commit_package, stage_package
    from app.mission.routes_v2 import delete_mission_endpoint

    from .test_packages import archive

    view, _ = create(service)
    bind(service, tmp_path)
    mission, manifest = service.store._load(view.mission.id)
    route_id = manifest.expected_legs[0].route.route_id
    foreign = Mission(
        id="foreign",
        name="Foreign",
        legs=[
            MissionLeg(
                id="foreign-leg",
                name="Foreign",
                route_id=route_id,
                transports=TransportConfig(initial_x_satellite_id="SOUTH"),
            )
        ],
    )
    storage.save_mission_v2(foreign)
    if operation == "legacy":
        legacy = foreign.model_copy(update={"id": "legacy-delete"}, deep=True)
        storage.save_mission_v2(legacy)
    with archive(service, mission.id) as handle, zipfile.ZipFile(handle) as zf:
        plan = stage_package(zf, None, service.sources)
    target = storage.get_mission_file_path(foreign.id)
    if fault == "leg":
        target = storage.get_mission_leg_file_path(foreign.id, "foreign-leg")
    if fault == "malformed":
        target.write_bytes(b"{broken metadata")
    elif fault == "aliased":
        other = tmp_path / "foreign-metadata.json"
        target.rename(other)
        target.symlink_to(other)
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    runtime = Mock()
    with monkeypatch.context() as patch:
        if fault in {"unreadable", "leg"}:
            original_read, original_open = Path.read_bytes, builtins.open

            def fail_read(path):
                if path == target:
                    raise PermissionError("unreadable foreign reference")
                return original_read(path)

            def fail_open(path, *args, **kwargs):
                if Path(path) == target:
                    raise PermissionError("unreadable foreign reference")
                return original_open(path, *args, **kwargs)

            patch.setattr(Path, "read_bytes", fail_read)
            patch.setattr(builtins, "open", fail_open)
        if fault in {"unreadable", "malformed"}:
            assert foreign.id not in {p.id for p in storage.list_mission_metadata_v2()}
        with pytest.raises((HTTPException, PlanningFailure)) as raised:
            if operation == "route":
                asyncio.run(
                    delete_route(
                        route_id,
                        service.store.route_manager,
                        service.store.poi_manager,
                        runtime,
                    )
                )
            elif operation in {"mission", "legacy"}:
                asyncio.run(
                    delete_mission_endpoint(
                        legacy.id if operation == "legacy" else mission.id,
                        service.store.route_manager,
                        service.store.poi_manager,
                        runtime,
                    )
                )
            else:
                commit_package(plan, None)
        assert raised.value.status_code == (
            503 if fault in {"unreadable", "leg"} else 409
        )
        detail = (
            raised.value.detail
            if isinstance(raised.value, HTTPException)
            else raised.value.error.model_dump()
        )
        if fault in {"malformed", "aliased"}:
            assert detail["code"] == "planning_conflict"
        else:
            assert detail["retryable"] is True
            paths = (
                raised.value.detail["remaining_paths"]
                if isinstance(raised.value, HTTPException)
                else list(raised.value.remaining_paths)
            )
            assert paths == [str(target)]
    runtime.runtime.cancel.assert_not_called()
    runtime.cancel_owned.assert_not_called()
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    assert not list((service.sources.root / "deletions").glob("*.json"))


def test_reference_inventory_includes_partial_deletion_authority(
    service, tmp_path, monkeypatch
):
    from app.mission.planning.sources import route_references

    owner, _payload = _failed_deletion(service, tmp_path, monkeypatch)
    from app.mission.planning.deletion import load_record

    record = load_record(service.sources, owner)
    route_id = next(
        s["id"]
        for s in record.mission.metadata["itinerary_planning"]["source_revisions"]
        if s["kind"] == "route_kml"
    )
    assert not storage.get_mission_file_path(owner).exists()
    assert owner in route_references(route_id, sources=service.sources)


def test_zero_route_import_requires_complete_reference_inventory(
    service, tmp_path, monkeypatch
):
    import zipfile
    from pathlib import Path

    from app.mission.planning.errors import PlanningFailure
    from app.mission.planning.packages import commit_package, stage_package

    from .test_packages import archive

    view, _ = create(service)
    with archive(service, view.mission.id) as handle, zipfile.ZipFile(handle) as zf:
        plan = stage_package(zf, None, service.sources)
    assert not plan.routes
    target = storage.get_mission_file_path(view.mission.id)
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    original = Path.read_bytes
    with monkeypatch.context() as patch:

        def unreadable(path):
            if path == target:
                raise PermissionError("unreadable foreign metadata")
            return original(path)

        patch.setattr(Path, "read_bytes", unreadable)
        with pytest.raises(PlanningFailure) as raised:
            commit_package(plan, None)
        assert raised.value.status_code == 503
        assert raised.value.remaining_paths == (str(target),)
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }


def test_missing_planning_metadata_in_deletion_authority_is_structured(
    service, tmp_path, monkeypatch
):
    import json

    from app.mission.planning.deletion import load_record, record_path
    from app.mission.planning.errors import PlanningFailure
    from app.mission.planning.sources import route_references

    owner, _ = _failed_deletion(service, tmp_path, monkeypatch)
    path = record_path(service.sources, owner)
    raw = json.loads(path.read_bytes())
    raw["mission"]["metadata"].pop("itinerary_planning")
    path.write_text(json.dumps(raw))
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    for action in (
        lambda: load_record(service.sources, owner),
        lambda: route_references("any", sources=service.sources),
    ):
        with pytest.raises(PlanningFailure) as raised:
            action()
        assert raised.value.status_code in (409, 422)
        assert owner in raised.value.error.message
        assert raised.value.error.code in (
            "planning_conflict",
            "invalid_deletion_authority",
        )
    assert before == {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
