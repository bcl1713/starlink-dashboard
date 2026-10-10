"""Unit tests for active v2 mission-leg context resolution."""

import asyncio
import json

import pytest

from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.storage import (
    get_active_leg_lock,
    load_mission_v2,
    save_mission_v2,
)
from app.models.route import ParsedRoute, RouteMetadata, RoutePoint
from app.services.route_manager import RouteManager


def _route(route_id: str) -> ParsedRoute:
    return ParsedRoute(
        metadata=RouteMetadata(
            name=route_id,
            file_path=f"/tmp/{route_id}.kml",
            point_count=2,
        ),
        points=[
            RoutePoint(latitude=0.0, longitude=0.0, sequence=0),
            RoutePoint(latitude=1.0, longitude=1.0, sequence=1),
        ],
    )


def _mission(mission_id: str, leg_id: str, route_id: str) -> Mission:
    return Mission(
        id=mission_id,
        name=mission_id,
        legs=[
            MissionLeg(
                id=leg_id,
                name=leg_id,
                route_id=route_id,
                transports=TransportConfig(initial_x_satellite_id="X-1"),
            )
        ],
    )


@pytest.fixture
def route_manager(tmp_path) -> RouteManager:
    manager = RouteManager(routes_dir=tmp_path / "routes")
    manager.add_route("route-a", _route("route-a"))
    manager.add_route("route-b", _route("route-b"))
    return manager


@pytest.fixture
def v2_mission() -> Mission:
    return _mission("mission-a", "leg-a", "route-a")


def test_resolver_returns_parent_leg_and_route_after_fresh_read(
    route_manager, v2_mission
) -> None:
    from app.mission.active_context import resolve_active_mission_leg_context

    save_mission_v2(_mission("mission-b", "leg-b", "route-b"))
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    assert route_manager.activate_route("route-a") is True

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == "available"
    assert resolution.context is not None
    assert resolution.context.parent_mission_id == v2_mission.id
    assert resolution.context.parent_mission.id == v2_mission.id
    assert resolution.context.leg.id == "leg-a"
    assert resolution.context.route_id == "route-a"
    assert resolution.context.route is route_manager.get_route("route-a")


@pytest.mark.parametrize(
    ("state_setup", "expected"),
    [
        ("none", "no_active_mission"),
        ("blank_route", "route_unavailable"),
        ("padded_route", "route_unavailable"),
        ("missing_route", "route_unavailable"),
        ("route_mismatch", "route_unavailable"),
        ("two_active_legs", "inconsistent_active_mission"),
    ],
)
def test_resolver_returns_explicit_failure_without_context(
    state_setup, expected, route_manager
) -> None:
    from app.mission.active_context import resolve_active_mission_leg_context

    mission_a = _mission("mission-a", "leg-a", "route-a")
    mission_b = _mission("mission-b", "leg-b", "route-b")

    if state_setup == "blank_route":
        mission_a.legs[0].route_id = " "
        mission_a.legs[0].is_active = True
    elif state_setup == "padded_route":
        mission_a.legs[0].route_id = " route-a "
        mission_a.legs[0].is_active = True
        assert route_manager.activate_route("route-a") is True
    elif state_setup == "missing_route":
        mission_a.legs[0].route_id = "missing-route"
        mission_a.legs[0].is_active = True
    elif state_setup == "route_mismatch":
        mission_a.legs[0].is_active = True
        assert route_manager.activate_route("route-b") is True
    elif state_setup == "two_active_legs":
        mission_a.legs[0].is_active = True
        mission_b.legs[0].is_active = True

    save_mission_v2(mission_a)
    save_mission_v2(mission_b)

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == expected
    assert resolution.context is None


def test_resolver_ignores_flat_v1_active_looking_artifact(route_manager) -> None:
    from app.mission import storage
    from app.mission.active_context import resolve_active_mission_leg_context

    legacy_leg = _mission("legacy-mission", "legacy-leg", "route-a").legs[0]
    legacy_leg.is_active = True
    with open(storage.MISSIONS_DIR / "legacy-mission.json", "w") as handle:
        json.dump(legacy_leg.model_dump(), handle, default=str)
    assert route_manager.activate_route("route-a") is True

    resolution = resolve_active_mission_leg_context(route_manager)

    assert resolution.state == "no_active_mission"
    assert resolution.context is None


def test_resolver_and_v2_writer_share_active_leg_lock(
    monkeypatch, route_manager
) -> None:
    from app.mission import active_context, storage
    from app.mission.active_context import resolve_active_mission_leg_context

    events = []
    instances = []

    class RecordingLock:
        def __init__(self, path: str):
            self.path = path
            self.depth = 0
            instances.append(self)

        def __enter__(self):
            self.depth += 1
            events.append(("enter", self))
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            events.append(("exit", self))
            self.depth -= 1
            return False

    monkeypatch.setattr(storage, "_active_leg_locks", {})
    monkeypatch.setattr(storage, "FileLock", RecordingLock)
    real_list = active_context.list_mission_metadata_v2
    real_write = storage._save_mission_v2_unlocked

    def guarded_list():
        assert storage.get_active_leg_lock().depth > 0
        events.append(("read", storage.get_active_leg_lock()))
        return real_list()

    def guarded_write(mission):
        assert storage.get_active_leg_lock().depth > 0
        events.append(("write", storage.get_active_leg_lock()))
        return real_write(mission)

    monkeypatch.setattr(active_context, "list_mission_metadata_v2", guarded_list)
    monkeypatch.setattr(storage, "_save_mission_v2_unlocked", guarded_write)
    resolve_active_mission_leg_context(route_manager)
    save_mission_v2(_mission("mission-a", "leg-a", "route-a"))

    assert len(instances) == 1
    assert instances[0].path == str(storage.MISSIONS_DIR / ".active-leg.lock")
    assert all(lock is instances[0] for _, lock in events)
    assert [event for event, _ in events if event in {"read", "write"}] == [
        "read",
        "write",
    ]
    assert events[0][0] == "enter" and events[-1][0] == "exit"
    assert instances[0].depth == 0


def test_active_leg_lock_uses_a_canonical_minimum_version_compatible_instance(
    monkeypatch,
) -> None:
    from app.mission import storage

    constructed_paths: list[str] = []

    class CompatibleFileLock:
        def __init__(self, path: str):
            self.path = path
            self.depth = 0
            constructed_paths.append(path)

        def __enter__(self):
            self.depth += 1
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            self.depth -= 1
            return False

    monkeypatch.setattr(storage, "_active_leg_locks", {}, raising=False)
    monkeypatch.setattr(storage, "FileLock", CompatibleFileLock)

    outer_lock = storage.get_active_leg_lock()
    inner_lock = storage.get_active_leg_lock()

    assert outer_lock is inner_lock
    assert constructed_paths == [str(storage.MISSIONS_DIR / ".active-leg.lock")]
    with outer_lock, inner_lock:
        assert outer_lock.depth == 2
    assert outer_lock.depth == 0


def test_active_leg_lock_is_reentrant_when_save_runs_inside_coordination_scope() -> (
    None
):
    mission = _mission("mission-reentrant", "leg-reentrant", "route-a")

    with get_active_leg_lock():
        save_mission_v2(mission)

    loaded = load_mission_v2(mission.id)
    assert loaded is not None
    assert loaded.legs[0].id == "leg-reentrant"


def test_delete_endpoint_acquires_global_active_leg_lock_before_parent_lock(
    monkeypatch, route_manager, tmp_path
) -> None:
    from app.mission import routes_v2

    mission_id = "delete-lock-boundary"
    save_mission_v2(_mission(mission_id, "leg-a", "route-a"))
    route_file = tmp_path / "route-a.kml"
    route_file.write_text("synthetic route ownership fixture")
    route_manager.get_route("route-a").metadata.file_path = str(route_file)
    entered: list[str] = []
    stack: list[str] = []

    class RecordingLock:
        def __init__(self, name: str):
            self.name = name

        def __enter__(self):
            if self.name == "mission":
                assert stack == ["active"]
            entered.append(self.name)
            stack.append(self.name)
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            assert stack.pop() == self.name
            return False

    monkeypatch.setattr(
        routes_v2, "get_mission_lock", lambda mission_id: RecordingLock("mission")
    )
    monkeypatch.setattr(
        routes_v2, "get_active_leg_lock", lambda: RecordingLock("active")
    )
    real_get = route_manager.get_route

    def guarded_get(route_id):
        assert stack == ["active", "mission"]
        return real_get(route_id)

    monkeypatch.setattr(route_manager, "get_route", guarded_get)
    asyncio.run(
        routes_v2.delete_mission_endpoint(
            mission_id, route_manager=route_manager, poi_manager=None
        )
    )
    assert entered == ["active", "mission"]
    assert not stack
    assert load_mission_v2(mission_id) is None
    assert not route_file.exists()
    assert "route-a" not in route_manager._routes


def test_v2_writer_removes_deleted_active_leg_inside_shared_lock(route_manager) -> None:
    from app.mission.active_context import resolve_active_mission_leg_context

    mission = _mission("mission-a", "leg-a", "route-a")
    mission.legs[0].is_active = True
    save_mission_v2(mission)
    assert route_manager.activate_route("route-a") is True

    mission.legs = []
    save_mission_v2(mission)

    assert (
        resolve_active_mission_leg_context(route_manager).state == "no_active_mission"
    )
