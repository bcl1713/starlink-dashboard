"""Coordinator cancellation, restart ownership, and cheap ready export."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from filelock import Timeout

from app.mission.slide_cache.coordinator import JobCancellation, SlideCoordinator
from app.mission.slide_cache.identity import encode_snapshot
from app.mission.slide_cache.store import SlideStore
from tests.unit.test_customer_document import inputs


def saved_leg(tmp_path, monkeypatch):
    from app.mission import storage
    from app.mission.models import Mission, MissionLeg, TransportConfig

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    mission = Mission(
        id="m",
        name="Original",
        legs=[
            MissionLeg(
                id="a",
                name="A",
                route_id="",
                transports=TransportConfig(initial_x_satellite_id=""),
            )
        ],
    )
    storage.save_mission_v2(mission)
    return mission


def test_normalization_releases_active_gate(tmp_path, monkeypatch):
    from app.mission import storage
    from app.mission.slide_cache import coordinator as module
    from app.mission.slide_cache import identity

    saved_leg(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    original = identity.leg_inputs

    def slow_normalization(*args):
        entered.set()
        assert release.wait(3)
        return original(*args)

    monkeypatch.setattr(identity, "leg_inputs", slow_normalization)
    readable = False
    with ThreadPoolExecutor(max_workers=1) as executor:
        task = executor.submit(
            module.reconcile, "m", None, None, SlideStore(tmp_path / "cache"), "v1"
        )
        try:
            assert entered.wait(2)
            try:
                with storage.get_active_leg_lock().acquire(timeout=0.25):
                    readable = storage.load_mission_v2("m").name == "Original"
            except Timeout:
                pass
        finally:
            release.set()
            task.result(timeout=3)
    assert readable, "Customer normalization held the API's global storage gate"


def test_superseded_capture_cannot_enqueue(tmp_path, monkeypatch):
    from app.mission import storage
    from app.mission.slide_cache import coordinator as module
    from app.mission.slide_cache import identity

    mission = saved_leg(tmp_path, monkeypatch)
    original = identity.leg_inputs
    changed = False

    def change_after_capture(*args):
        nonlocal changed
        if not changed:
            changed = True
            mission.name = "New committed input"
            storage.save_mission_v2(mission)
        return original(*args)

    monkeypatch.setattr(identity, "leg_inputs", change_after_capture)
    cache = SlideStore(tmp_path / "cache")
    module.reconcile("m", None, None, cache, "v1")
    queued = json.loads(cache.records("m")["a"]["inputs"])
    assert queued["metadata"]["name"] == "New committed input"


def test_cancellation_poll_never_reconciles_full_inputs(tmp_path, monkeypatch):
    coordinator = SlideCoordinator(None, None, cache=SlideStore(tmp_path / "cache"))
    token = coordinator.cache.request("m", "a", "v1", b"inputs")
    monkeypatch.setattr(
        coordinator,
        "reconcile_all",
        lambda: pytest.fail("Heavy work in cancellation poll"),
    )
    assert not JobCancellation(
        coordinator, {"mission": "m", "leg": "a", "token": token}
    ).is_set()


def test_idle_reconciliation_reuses_validated_inputs(tmp_path, monkeypatch):
    from app.mission.slide_cache import capture
    from app.mission.slide_cache import coordinator as module

    mission = saved_leg(tmp_path, monkeypatch)
    original = capture.normalize_capture
    calls = []

    def normalize(raw, **kwargs):
        calls.append(raw)
        return original(raw, **kwargs)

    monkeypatch.setattr(capture, "normalize_capture", normalize)
    cache, memo = SlideStore(tmp_path / "cache"), {}
    module.reconcile("m", None, None, cache, "v1", memo=memo)
    module.reconcile("m", None, None, cache, "v1", memo=memo)
    assert len(calls) == 1
    mission.name = "Changed"
    __import__("app.mission.storage", fromlist=["save_mission_v2"]).save_mission_v2(
        mission
    )
    module.reconcile("m", None, None, cache, "v1", memo=memo)
    assert len(calls) == 2


def test_status_records_do_not_load_artifact_blobs(tmp_path, monkeypatch):
    import sqlite3
    from contextlib import contextmanager

    cache = SlideStore(tmp_path / "cache")
    token = cache.request("m", "a", "v1", b"inputs")
    cache.claim()
    cache.publish("m", "a", token, b"snapshot", b"pdf", b"evidence")
    original = cache.connection

    @contextmanager
    def metadata_only():
        with original() as db:
            db.set_authorizer(
                lambda operation, table, column, *rest: (
                    sqlite3.SQLITE_DENY
                    if operation == sqlite3.SQLITE_READ
                    and table == "slides"
                    and column in {"inputs", "snapshot", "pdf", "evidence"}
                    else sqlite3.SQLITE_OK
                )
            )
            yield db

    monkeypatch.setattr(cache, "connection", metadata_only)
    assert hasattr(cache, "status_records"), "Cheap preparation status is absent"
    record = cache.status_records("m")["a"]
    assert record["state"] == "ready" and record["fingerprint"] == "v1"
    assert not {"inputs", "snapshot", "pdf", "evidence"} & record.keys()


def test_new_input_cancels_only_its_running_job(tmp_path, monkeypatch):
    coordinator = SlideCoordinator(
        None, None, cache=SlideStore(tmp_path / "slides.sqlite3")
    )
    monkeypatch.setattr(coordinator, "reconcile_all", lambda: None)
    a = coordinator.cache.request("m", "a", "old", b"inputs")
    coordinator.cache.request("m", "b", "other", b"other inputs")
    cancel_a = JobCancellation(coordinator, {"mission": "m", "leg": "a", "token": a})
    b = coordinator.cache.records("m")["b"]["token"]
    cancel_b = JobCancellation(coordinator, {"mission": "m", "leg": "b", "token": b})
    coordinator.cache.request("m", "a", "new", b"new inputs")
    assert cancel_a.is_set()
    assert not cancel_b.is_set()


def test_superseded_worker_is_reaped_before_next_claim(tmp_path, monkeypatch):
    import app.mission.slide_cache.coordinator as module
    from app.mission.exporter.customer_runtime import _alive, _process_record

    coordinator = SlideCoordinator(
        None, None, cache=SlideStore(tmp_path / "slides.sqlite3")
    )
    monkeypatch.setattr(coordinator, "reconcile_all", lambda: None)
    coordinator.cache.request("m", "a", "old", b"{}")
    job = coordinator.cache.claim()
    original = module.run_owned_renderer
    owned = []

    def render(command, staging, **kwargs):
        # Real supervised subprocess and descendant; only renderer content is fake.
        command = [
            __import__("sys").executable,
            "-c",
            "import subprocess,time; subprocess.Popen(['sleep','30']); time.sleep(30)",
        ]

        def supersede():
            owner = Path(staging) / "python-owner.json"
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if owner.exists():
                    raw = json.loads(owner.read_text())
                    if raw.get("pid"):
                        owned.append(_process_record(raw["pid"]))
                        coordinator.cache.request("m", "a", "new", b"new")
                        return
                time.sleep(0.01)

        thread = threading.Thread(target=supersede)
        thread.start()
        try:
            return original(command, staging, **kwargs)
        finally:
            thread.join(5)

    monkeypatch.setattr(module, "run_owned_renderer", render)
    coordinator.run_job(job)
    assert owned and all(not _alive(record) for record in owned)
    assert coordinator.cache.claim()["fingerprint"] == "new"


def test_ready_export_uses_prepared_snapshot_without_timeline_or_map_work(
    tmp_path, monkeypatch
):
    from app.mission import storage
    from app.mission.exporter import snapshot as snapshot_module

    # The production fixture's capture dependencies exercise real saved input identity.
    # Snapshot rendering is performed before poisoning all heavy generation calls.
    from app.mission.models import Mission, MissionLeg, TransportConfig
    from app.mission.slide_cache.coordinator import reconcile
    from app.mission.slide_cache.identity import renderer_revision
    from app.mission.slide_cache.prepared_export import await_prepared

    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    leg = MissionLeg(
        id="a",
        name="A",
        route_id="",
        transports=TransportConfig(initial_x_satellite_id=""),
    )
    storage.save_mission_v2(Mission(id="m", name="Mission", legs=[leg]))
    cache = __import__(
        "app.mission.slide_cache.store", fromlist=["default_store"]
    ).default_store()
    reconcile("m", None, None, cache, renderer_revision())
    job = cache.claim()
    # Cache an immutable prepared leg; no renderer is needed to prove the ready read path.
    from dataclasses import replace

    captured = inputs()[0]
    captured = replace(captured, legs=(replace(captured.legs[0], leg_id="a"),))
    cache.publish(
        "m", "a", job["token"], encode_snapshot(captured), b"pdf", b"evidence"
    )
    monkeypatch.setattr(
        snapshot_module,
        "prepare_mission_timeline",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("timeline rebuilt on ready path")
        ),
    )
    result, records = await_prepared(
        "m", None, None, cancel=threading.Event(), wall_seconds=1
    )
    assert result.legs[0].timeline_json == captured.legs[0].timeline_json
    assert records["a"]["pdf"] == b"pdf"


def test_renderer_deadline_preserves_already_prepared_csv_snapshot(
    tmp_path, monkeypatch
):
    import app.mission.slide_cache.coordinator as module
    from app.mission.exporter.customer_runtime import RendererFailure

    coordinator = SlideCoordinator(
        None, None, cache=SlideStore(tmp_path / "slides.sqlite3")
    )
    coordinator.cache.request("m", "a", "one", b"inputs")
    job = coordinator.cache.claim()
    captured = inputs()[0]

    def failed_renderer(command, staging, **kwargs):
        (Path(staging) / "snapshot.json").write_bytes(encode_snapshot(captured))
        raise RendererFailure("deadline")

    monkeypatch.setattr(module, "run_owned_renderer", failed_renderer)
    coordinator.run_job(job)
    record = coordinator.cache.records("m")["a"]
    assert record["snapshot"] == encode_snapshot(captured)
    assert record["state"] == "failed"
    assert record["warning"] == "deadline"


def test_second_coordinator_does_not_recover_an_active_job(tmp_path, monkeypatch):
    cache = SlideStore(tmp_path / "slides.sqlite3")
    cache.request("m", "a", "one", b"inputs")
    first, second = SlideCoordinator(None, None, cache=cache), SlideCoordinator(
        None, None, cache=cache
    )
    entered, release = threading.Event(), threading.Event()
    active = []
    for coordinator in (first, second):
        monkeypatch.setattr(coordinator, "reconcile_all", lambda: None)

        def work(job, owner=coordinator):
            active.append(owner)
            entered.set()
            release.wait(3)

        monkeypatch.setattr(coordinator, "run_job", work)
    first.start()
    try:
        assert entered.wait(2)
        second.start()
        time.sleep(0.1)
        assert len(active) == 1
        assert cache.records("m")["a"]["state"] == "running"
    finally:
        first.stop.set()
        second.stop.set()
        release.set()
        first.close()
        second.close()
