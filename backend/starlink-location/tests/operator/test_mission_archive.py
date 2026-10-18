"""The portable mission ZIP adds history without restoring it on plan import."""

import hashlib
import io
import json
import zipfile

from app.operator.projections import capture_projection
from tests.operator.service_helpers import create, submit, update


def test_archive_contains_full_history_and_distinguishes_operational_chronology(
    service, record_data
):
    from app.mission.package.operations_archive import journal_files

    first = create(service, record_data)
    corrected = submit(
        service,
        update(
            service,
            first,
            payload={
                "entry_type": "note",
                "title": "Corrected synthetic note",
                "note": "Corrected body",
            },
        ),
    ).saved_records[0]
    create(
        service,
        record_data,
        time={
            "occurred_at": "2026-10-17T12:00:00Z",
            "precision": "exact",
            "end_state": "instant",
        },
    )
    bundle = capture_projection(
        service.store, mission_id="demo-mission", include_audit=True
    )
    files = journal_files(bundle)
    manifest = json.loads(files["operations/manifest.json"])
    for name, digest in manifest["checksums"].items():
        assert hashlib.sha256(files[name]).hexdigest() == digest
    journal = json.loads(files["operations/journal.json"])
    assert journal["schema_version"] == 1
    assert [
        r["time"]["occurred_at"] for r in journal["chronological_revisions"]
    ] == sorted(r["time"]["occurred_at"] for r in journal["chronological_revisions"])
    audit = [json.loads(line) for line in files["operations/audit.jsonl"].splitlines()]
    assert len(audit) == 3
    assert audit[0]["payload"]["note"] == "Synthetic content"
    assert audit[1]["record_id"] == str(corrected.record_id)
    assert (
        journal["ordering"]["unknown_actual_time"]
        == "after_known_actual_times; acceptance_sequence_tiebreaker"
    )
    assert b"Corrected synthetic note" in files["operations/handover.txt"]
    assert files == journal_files(bundle)


def test_additions_preserve_every_existing_member_and_update_manifest():
    from app.mission.package.operations_archive import append_archive

    original = io.BytesIO()
    with zipfile.ZipFile(original, "w") as archive:
        archive.writestr("mission.json", b'{"id":"synthetic"}')
        archive.writestr("exports/mission/Customer briefing.pdf", b"%PDF-original")
        archive.writestr(
            "manifest.json",
            json.dumps(
                {
                    "version": "2.0",
                    "file_structure": {},
                    "statistics": {"total_files": 3},
                }
            ),
        )
    snapshot = {
        "schema_version": 1,
        "files": {"operations/current.json": "[]\n"},
        "components": {"operator": {"high_water": 0}},
        "capture_policy": "sequential_component_snapshots",
    }
    result = append_archive(
        original, snapshot, planning_fingerprint="plan", cancel=None
    )
    with result, zipfile.ZipFile(result) as archive:
        assert archive.read("exports/mission/Customer briefing.pdf") == b"%PDF-original"
        assert archive.read("mission.json") == b'{"id":"synthetic"}'
        assert archive.read("operations/current.json") == b"[]\n"
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == "2.0"
        assert manifest["archive_components"]["planning_fingerprint"] == "plan"
        assert manifest["statistics"]["total_files"] == len(archive.namelist())
        assert len(archive.namelist()) == len(set(archive.namelist()))
    original.close()


def test_archival_projection_includes_persisted_model_occurrences_without_polling(
    service, record_data
):
    from app.mission.package.operations_archive import journal_files

    create(service, record_data)
    bundle = capture_projection(
        service.store,
        mission_id="demo-mission",
        include_audit=True,
        include_events=True,
    )
    files = journal_files(bundle)
    events = json.loads(files["operations/events.json"])
    assert events["schema_version"] == 1
    assert events["capture_policy"] == "persisted_only; no_model_recalculation"
    assert events["occurrences"] == []
    assert events["acknowledgments"] == []


def test_archive_keeps_real_pop_advisories_modeled(production, service, clock):
    from types import SimpleNamespace

    from app.mission.package.operations_archive import capture_archive
    from app.mission.pop_status import PopStatusService
    from app.operator.event_feed import build_snapshot
    from app.operator.runtime import OperatorRuntime

    adapter, publication, state, config, routes, _, _ = production
    adapter.pop_service = PopStatusService(routes, lambda: config)
    runtime = OperatorRuntime.start(service.store.settings, clock=clock)
    runtime.event_publication = publication
    try:
        build_snapshot(runtime, "demo-mission", adapter)
        clock.advance(16)
        state["telemetry"].position.observed_at = clock.now()
        state["telemetry"].position.speed_observed_at = clock.now()
        build_snapshot(runtime, "demo-mission", adapter)
        request = SimpleNamespace(
            app=SimpleNamespace(state=SimpleNamespace(operator_runtime=runtime))
        )
        snapshot = capture_archive(request, "demo-mission")
        events = json.loads(snapshot["files"]["operations/events.json"])
        modeled = [
            r["event"]
            for r in events["occurrences"]
            if r["event"]["provenance"] == "modeled"
        ]
        assert modeled
        assert any("pop" in json.dumps(r).lower() for r in modeled)
        assert all(r["provenance"] == "modeled" for r in modeled)
    finally:
        runtime.close()


def test_enabled_unavailable_journal_fails_without_creating_empty_archive(
    clock, tmp_path
):
    from types import SimpleNamespace

    import pytest

    from app.mission.package.operations_archive import capture_archive
    from app.operator.runtime import OperatorRuntime
    from app.operator.settings import OperatorSettings

    runtime = OperatorRuntime(OperatorSettings(enabled=True, root=tmp_path), clock)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(operator_runtime=runtime))
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        capture_archive(request, "demo-mission")


def test_concurrent_correction_cannot_change_prepared_journal(
    service, record_data, clock, tmp_path
):
    import threading
    import time
    from types import SimpleNamespace

    from app.mission.package.customer_artifacts import MissionPackageDownload
    from app.mission.package.operations_archive import capture_archive
    from app.mission.package.preparation import ExportPreparationService
    from app.mission.slide_cache.store import SlideStore
    from app.operator.runtime import OperatorRuntime
    from tests.unit.test_customer_package import data_package

    first = create(service, record_data)
    runtime = OperatorRuntime.start(service.store.settings, clock=clock)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(operator_runtime=runtime))
    )
    entered, release = threading.Event(), threading.Event()

    def build(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return MissionPackageDownload(data_package(), None)

    preparation = ExportPreparationService(
        None,
        None,
        enabled=False,
        cache=SlideStore(tmp_path / "exports/slides.sqlite3"),
        builder=build,
        archive_capture=lambda mission: capture_archive(request, mission),
    )
    try:
        job = preparation.start("demo-mission")
        assert entered.wait(2)
        frozen = preparation.jobs.archive(job.id)
        submit(
            service,
            update(
                service,
                first,
                payload={
                    "entry_type": "note",
                    "title": "Later correction",
                    "note": "Later body",
                },
            ),
        )
        release.set()
        deadline = time.monotonic() + 3
        while preparation.status("demo-mission", job.id).state in (
            "queued",
            "preparing",
        ):
            assert time.monotonic() < deadline
            time.sleep(0.01)
        assert preparation.status("demo-mission", job.id).state == "ready"
        with preparation.open_download(
            "demo-mission", job.id
        ).stream as stream, zipfile.ZipFile(stream) as archive:
            assert (
                archive.read("operations/current.json").decode()
                == frozen["files"]["operations/current.json"]
            )
            assert b"Later correction" not in archive.read("operations/audit.jsonl")
        latest = preparation.start("demo-mission")
        assert latest.fingerprint != job.fingerprint
    finally:
        release.set()
        preparation.close()
        runtime.close()
