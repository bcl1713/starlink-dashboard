"""Decisions share existing typed dependency rules through recovery."""

import pytest

from app.operator.errors import OperatorError
from app.operator.models import RemoveRecord, RestoreRecord
from app.operator.recovery import validate_connection
from tests.operator.service_helpers import create, submit, update
from tests.operator.test_transport_contract import decision, row


def targets(service, record_data):
    call = create(
        service,
        record_data,
        record_type="call",
        payload={"entry_type": "call", "title": "Synthetic call"},
    )
    conference = create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Synthetic conference"},
    )
    data = decision(record_data, row(applied={"transport": "Ka"}))
    data["payload"].update(
        call_id=str(call.record_id), conference_id=str(conference.record_id)
    )
    return call, conference, create(service, data)


def test_transport_target_remove_move_and_type_conflict(service, record_data):
    call, conference, saved = targets(service, record_data)
    for command in [
        RemoveRecord(record_id=call.record_id, expected_version=1),
        RemoveRecord(record_id=conference.record_id, expected_version=1),
        update(service, call, mission_id="other-mission"),
        update(service, saved, mission_id="other-mission"),
        update(
            service,
            conference,
            record_type="journal_entry",
            payload={"entry_type": "note", "title": "Type correction"},
        ),
    ]:
        with service.store.connect() as db:
            before = db.execute("SELECT count(*) FROM commands").fetchone()[0]
        with pytest.raises(OperatorError, match="dependency_conflict") as exc:
            submit(service, command)
        assert str(saved.record_id) in exc.value.record_ids
        with service.store.connect() as db:
            assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == before


def test_transport_unlink_remove_restore_sequence(service, record_data):
    call, _conference, saved = targets(service, record_data)
    removed = submit(
        service, RemoveRecord(record_id=saved.record_id, expected_version=1)
    ).saved_records[0]
    gone = submit(
        service, RemoveRecord(record_id=call.record_id, expected_version=1)
    ).saved_records[0]
    with pytest.raises(OperatorError, match="dependency_conflict"):
        submit(service, RestoreRecord(record_id=removed.record_id, expected_version=2))
    submit(service, RestoreRecord(record_id=gone.record_id, expected_version=2))
    active = submit(
        service, RestoreRecord(record_id=removed.record_id, expected_version=2)
    ).saved_records[0]
    content = active.payload.model_dump(mode="json") | {
        "call_id": None,
        "conference_id": None,
    }
    moved = submit(
        service, update(service, active, mission_id="other-mission", payload=content)
    ).saved_records[0]
    assert moved.mission_id == "other-mission"
    assert (
        service.history(str(saved.record_id)).items[0].payload.call_id == call.record_id
    )
    with service.store.connect() as db:
        assert (
            db.execute(
                "SELECT * FROM current_links WHERE from_id=?", (str(saved.record_id),)
            ).fetchall()
            == []
        )
        validate_connection(db, clock=service.clock)


def test_recovery_rejects_missing_transport_link(service, record_data):
    _call, _conference, saved = targets(service, record_data)
    with service.store.connect(write=True) as db:
        db.execute("DELETE FROM current_links WHERE from_id=?", (str(saved.record_id),))
    with service.store.connect() as db, pytest.raises(
        OperatorError, match="store_corrupt"
    ):
        validate_connection(db, clock=service.clock)
