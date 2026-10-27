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
            import os

            self.process_id = os.getpid()
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
    monkeypatch.setattr(storage, "RepositoryGate", RecordingLock)
    from app.mission import active_context_cache

    real_list = active_context_cache._inventory
    real_write = storage._save_mission_v2_unlocked

    def guarded_list(root):
        assert storage.get_active_leg_lock().depth > 0
        events.append(("read", storage.get_active_leg_lock()))
        return real_list(root)

    def guarded_write(mission):
        assert storage.get_active_leg_lock().depth > 0
        events.append(("write", storage.get_active_leg_lock()))
        return real_write(mission)

    monkeypatch.setattr(active_context_cache, "_inventory", guarded_list)
    monkeypatch.setattr(storage, "_save_mission_v2_unlocked", guarded_write)
    resolve_active_mission_leg_context(route_manager)
    save_mission_v2(_mission("mission-a", "leg-a", "route-a"))

    assert len(instances) == 1
    assert instances[0].path == str(storage.MISSIONS_DIR / ".active-leg.lock")
    assert all(lock is instances[0] for _, lock in events)
    assert [event for event, _ in events if event in {"read", "write"}] == [
        "read",
        "read",
        "write",
    ]
    assert events[0][0] == "enter" and events[-1][0] == "exit"
    assert instances[0].depth == 0


def test_active_leg_lock_uses_a_canonical_minimum_version_compatible_instance(
    monkeypatch,
) -> None:
    from app.mission import repository_gate, storage

    constructed_paths: list[str] = []

    class CompatibleFileLock:
        timeout = -1

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

        def acquire(self, timeout=None, poll_interval=0.05):
            self.depth += 1
            return self

        def release(self, force=False):
            self.depth -= 1

        @property
        def is_locked(self):
            return self.depth > 0

    monkeypatch.setattr(storage, "_active_leg_locks", {}, raising=False)
    monkeypatch.setattr(repository_gate, "FileLock", CompatibleFileLock)

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


def test_stable_context_reads_no_json_or_inventory_after_warmup(
    monkeypatch, route_manager, v2_mission
):
    """Count real I/O boundaries, not only calls to the mission loader."""
    import builtins
    from pathlib import Path
    from app.mission import active_context

    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    assert active_context.resolve_active_mission_leg_context(route_manager).context
    reads = []
    scans = []
    real_open, real_iterdir, real_glob = builtins.open, Path.iterdir, Path.glob

    def counted_open(path, *args, **kwargs):
        if str(path).endswith(".json"):
            reads.append(str(path))
        return real_open(path, *args, **kwargs)

    def counted_iterdir(path):
        scans.append(str(path))
        return real_iterdir(path)

    def counted_glob(path, pattern):
        scans.append(str(path))
        return real_glob(path, pattern)

    monkeypatch.setattr(builtins, "open", counted_open)
    monkeypatch.setattr(Path, "iterdir", counted_iterdir)
    monkeypatch.setattr(Path, "glob", counted_glob)
    for _ in range(125):
        assert active_context.resolve_active_mission_leg_context(route_manager).context
    assert reads == []
    assert scans == []


def test_local_mutation_invalidates_warmed_context_without_subscriber(
    route_manager, v2_mission
):
    from app.mission.active_context import resolve_active_mission_leg_context

    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    first = resolve_active_mission_leg_context(route_manager)
    v2_mission.legs[0].is_active = False
    save_mission_v2(v2_mission)
    assert resolve_active_mission_leg_context(route_manager).context is None
    assert first.context.leg.is_active


def test_external_edit_is_reconciled_and_generation_is_meaningful(
    monkeypatch, route_manager, v2_mission
):
    from app.mission import active_context, storage

    clock = [10.0]
    from app.mission import active_context_cache

    monkeypatch.setattr(active_context_cache, "monotonic", lambda: clock[0])
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    first = active_context.resolve_active_mission_leg_context(route_manager)
    clock[0] += 2
    unchanged = active_context.resolve_active_mission_leg_context(route_manager)
    assert unchanged.generation == first.generation
    path = storage.get_mission_leg_file_path(v2_mission.id, "leg-a")
    raw = json.loads(path.read_bytes())
    raw["is_active"] = False
    path.write_text(json.dumps(raw))
    clock[0] += 2
    changed = active_context.resolve_active_mission_leg_context(route_manager)
    assert changed.context is None
    assert changed.generation != first.generation


def test_duplicate_directory_identity_fails_closed(route_manager, v2_mission):
    import shutil
    from app.mission import storage
    from app.mission.active_context import resolve_active_mission_leg_context

    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    shutil.copytree(
        storage.MISSIONS_DIR / v2_mission.id, storage.MISSIONS_DIR / "alias"
    )
    route_manager.activate_route("route-a")
    result = resolve_active_mission_leg_context(route_manager)
    assert result.state == "inconsistent_active_mission"
    assert result.context is None


def test_public_models_are_detached_from_snapshot(route_manager, v2_mission):
    from app.mission.active_context import resolve_active_mission_leg_context

    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    first = resolve_active_mission_leg_context(route_manager)
    first.context.leg.is_active = False
    first.context.parent_mission.name = "edited response"
    fresh = resolve_active_mission_leg_context(route_manager)
    assert fresh.context.leg.is_active
    assert fresh.context.parent_mission.name == v2_mission.name


@pytest.mark.parametrize(
    "change", ["corrupt", "remove_leg", "remove_mission", "conflict"]
)
def test_external_changes_discard_old_binding_and_recover(
    monkeypatch, route_manager, v2_mission, change
):
    import shutil
    from app.mission import active_context_cache as cache, storage

    clock = [100.0]
    monkeypatch.setattr(cache, "monotonic", lambda: clock[0])
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    previous = cache.get_active_mission_snapshot(route_manager)
    assert previous.binding is not None
    leg_path = storage.get_mission_leg_file_path(v2_mission.id, "leg-a")
    if change == "corrupt":
        leg_path.write_text("{")
    elif change == "remove_leg":
        leg_path.unlink()
    elif change == "remove_mission":
        shutil.rmtree(storage.MISSIONS_DIR / v2_mission.id)
    else:
        other = _mission("mission-b", "leg-b", "route-a")
        other.legs[0].is_active = True
        # External publisher does not participate in the in-process generation.
        folder = storage.MISSIONS_DIR / other.id
        (folder / "legs").mkdir(parents=True)
        (folder / "mission.json").write_text(
            other.model_copy(update={"legs": []}).model_dump_json()
        )
        (folder / "legs" / "leg-b.json").write_text(other.legs[0].model_dump_json())
    clock[0] += 2
    changed = cache.get_active_mission_snapshot(route_manager)
    assert changed.binding is None
    assert not cache.active_mission_snapshot_is_current(route_manager, previous)
    if change == "conflict":
        shutil.rmtree(storage.MISSIONS_DIR / "mission-b")
    # Use the low-level recovery writer: the ordinary public save intentionally
    # rejects corrupt previous files, which is separate input validation.
    with get_active_leg_lock():
        storage._save_mission_v2_unlocked(v2_mission)
    clock[0] += 2
    restored = cache.get_active_mission_snapshot(route_manager)
    assert restored.binding.parent_mission_id == v2_mission.id
    assert restored.generation > previous.generation


def test_external_write_during_reconciliation_is_not_published(
    monkeypatch, route_manager, v2_mission
):
    from app.mission import active_context_cache as cache, storage

    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    load = storage.load_mission_v2

    def racing_load(mission_id):
        result = load(mission_id)
        path = storage.get_mission_leg_file_path(mission_id, "leg-a")
        path.write_text(path.read_text() + " ")
        return result

    monkeypatch.setattr(storage, "load_mission_v2", racing_load)
    assert cache.get_active_mission_snapshot(route_manager).binding is None
    monkeypatch.setattr(storage, "load_mission_v2", load)
    # External recovery is intentionally retried on the bounded schedule.
    route_manager._active_mission_context_cache.deadline = 0
    assert cache.get_active_mission_snapshot(route_manager).binding is not None


def test_route_reload_and_switch_invalidate_snapshot_immediately(
    route_manager, v2_mission
):
    from app.mission import active_context_cache as cache

    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    first = cache.get_active_mission_snapshot(route_manager)
    route_manager.add_route("route-a", _route("changed"))
    assert not cache.active_mission_snapshot_is_current(route_manager, first)
    current = cache.get_active_mission_snapshot(route_manager)
    assert current.route_identity != first.route_identity
    route_manager.activate_route("route-b")
    assert not cache.active_mission_snapshot_is_current(route_manager, current)
    assert cache.get_active_mission_snapshot(route_manager).binding is None


def test_failed_reconciliation_is_throttled(monkeypatch, route_manager, v2_mission):
    from app.mission import active_context_cache as cache, storage

    clock = [100.0]
    monkeypatch.setattr(cache, "monotonic", lambda: clock[0])
    save_mission_v2(v2_mission)
    path = storage.get_mission_leg_file_path(v2_mission.id, "leg-a")
    path.write_text("{")
    first = cache.get_active_mission_snapshot(route_manager)
    assert first.binding is None
    attempts = []
    real_inventory = cache._inventory

    def counted_inventory(root):
        attempts.append(root)
        return real_inventory(root)

    monkeypatch.setattr(cache, "_inventory", counted_inventory)
    for _ in range(125):
        assert cache.get_active_mission_snapshot(route_manager).binding is None
    assert attempts == []
    clock[0] += 2
    cache.get_active_mission_snapshot(route_manager)
    assert len(attempts) == 1


def test_poll_deadline_does_not_change_an_unchanged_generation(
    monkeypatch, route_manager, v2_mission
):
    from app.mission import active_context_cache as cache

    clock = [100.0]
    monkeypatch.setattr(cache, "monotonic", lambda: clock[0])
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    accepted = cache.get_active_mission_snapshot(route_manager)
    clock[0] += 2
    assert cache.active_mission_snapshot_is_current(route_manager, accepted)
    assert cache.get_active_mission_snapshot(route_manager) is accepted


def test_stalled_reconciliation_owner_fails_closed(
    monkeypatch, route_manager, v2_mission
):
    from app.mission import active_context_cache as cache

    clock = [100.0]
    monkeypatch.setattr(cache, "monotonic", lambda: clock[0])
    v2_mission.legs[0].is_active = True
    save_mission_v2(v2_mission)
    route_manager.activate_route("route-a")
    previous = cache.get_active_mission_snapshot(route_manager)
    route_manager._active_mission_context_owner = object()
    clock[0] += 4
    assert cache.get_active_mission_snapshot(route_manager, reconcile=False) is None
    assert not cache.active_mission_snapshot_is_current(route_manager, previous)
    assert cache.get_active_mission_snapshot(route_manager) is previous
