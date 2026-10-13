"""Persisted bounded export jobs own their package, independently of shared slides."""

import importlib
import io
import threading
import time
import zipfile
from contextlib import contextmanager

import pytest

from app.mission import storage
from app.mission.models import Mission, MissionLeg, TransportConfig
from app.mission.package.customer_artifacts import MissionPackageDownload
from app.mission.slide_cache.store import SlideStore


@contextmanager
def runtime(tmp_path, monkeypatch, **options):
    module = importlib.import_module("app.mission.package.preparation")
    monkeypatch.setattr(storage, "MISSIONS_DIR", tmp_path / "missions")
    mission = Mission(
        id="m",
        name="Example",
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
    service = module.ExportPreparationService(
        None,
        None,
        enabled=options.pop("enabled", False),
        cache=SlideStore(tmp_path / "cache/slides.sqlite3"),
        **options,
    )
    try:
        yield service, mission
    finally:
        service.close()
        assert not service.thread.is_alive()


def wait_state(service, job, states):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = service.status("m", job.id)
        if current.state in states:
            return current
        service.stop.wait(0.01)
    pytest.fail(f"Job failed to reach {states}: {current}")


def test_ready_package_is_scoped_and_downloads_exact_snapshot(tmp_path, monkeypatch):
    with runtime(tmp_path, monkeypatch) as (service, mission):
        job = service.start("m")
        assert job.deadline - job.queued_at == 600
        ready = wait_state(service, job, {"ready"})
        assert ready.expires_at - ready.finished_at == 1800
        with service.open_download("m", job.id).stream as stream, zipfile.ZipFile(
            stream
        ) as archive:
            assert "manifest.json" in archive.namelist()
        with pytest.raises(KeyError):
            service.status("other", job.id)
        mission.name = "Later mission"
        storage.save_mission_v2(mission)
        assert service.status("m", job.id).fingerprint == ready.fingerprint
        with service.open_download("m", job.id).stream as stream:
            assert stream.read(2) == b"PK"


def test_preparation_deadline_is_not_reset(tmp_path, monkeypatch):
    clock = [1000.0]
    entered = threading.Event()

    def build(*args, cancel, **kwargs):
        entered.set()
        assert cancel.wait(3)
        from app.mission.exporter.export_cancel import check_cancelled

        check_cancelled(cancel)

    with runtime(tmp_path, monkeypatch, clock=lambda: clock[0], builder=build) as (
        service,
        _,
    ):
        job = service.start("m")
        assert entered.wait(3)
        clock[0] += 601
        assert service.status("m", job.id).deadline == 1600
        failed = wait_state(service, job, {"failed"})
        assert failed.error_code == "deadline"


def test_ready_package_expiry(tmp_path, monkeypatch):
    clock = [1000.0]
    with runtime(tmp_path, monkeypatch, clock=lambda: clock[0]) as (service, _):
        job = service.start("m")
        ready = wait_state(service, job, {"ready"})
        clock[0] = ready.expires_at + 1
        assert service.status("m", job.id).state == "expired"
        with pytest.raises(TimeoutError):
            service.open_download("m", job.id)
        assert not list(service.artifacts.glob("*.zip"))


def test_cancel_keeps_shared_preparation(tmp_path, monkeypatch):
    entered = threading.Event()
    calls = []

    def build(*args, cancel, **kwargs):
        calls.append(cancel)
        if len(calls) == 1:
            entered.set()
            assert cancel.wait(3)
            from app.mission.exporter.export_cancel import check_cancelled

            check_cancelled(cancel)
        return MissionPackageDownload(io.BytesIO(b"second package"), None)

    with runtime(tmp_path, monkeypatch, builder=build) as (service, _):
        shared = service.cache.request("m", "a", "shared", b"shared slide inputs")
        first = service.start("m")
        assert entered.wait(3)
        second = service.start("m")
        assert second.id != first.id
        service.cancel("m", first.id)
        assert wait_state(service, first, {"cancelled"}).state == "cancelled"
        assert wait_state(service, second, {"ready"}).state == "ready"
        assert service.cache.current("m", "a", shared)
        with service.open_download("m", second.id).stream as stream:
            assert stream.read() == b"second package"


def test_saved_change_supersedes_pending_package(tmp_path, monkeypatch):
    entered = threading.Event()

    def build(*args, cancel, **kwargs):
        entered.set()
        assert cancel.wait(3)
        from app.mission.exporter.export_cancel import check_cancelled

        check_cancelled(cancel)

    with runtime(tmp_path, monkeypatch, builder=build) as (service, mission):
        job = service.start("m")
        assert entered.wait(3)
        mission.name = "Changed while preparing"
        storage.save_mission_v2(mission)
        assert wait_state(service, job, {"superseded"}).state == "superseded"
        assert not list(service.artifacts.glob("*.zip"))


def test_worker_failure_is_sanitized_and_retryable(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError("private operational file path")

    with runtime(tmp_path, monkeypatch, builder=fail) as (service, _):
        job = service.start("m")
        failed = wait_state(service, job, {"failed"})
        assert failed.error_code == "runtime"
        assert "private" not in failed.model_dump_json()
        assert service.start("m").id != job.id


def test_disabled_shared_renderer_remains_explicit_and_downloadable(
    tmp_path, monkeypatch
):
    from app.mission.slide_cache import coordinator

    monkeypatch.setattr(coordinator, "_runtime", None)
    with runtime(tmp_path, monkeypatch, enabled=True) as (service, _):
        ready = wait_state(service, service.start("m"), {"ready"})
        assert ready.briefing_status == "omitted"
        assert ready.warning_code in {"runtime", "data"}
        with service.open_download("m", ready.id).stream as stream, zipfile.ZipFile(
            stream
        ) as archive:
            assert "manifest.json" in archive.namelist()
            assert not any(name.endswith(".pdf") for name in archive.namelist())


def test_restart_recovers_abandoned_job_without_resetting_deadline(
    tmp_path, monkeypatch
):
    with runtime(tmp_path, monkeypatch, clock=lambda: 1000) as (first, _):
        ready = wait_state(first, first.start("m"), {"ready"})
        first.close()
        # Persist the state left by a crash between assembly and ready publication.
        first.jobs.write(
            ready.model_copy(update={"state": "preparing", "stage": "assembling"})
        )
        second = type(first)(
            None, None, enabled=False, cache=first.cache, clock=lambda: 1001
        )
        try:
            failed = wait_state(second, ready, {"failed"})
            assert failed.error_code == "runtime"
            assert failed.deadline == ready.deadline
            assert not second.path(ready.id).exists()
        finally:
            second.close()


def test_second_runtime_does_not_recover_an_active_export(tmp_path, monkeypatch):
    entered = threading.Event()

    def build(*args, cancel, **kwargs):
        entered.set()
        assert cancel.wait(3)
        from app.mission.exporter.export_cancel import check_cancelled

        check_cancelled(cancel)

    with runtime(tmp_path, monkeypatch, builder=build) as (first, _):
        job = first.start("m")
        assert entered.wait(3)
        second = type(first)(None, None, enabled=False, cache=first.cache)
        try:
            assert first.status("m", job.id).state == "preparing"
        finally:
            second.close()
            first.cancel("m", job.id)


def test_preparation_http_never_waits_for_cold_download(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.mission.package.preparation_routes import router
    from app.mission.routes_v2 import router as legacy_router

    entered, release = threading.Event(), threading.Event()

    def build(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return MissionPackageDownload(io.BytesIO(b"PK-owned snapshot"), None)

    with runtime(tmp_path, monkeypatch, builder=build) as (service, _):
        app = FastAPI()
        app.state.export_preparation_service = service
        app.include_router(router)
        app.include_router(legacy_router)
        try:
            with TestClient(app) as client:
                response = client.post("/api/v2/missions/m/export")
                assert response.status_code == 202
                assert entered.wait(2)
                path = response.headers["location"]
                job_id = response.json()["id"]
                assert client.get(path + "/download").status_code == 409
                assert client.get(path).json()["state"] == "preparing"
                assert client.get(path.replace("/m/", "/other/")).status_code == 404
                release.set()
                wait_state(service, service.status("m", job_id), {"ready"})
                downloaded = client.get(path + "/download")
                assert downloaded.content == b"PK-owned snapshot"
                assert (
                    downloaded.headers["x-export-fingerprint"]
                    == response.json()["fingerprint"]
                )
                assert client.post("/api/v2/missions/m/export").status_code == 200
        finally:
            release.set()
