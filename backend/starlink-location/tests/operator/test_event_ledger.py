"""Material event generations survive steady reads and cannot resurrect old cues."""

import sqlite3
from datetime import timedelta

import pytest


def event(clock, **updates):
    from app.operator.event_models import OperationalEvent

    return OperationalEvent(
        event_id="call-a-prep",
        mission_id="demo-mission",
        kind="call_prep",
        title="Synthetic preparation",
        due_at=clock.now(),
        schedule_key="schedule-one",
        **updates,
    )


def test_steady_feed_does_not_write_and_schedule_change_retires(service, clock):
    from app.operator.event_ledger import reconcile
    from app.operator.event_policy import EventPolicy

    with service.store.connect(write=True) as db:
        first = reconcile(db, [event(clock)], as_of=clock.now(), policy=EventPolicy())[
            0
        ]
        writes = db.total_changes
        again = reconcile(db, [event(clock)], as_of=clock.now(), policy=EventPolicy())[
            0
        ]
        assert again.notification.generation == first.notification.generation
        assert db.total_changes == writes
        moved = event(clock).model_copy(
            update={
                "due_at": clock.now() + timedelta(minutes=20),
                "schedule_key": "schedule-two",
            }
        )
        second = reconcile(db, [moved], as_of=clock.now(), policy=EventPolicy())[0]
        assert second.notification.generation != first.notification.generation
        assert db.execute(
            "SELECT state FROM event_transitions WHERE occurrence_id=? ORDER BY seq",
            (first.notification.generation,),
        ).fetchall() == [("accepted",), ("retired",)]
        # A restore/rewind of the identical obsolete schedule must not re-arm it.
        restored = reconcile(
            db, [event(clock)], as_of=clock.now(), policy=EventPolicy()
        )[0]
        assert restored.notification.retired


def test_notification_history_is_immutable(service, clock):
    from app.operator.event_ledger import reconcile
    from app.operator.event_policy import EventPolicy

    with service.store.connect(write=True) as db:
        reconcile(db, [event(clock)], as_of=clock.now(), policy=EventPolicy())
    for table in ("event_occurrences", "event_transitions"):
        with pytest.raises(sqlite3.IntegrityError), service.store.connect(
            write=True
        ) as db:
            db.execute(f"DELETE FROM {table}")


def test_acknowledgment_receipt_recovers_without_operational_revision(
    service, clock, tmp_path
):
    from uuid import uuid4
    from app.operator.event_models import AckReceipt
    from app.operator.event_ledger import reconcile
    from app.operator.event_policy import EventPolicy
    from app.operator.backup import backup_store, validated_backup
    from app.operator.recovery import verify_store

    command_id, acknowledgment_id = str(uuid4()), str(uuid4())
    with service.store.connect(write=True) as db:
        row = reconcile(db, [event(clock)], as_of=clock.now(), policy=EventPolicy())[0]
        receipt = AckReceipt(
            command_id=command_id,
            acknowledgment_id=acknowledgment_id,
            occurrence_id=row.notification.generation,
            severity_generation=0,
            acknowledged_at=clock.now(),
        )
        db.execute(
            "INSERT INTO event_acknowledgments VALUES (?, ?, 0, ?, ?)",
            (
                acknowledgment_id,
                row.notification.generation,
                command_id,
                clock.now().isoformat(),
            ),
        )
        db.execute(
            "INSERT INTO commands VALUES (?, ?, 'ack-hash', 1, ?, 200, ?)",
            (
                command_id,
                str(uuid4()),
                clock.now().isoformat(),
                receipt.model_dump_json(),
            ),
        )
    assert verify_store(service.store).ready
    manifest = backup_store(service.store, directory=tmp_path / "backups")
    info, _ = validated_backup(manifest, clock=clock)
    assert info["H"] == 0
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM revisions").fetchone() == (0,)
        reconciled = reconcile(
            db, [event(clock)], as_of=clock.now(), policy=EventPolicy()
        )[0]
        assert reconciled.notification.acknowledged
        assert reconciled.notification.acknowledged_at == clock.now()
