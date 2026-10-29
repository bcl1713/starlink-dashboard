"""Persistent artifact ownership includes unacknowledged and overlapping work."""

import pytest

from app.mission.slide_cache.store import SlideStore


def test_failed_unacknowledged_capture_releases_files_and_quota(tmp_path):
    from app.mission.package.archive_files import ArchiveFiles

    files = ArchiveFiles(SlideStore(tmp_path / "cache.db"))
    with pytest.raises(ValueError, match="capture failed"), files.capture() as owner:
        directory = owner.directory
        with owner.open_sidecar() as stream:
            stream.write(b"partial evidence")
        raise ValueError("capture failed")
    assert not directory.exists()
    with files.cache.connection() as db:
        assert (
            db.execute("SELECT count(*) FROM export_artifact_owners").fetchone()[0] == 0
        )


def test_snapshot_attachment_survives_another_store_and_is_released_on_expiry(tmp_path):
    from app.mission.package.archive_files import ArchiveFiles
    from app.mission.package.preparation_store import (
        ExportPreparation,
        PreparationStore,
    )

    cache = SlideStore(tmp_path / "cache.db")
    files = ArchiveFiles(cache)
    jobs = PreparationStore(cache)
    with files.capture() as owner:
        with owner.open_sidecar() as stream:
            stream.write(b"immutable evidence")
        attachment = owner.publish({"members": {}, "uncompressed_bytes": 18})
        job = ExportPreparation(
            id="job",
            mission_id="m",
            state="queued",
            fingerprint="f",
            queued_at=1,
            deadline=601,
        )
        jobs.write(job, archive={"files": {}, "attachments": [attachment]}, owner=owner)
    other = ArchiveFiles(cache)
    assert other.path(attachment).read_bytes() == b"immutable evidence"
    job.state = "expired"
    jobs.write(job)
    other.sweep(jobs)
    assert not owner.directory.exists()


def test_quota_rejection_does_not_remove_existing_capture(tmp_path):
    from app.mission.package.archive_errors import ArchiveCapacityError
    from app.mission.package.archive_files import ArchiveFiles

    files = ArchiveFiles(SlideStore(tmp_path / "cache.db"))
    with files.capture() as first:
        first_path = first.directory
        with pytest.raises(ArchiveCapacityError), files.capture():
            pytest.fail("Unreserved capture was permitted")
        assert first_path.is_dir()


def test_arbitrary_attachment_paths_are_rejected(tmp_path):
    from app.mission.package.archive_files import ArchiveFiles

    files = ArchiveFiles(SlideStore(tmp_path / "cache.db"))
    with pytest.raises(ValueError):
        files.path({"id": "../../archive.db"})


@pytest.mark.parametrize("representation", ["full", "compact"])
def test_real_mission_preparation_uses_owned_streaming_telemetry(
    tmp_path, monkeypatch, representation
):
    import csv
    import io
    import zipfile
    from types import SimpleNamespace

    from app.mission import storage
    from app.mission.package.customer_artifacts import MissionPackageDownload
    from app.mission.package.operations_archive import capture_archive
    from app.services.telemetry_archive.store import ArchiveStore
    from tests.unit.test_customer_package import data_package
    from tests.unit.test_export_preparation import runtime, wait_state
    from tests.unit.test_streaming_telemetry import seed

    archive = ArchiveStore(tmp_path / "archive.db")
    seed(archive)
    flight = SimpleNamespace(
        archive=archive,
        preparations=SimpleNamespace(load_mission=storage.load_mission_v2),
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(flight_event_runtime=flight))
    )

    def owned(mission_id, owner, telemetry_format):
        return capture_archive(
            request, mission_id, owner=owner, telemetry_format=telemetry_format
        )

    with runtime(
        tmp_path,
        monkeypatch,
        archive_capture_owned=owned,
        builder=lambda *a, **kw: MissionPackageDownload(data_package(), None),
    ) as (service, mission):
        mission.legs[0].id = "one"
        storage.save_mission_v2(mission)
        job = service.start("m", telemetry_format=representation)
        ready = wait_state(service, job, {"ready", "failed"})
        assert ready.state == "ready"
        with service.open_download("m", job.id).stream as stream, zipfile.ZipFile(
            stream
        ) as package:
            rows = list(
                csv.DictReader(
                    io.StringIO(
                        package.read("telemetry/legs/001/observations.csv").decode()
                    )
                )
            )
            assert len(rows) == 7
            assert ("series_id" in rows[0]) == (representation == "compact")
            assert package.testzip() is None
        reused = service.start("m", telemetry_format=representation)
        assert reused.id == job.id
        with service.cache.connection() as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM export_artifact_owners WHERE kind='capture'"
                ).fetchone()[0]
                == 0
            )


async def test_request_cancellation_before_acknowledgment_reaps_capture(
    tmp_path, monkeypatch
):
    import asyncio
    import threading

    from app.mission.package.export_job import prepare_for_request
    from tests.unit.test_export_preparation import runtime

    entered, finished = threading.Event(), threading.Event()

    def capture(mission_id, owner, representation):
        try:
            with owner.open_sidecar() as stream:
                stream.write(b"partial")
                entered.set()
                while True:
                    owner.check()
                    finished.wait(0.005)
        finally:
            finished.set()

    class Request:
        async def is_disconnected(self):
            return False

    with runtime(tmp_path, monkeypatch, archive_capture_owned=capture) as (service, _):
        task = asyncio.create_task(prepare_for_request(Request(), service, "m"))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert finished.is_set()
            assert not list(service.files.root.iterdir())
            assert service.jobs.all() == []
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def test_capture_deadline_releases_unacknowledged_files(tmp_path):
    from app.mission.package.archive_errors import ArchiveDeadlineError
    from app.mission.package.archive_files import ArchiveFiles

    now = [1000.0]
    files = ArchiveFiles(SlideStore(tmp_path / "cache.db"), clock=lambda: now[0])
    with pytest.raises(ArchiveDeadlineError), files.capture() as owner:
        with owner.open_sidecar() as stream:
            stream.write(b"partial")
        now[0] += 601
        owner.check()
    assert not list(files.root.iterdir())


def test_upgrade_accounts_for_existing_ready_download_without_changing_it(tmp_path):
    from app.mission.package.archive_files import ArchiveFiles
    from app.mission.package.preparation_store import (
        ExportPreparation,
        PreparationStore,
    )

    cache = SlideStore(tmp_path / "cache.db")
    files, jobs = ArchiveFiles(cache), PreparationStore(cache)
    files.downloads.mkdir()
    path = files.downloads / "old-job.zip"
    path.write_bytes(b"legacy ready download")
    job = ExportPreparation(
        id="old-job",
        mission_id="m",
        state="ready",
        fingerprint="old",
        queued_at=1,
        deadline=601,
        expires_at=10000,
    )
    jobs.write(job)
    files.sweep(jobs)
    files.sweep(jobs)
    assert path.read_bytes() == b"legacy ready download"
    with cache.connection() as db:
        assert db.execute(
            "SELECT sum(reserved),count(*) FROM export_artifact_owners"
        ).fetchone()[:] == (21, 1)
    job.state = "expired"
    jobs.write(job)
    files.sweep(jobs)
    assert not path.exists()
