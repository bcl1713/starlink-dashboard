"""Normal relative production roots retain strict package alias rejection."""

import io
import json
import zipfile
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.mission import storage
from app.mission.dependencies import get_poi_manager, get_route_manager
from app.mission.planning import packages
from app.mission.planning.errors import PlanningFailure
from app.mission.planning.service import PlanningService
from app.mission.planning.store import PlanningStore
from app.mission.routes_v2 import router
from app.services.poi_manager import POIManager
from app.services.route_manager import RouteManager

from .test_packages import archive
from .test_store import bind, create


@pytest.fixture
def relative_service(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(storage, "MISSIONS_DIR", Path("data/missions"))
    return PlanningService(
        PlanningStore(
            storage.MISSIONS_DIR,
            RouteManager(tmp_path / "routes"),
            POIManager(tmp_path / "pois.json"),
        )
    )


def test_real_api_collision_and_roundtrip_with_relative_storage(
    relative_service, tmp_path
):
    service = relative_service
    view, _ = create(service)
    original = bind(service, tmp_path)
    app = FastAPI()
    app.state.planning_service = service
    app.include_router(router)
    app.dependency_overrides[get_route_manager] = lambda: service.store.route_manager
    app.dependency_overrides[get_poi_manager] = lambda: service.store.poi_manager
    with TestClient(app) as client:
        identity = view.mission.id
        for _ in range(2):
            with archive(service, identity) as handle:
                response = client.post(
                    "/api/v2/missions/import",
                    files={"file": ("synthetic.zip", handle.read(), "application/zip")},
                )
            assert response.status_code == 200, response.text
            imported = response.json()
            assert imported["success"] and imported["mission_id"] != identity
            identity = imported["mission_id"]
            current = service.store.read(identity)
            assert len(current.expected_legs) == 3
            assert (
                current.expected_legs[0].leg.route.content_hash
                == original.expected_legs[0].leg.route.content_hash
            )
            assert (
                current.expected_legs[0].leg.route.route_id
                != original.expected_legs[0].leg.route.route_id
            )
    assert service.store.read(view.mission.id) == original


@pytest.mark.parametrize("when", ["stage", "commit"])
@pytest.mark.parametrize("kind", ["parent", "leaf"])
def test_relative_root_rejects_alias_without_foreign_writes(
    relative_service, tmp_path, monkeypatch, when, kind
):
    service = relative_service
    view, _ = create(service)
    with archive(service, view.mission.id) as handle:
        payload = handle.read()
    destination = service.store.root / str(UUID(int=1))
    numbers = iter(range(1, 20))
    monkeypatch.setattr(packages, "uuid4", lambda: UUID(int=next(numbers)))
    if when == "commit":
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            plan = packages.stage_package(zf, None, service.sources)
        assert all(Path(path).is_absolute() for path, _ in plan.files)
        destination = service.store.root / json.loads(plan.mission_json)["id"]
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    marker = foreign / "marker"
    marker.write_bytes(b"foreign remains unchanged")
    if kind == "parent":
        destination.symlink_to(foreign, target_is_directory=True)
    else:
        destination.mkdir()
        (destination / "mission.json").symlink_to(marker)
    before = {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    }
    with pytest.raises((ValueError, PlanningFailure)):
        if when == "stage":
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                packages.stage_package(zf, None, service.sources)
        else:
            packages.commit_package(plan, None)
    assert {
        str(p): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file() and p.suffix != ".lock"
    } == before
    assert marker.read_bytes() == b"foreign remains unchanged"
