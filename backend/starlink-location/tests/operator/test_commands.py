"""Accepted changes and their audit/receipt either all commit or all roll back."""

import pytest
from pydantic import ValidationError

from app.operator.errors import OperatorError
from app.operator.models import RemoveRecord, RestoreRecord
from tests.operator.service_helpers import create, submit, update


def test_late_entry_correct_remove_restore(service, record_data, clock):
    original = create(service, record_data)
    assert original.time.ended_at.hour == 14
    assert original.recorded_at.hour == 16
    original = create(
        service,
        record_data,
        time=original.time.model_copy(
            update={"ended_at": original.time.ended_at.replace(hour=15, minute=45)}
        ),
    )
    clock.advance(10)
    corrected = submit(
        service,
        update(
            service,
            original,
            time=original.time.model_copy(
                update={"ended_at": original.time.ended_at.replace(minute=35)}
            ),
        ),
    ).saved_records[0]
    removed = submit(
        service, RemoveRecord(record_id=original.record_id, expected_version=2)
    ).saved_records[0]
    restored = submit(
        service, RestoreRecord(record_id=original.record_id, expected_version=3)
    ).saved_records[0]
    assert service.get(str(original.record_id)) == restored
    with service.store.connect() as db:
        assert (
            db.execute(
                "SELECT count(*) FROM current_records WHERE record_id=?",
                (str(original.record_id),),
            ).fetchone()[0]
            == 1
        )
    history = service.history(str(original.record_id)).items
    assert [r.version for r in history] == [1, 2, 3, 4]
    assert [r.time.ended_at.minute for r in history] == [45, 35, 35, 35]
    assert history[1].recorded_at > history[0].recorded_at
    assert removed.deleted and not restored.deleted
    assert [(r.reason, r.reason_origin) for r in history[1:]] == [
        ("Operator correction", "automatic"),
        ("Operator removal", "automatic"),
        ("Operator restoration", "automatic"),
    ]
    assert original.provenance.kind == "operator_reported"
    assert original.provenance.mutation_origin == "retrospective"


@pytest.mark.parametrize(
    "note, reason, origin",
    [
        (None, "Operator correction", "automatic"),
        ("  ", "Operator correction", "automatic"),
        ("Corrected report", "Corrected report", "operator"),
    ],
)
def test_optional_audit_reasons(service, record_data, note, reason, origin):
    saved = create(service, record_data)
    result = submit(service, update(service, saved, audit_note=note)).saved_records[0]
    assert (result.reason, result.reason_origin) == (reason, origin)
    with pytest.raises(ValidationError):
        update(service, result, audit_note="x" * 1001)


class FailAfterWrite:
    """Wrap real SQLite; fail after an actual selected low-level write."""

    def __init__(self, db, prefix, occurrence):
        self.db, self.prefix, self.remaining = db, prefix, occurrence

    def execute(self, sql, parameters=()):
        result = self.db.execute(sql, parameters)
        if sql.startswith(self.prefix):
            self.remaining -= 1
            if self.remaining == 0:
                raise RuntimeError("injected persistence failure")
        return result

    def __getattr__(self, name):
        return getattr(self.db, name)


@pytest.mark.parametrize(
    "prefix",
    [
        "INSERT INTO revisions",
        "UPDATE records",
        "DELETE FROM current_links",
        "INSERT INTO current_links",
        "INSERT INTO commands",
    ],
)
@pytest.mark.parametrize("count", [1, 2])
def test_atomic_failure_barriers(service, record_data, monkeypatch, prefix, count):
    from app.operator import commands

    parent = create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Conference"},
    )
    originals = [
        create(
            service,
            record_data,
            record_type="call",
            payload={
                "entry_type": "call",
                "title": "Call",
                "conference_id": str(parent.record_id),
            },
        )
        for _ in range(count)
    ]
    with service.store.connect() as db:
        before = {
            t: db.execute(f"SELECT * FROM {t}").fetchall()
            for t in ("revisions", "records", "current_links", "commands")
        }
    real = commands._persist_changes

    def fail(db, changes, receipt, **kwargs):
        # Two-record internal fixture, no production batch command.
        if count == 2:
            second = changes[0].model_copy(
                update={
                    "record_id": originals[1].record_id,
                    "journal_seq": changes[0].journal_seq + 1,
                }
            )
            changes.append(second)
            receipt.saved_records.append(second)
        real(
            FailAfterWrite(
                db, prefix, count if prefix != "INSERT INTO commands" else 1
            ),
            changes,
            receipt,
            **kwargs,
        )

    monkeypatch.setattr(commands, "_persist_changes", fail)
    with pytest.raises(RuntimeError, match="injected"):
        submit(service, update(service, originals[0]))
    with service.store.connect() as db:
        assert {
            t: db.execute(f"SELECT * FROM {t}").fetchall() for t in before
        } == before
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
