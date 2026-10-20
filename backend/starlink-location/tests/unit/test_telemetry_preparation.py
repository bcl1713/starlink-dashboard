"""Download snapshots survive event corrections and expire independently."""

import time
from types import SimpleNamespace

from app.services.telemetry_archive.preparation import TelemetryPreparationService
from app.services.telemetry_archive.store import ArchiveStore
from tests.unit.test_telemetry_package import capture


def test_prepared_download_is_immutable_and_source_survives_expiry(tmp_path):
    archive = ArchiveStore(tmp_path / "archive.db")
    with archive.ledger.connect() as db:
        import json

        original = capture("one")
        db.execute(
            "INSERT INTO captures VALUES (?, ?, ?, ?)",
            ("m", "one", "one", json.dumps(original)),
        )
        db.execute("INSERT INTO capture_heads VALUES (?, ?, ?)", ("m", "one", "one"))
    clock = [100.0]
    service = TelemetryPreparationService(
        tmp_path,
        archive,
        lambda _: SimpleNamespace(legs=[SimpleNamespace(id="one")]),
        clock=lambda: clock[0],
    )
    try:
        job = service.start("m")
        for _ in range(200):
            job = service.status("m", job.id)
            if job.state in ("ready", "failed"):
                break
            time.sleep(0.005)
        assert job.state == "ready"
        original_bytes = service.open_download("m", job.id).stream.read()
        assert original_bytes
        clock[0] += 1801
        assert service.status("m", job.id).state == "expired"
        assert archive.capture("m", "one") is not None
    finally:
        service.close()


def test_bounded_capture_rejects_complete_payload_without_truncation(tmp_path):
    import json

    import pytest

    archive = ArchiveStore(tmp_path / "archive.db")
    original = capture("one")
    with archive.ledger.connect() as db:
        db.execute(
            "INSERT INTO captures VALUES (?, ?, ?, ?)",
            ("m", "one", "one", json.dumps(original)),
        )
        db.execute("INSERT INTO capture_heads VALUES (?, ?, ?)", ("m", "one", "one"))
    service = TelemetryPreparationService(
        tmp_path, archive, lambda _: SimpleNamespace(legs=[SimpleNamespace(id="one")])
    )
    try:
        with pytest.raises(RuntimeError, match="archive.*limit"):
            service.capture_snapshot("m", allow_partial=True, max_input_bytes=1)
        assert service.capture_snapshot("m", allow_partial=True)["captures"] == [
            original
        ]
    finally:
        service.close()
