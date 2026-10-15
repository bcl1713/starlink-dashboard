"""Durability/admission must not depend on a surviving browser request."""

from datetime import datetime, timedelta, timezone

import pytest


def store(tmp_path):
    from app.mission.itinerary_import.store import ImportStore

    return ImportStore(tmp_path / "imports")


def test_idempotency_survives_restart_and_rejects_changed_upload(tmp_path):
    s = store(tmp_path)
    op = s.create(b"pdf", [("route.kml", b"kml")], "same")
    assert store(tmp_path).create(b"pdf", [("route.kml", b"kml")], "same").id == op.id
    with pytest.raises(ValueError, match="different"):
        s.create(b"changed", [("route.kml", b"kml")], "same")
    assert len(list(s.root.glob("*/operation.json"))) == 1


def test_generation_protects_corrections_and_cancellation(tmp_path):
    s = store(tmp_path)
    op = s.create(b"pdf", [("r.kml", b"kml")], "key")
    changed = s.update(op.id, op.generation, state="needs_input")
    with pytest.raises(ValueError, match="stale"):
        s.update(op.id, op.generation, state="running")
    cancelled = s.update(op.id, changed.generation, state="cancelled")
    assert store(tmp_path).read(op.id).state == "cancelled"
    assert cancelled.generation > changed.generation
    assert "owned" not in cancelled.model_dump_json()


def test_upload_limits_and_admission(tmp_path):
    s = store(tmp_path)
    for pdf, kmls in [
        (b"x" * (10 * 1024 * 1024 + 1), [("r.kml", b"k")]),
        (b"p", [("r.kml", b"k")] * 17),
        (b"p", []),
    ]:
        with pytest.raises(ValueError):
            s.create(pdf, kmls, "bad")
    for i in range(9):
        s.create(b"p", [("r.kml", b"k")], str(i))
    with pytest.raises(OverflowError):
        s.create(b"p", [("r.kml", b"k")], "tenth")


def test_expired_operation_cannot_resume(tmp_path):
    s = store(tmp_path)
    op = s.create(b"p", [("r.kml", b"k")], "key")
    s.update(
        op.id, op.generation, deadline=datetime.now(timezone.utc) - timedelta(seconds=1)
    )
    assert s.pending() == []
    assert s.read(op.id).state == "failed"


def test_ready_revision_resumes_after_restart(tmp_path):
    s = store(tmp_path)
    op = s.create(b"pdf", [("r.kml", b"kml")], "ready", "existing")
    s.update(op.id, op.generation, state="ready", stage="applying_changes")
    assert [item.id for item in store(tmp_path).pending()] == [op.id]
