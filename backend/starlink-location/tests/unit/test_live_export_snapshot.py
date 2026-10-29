"""Mid-mission exports retain their captured revision while live inputs change."""

import json
import threading
import zipfile

import pytest

from app.mission import storage
from app.mission.package.customer_artifacts import build_mission_package_download
from tests.unit.test_export_preparation import runtime, wait_state
from tests.unit.test_export_snapshot import BASE, export_inputs

__all__ = ["export_inputs"]


def test_saved_change_during_assembly_downloads_original_snapshot(
    tmp_path, monkeypatch
):
    entered, release = threading.Event(), threading.Event()

    def build(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return build_mission_package_download(*args, **kwargs)

    with runtime(tmp_path, monkeypatch, builder=build) as (service, mission):
        try:
            job = service.start("m")
            assert entered.wait(3)
            mission.name = "Saved after export started"
            storage.save_mission_v2(mission)
            release.set()
            completed = wait_state(service, job, {"ready", "failed", "superseded"})
            assert completed.state == "ready"
            with service.open_download("m", job.id).stream as source, zipfile.ZipFile(
                source
            ) as package:
                assert json.loads(package.read("mission.json"))["name"] == "Example"
        finally:
            release.set()


def test_saved_change_during_telemetry_capture_keeps_original_plan(
    tmp_path, monkeypatch
):
    def capture(_):
        mission = storage.load_mission_v2("m")
        mission.name = "Live update during telemetry capture"
        storage.save_mission_v2(mission)
        return {
            "schema_version": 1,
            "capture_policy": "sequential_component_snapshots",
            "components": {},
            "files": {},
        }

    with runtime(tmp_path, monkeypatch, archive_capture=capture) as (service, _):
        job = service.start("m")
        assert (
            wait_state(service, job, {"ready", "failed", "superseded"}).state == "ready"
        )
        with service.open_download("m", job.id).stream as source, zipfile.ZipFile(
            source
        ) as package:
            assert json.loads(package.read("mission.json"))["name"] == "Example"


def test_assembly_does_not_rescan_live_renderer_or_dependencies(tmp_path, monkeypatch):
    from app.mission.package import preparation_worker

    entered, release = threading.Event(), threading.Event()

    def build(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return build_mission_package_download(*args, **kwargs)

    with runtime(tmp_path, monkeypatch, builder=build) as (service, _):
        try:
            job = service.start("m")
            assert entered.wait(3)

            def forbidden(*args, **kwargs):
                raise AssertionError("Assembly must use its immutable captured inputs")

            monkeypatch.setattr(service, "capture_revision", forbidden)
            monkeypatch.setattr(preparation_worker, "capture_is_current", forbidden)
            release.set()
            assert (
                wait_state(service, job, {"ready", "failed", "superseded"}).state
                == "ready"
            )
        finally:
            release.set()


def test_queued_snapshot_survives_restart_and_later_save(tmp_path, monkeypatch):
    from app.mission.package.preparation_worker import PreparationWorker

    original_run = PreparationWorker.run
    monkeypatch.setattr(PreparationWorker, "run", lambda self: None)
    with runtime(tmp_path, monkeypatch) as (first, mission):
        job = first.start("m")
        first.captures.clear()
        first.close()
        mission.name = "Newer plan after process loss"
        storage.save_mission_v2(mission)
        monkeypatch.setattr(PreparationWorker, "run", original_run)
        second = type(first)(None, None, enabled=False, cache=first.cache)
        try:
            assert (
                wait_state(second, job, {"ready", "failed", "superseded"}).state
                == "ready"
            )
            with second.open_download("m", job.id).stream as source, zipfile.ZipFile(
                source
            ) as package:
                assert json.loads(package.read("mission.json"))["name"] == "Example"
        finally:
            second.close()


def test_leg_composition_is_frozen_before_telemetry_capture(tmp_path, monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from app.mission.package import operations_archive
    from app.services.telemetry_archive.store import ArchiveStore

    @contextmanager
    def no_journal(_):
        yield None

    monkeypatch.setattr(operations_archive, "runtime_for", no_journal)
    flight = SimpleNamespace(
        archive=ArchiveStore(tmp_path / "flight.sqlite3"),
        preparations=SimpleNamespace(load_mission=storage.load_mission_v2),
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(flight_event_runtime=flight))
    )

    def capture(mission_id, owner, representation):
        mission = storage.load_mission_v2(mission_id)
        mission.legs = [mission.legs[0].model_copy(update={"id": "new-leg"})]
        storage.save_mission_v2(mission)
        return operations_archive.capture_archive(
            request, mission_id, owner=owner, telemetry_format=representation
        )

    with runtime(tmp_path, monkeypatch, archive_capture_owned=capture) as (service, _):
        job = service.start("m")
        assert (
            wait_state(service, job, {"ready", "failed", "superseded"}).state == "ready"
        )
        with service.open_download("m", job.id).stream as source, zipfile.ZipFile(
            source
        ) as package:
            assert [
                leg["id"] for leg in json.loads(package.read("mission.json"))["legs"]
            ] == ["a"]
            assert [
                leg["leg_id"]
                for leg in json.loads(package.read("telemetry/manifest.json"))["legs"]
            ] == ["a"]


def test_planning_snapshot_quota_is_atomic_and_counts_toward_file_reservations(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    import pytest

    from app.mission.package import archive_files, preparation_store
    from app.mission.slide_cache.store import SlideStore

    monkeypatch.setattr(preparation_store, "MAX_ARCHIVE_STORAGE_BYTES", 1000)
    monkeypatch.setattr(archive_files, "DISK_QUOTA", 1000)
    monkeypatch.setattr(archive_files, "CAPTURE_RESERVATION", 400)
    cache = SlideStore(tmp_path / "cache.sqlite3")
    jobs = preparation_store.PreparationStore(cache)
    planning = SimpleNamespace(encode=lambda: b"p" * 700)

    def job(identity):
        return preparation_store.ExportPreparation(
            id=identity,
            mission_id="m",
            state="queued",
            fingerprint="f",
            queued_at=0,
            deadline=600,
        )

    jobs.write(job("first"), planning=planning)
    with pytest.raises(RuntimeError, match="storage"):
        jobs.write(job("second"), planning=planning)
    with pytest.raises(KeyError):
        jobs.read("m", "second")
    files = archive_files.ArchiveFiles(cache)
    with pytest.raises(RuntimeError, match="storage"), files.capture():
        pytest.fail("Planning bytes must remain reserved while queued")
    jobs.discard_archive("first")
    jobs.write(job("second"), planning=planning)
    jobs.discard_archive("second")
    with cache.connection() as db:
        assert (
            db.execute("SELECT count(*) FROM export_planning_snapshots").fetchone()[0]
            == 0
        )
        assert (
            db.execute("SELECT count(*) FROM export_artifact_owners").fetchone()[0] == 0
        )


def test_prepared_pages_are_copied_and_matched_to_frozen_inputs(tmp_path, monkeypatch):
    from dataclasses import replace

    from app.mission.package.customer_artifacts import (
        CustomerBriefingArtifacts,
        CustomerBriefingOutcome,
    )
    from app.mission.package.frozen_planning import FrozenPlanning, capture_planning
    from app.mission.slide_cache import assembly
    from app.mission.slide_cache.capture import normalize_capture
    from app.mission.slide_cache.identity import encode_snapshot

    with runtime(tmp_path, monkeypatch) as (service, _):
        raw = service.capture("m")
        original = capture_planning(raw, service.cache, enabled=False)
        _, _, _, expected = normalize_capture(
            replace(
                raw, renderer_revision=raw.renderer_revision.removesuffix(":disabled")
            )
        )
        fingerprint, inputs = expected["a"]
        token = service.cache.request("m", "a", fingerprint, inputs)
        assert service.cache.claim()["token"] == token
        assert service.cache.publish(
            "m",
            "a",
            token,
            encode_snapshot(original.snapshot),
            b"qualified-pdf",
            b"qualified-evidence",
        )
        seen = []

        def assemble(snapshot, records, *, cancel=None):
            seen.append(records["a"]["state"])
            if records["a"]["state"] != "ready":
                return CustomerBriefingOutcome("omitted", "busy", None)
            assert records["a"]["pdf"] == b"qualified-pdf"
            return CustomerBriefingOutcome(
                "included",
                None,
                CustomerBriefingArtifacts(
                    records["a"]["pdf"], records["a"]["evidence"]
                ),
            )

        monkeypatch.setattr(assembly, "assemble_customer_pdf", assemble)
        frozen = capture_planning(raw, service.cache, enabled=True)
        service.cache.invalidate("m", ["a"])
        restored = FrozenPlanning.decode(frozen.encode())
        assert restored.snapshot == frozen.snapshot
        assert restored.briefing.artifacts.pdf == b"qualified-pdf"
        assert (
            capture_planning(raw, service.cache, enabled=True).briefing.status
            == "omitted"
        )
        assert seen == ["ready", "failed"]


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("cached_timeline", [False, True])
def test_forecast_csv_rebuilds_from_frozen_inputs_without_ready_pages(
    export_inputs, tmp_path, enabled, cached_timeline
):
    from datetime import timedelta

    from app.mission.package.preparation import ExportPreparationService
    from app.mission.slide_cache.store import SlideStore

    mission, routes, pois, _ = export_inputs
    if cached_timeline:
        from app.mission.exporter.snapshot import capture_export_snapshot
        from app.mission.models import MissionLegTimeline

        previous = capture_export_snapshot("m", routes, pois)
        storage.save_mission_timeline(
            "l",
            MissionLegTimeline.model_validate_json(previous.legs[0].timeline_json),
            "m",
        )
    mission.legs[0].adjusted_departure_time = BASE + timedelta(hours=4)
    storage.save_mission_v2(mission)
    service = ExportPreparationService(
        routes,
        pois,
        enabled=enabled,
        cache=SlideStore(tmp_path / "export-cache.sqlite3"),
    )
    try:
        job = service.start("m")
        ready = wait_state(service, job, {"ready", "failed", "superseded"})
        assert ready.state == "ready"
        with service.open_download("m", job.id).stream as source, zipfile.ZipFile(
            source
        ) as package:
            names = [
                name
                for name in package.namelist()
                if name.startswith("exports/legs/") and name.endswith("timeline.csv")
            ]
            assert names, "Missing cached customer pages must not omit forecast CSVs"
            text = package.read(names[0]).decode()
            assert "2026-10-07T12:00:00" in text
    finally:
        service.close()


@pytest.mark.parametrize("failure", ["cancel", "deadline"])
def test_capture_pdf_assembly_propagates_cancellation_and_deadline(
    tmp_path, monkeypatch, failure
):
    from app.mission.exporter.export_cancel import ExportCancelled, check_cancelled
    from app.mission.package.archive_errors import ArchiveDeadlineError
    from app.mission.package.frozen_planning import capture_planning
    from app.mission.slide_cache import assembly

    active = False

    class Cancel:
        def is_set(self):
            if active and failure == "deadline":
                raise ArchiveDeadlineError()
            return active

    def assemble(snapshot, records, *, cancel=None):
        nonlocal active
        active = True
        check_cancelled(cancel)

    monkeypatch.setattr(assembly, "assemble_customer_pdf", assemble)
    with runtime(tmp_path, monkeypatch) as (service, _):
        raw = service.capture("m")
        with pytest.raises(
            ArchiveDeadlineError if failure == "deadline" else ExportCancelled
        ):
            capture_planning(raw, service.cache, enabled=True, cancel=Cancel())


def test_recovered_ready_zip_releases_duplicate_planning_bytes(tmp_path, monkeypatch):
    from app.mission.package.frozen_planning import capture_planning

    with runtime(tmp_path, monkeypatch) as (service, _):
        raw = service.capture("m")
        job = wait_state(service, service.start("m"), {"ready"})
        service.close()
        planning = capture_planning(raw, service.cache, enabled=False)
        service.jobs.write(job, planning=planning)
        assert service.jobs.planning(job.id) is not None
        service.recover()
        assert service.jobs.planning(job.id) is None
        assert service.path(job.id).is_file()
