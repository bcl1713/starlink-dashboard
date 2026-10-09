"""Coordinator cancellation, restart ownership, and cheap ready export."""

import json
import threading
import time
from pathlib import Path

from app.mission.slide_cache.coordinator import JobCancellation, SlideCoordinator
from app.mission.slide_cache.identity import encode_snapshot
from app.mission.slide_cache.store import SlideStore
from tests.unit.test_customer_document import inputs


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
