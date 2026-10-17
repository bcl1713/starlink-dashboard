"""Planning associations and typed links remain valid without active legs."""

import pytest

from app.mission import storage
from app.operator.errors import OperatorError
from app.operator.models import RemoveRecord, RestoreRecord
from tests.operator.service_helpers import create, submit, update


def test_wrong_leg_and_missing_mission(service, record_data):
    saved = create(service, record_data, scope="leg", leg_id="leg-a")
    with pytest.raises(OperatorError) as invalid:
        submit(service, update(service, saved, leg_id="wrong-leg"))
    assert invalid.value.code == "validation_error"
    assert len(service.history(str(saved.record_id)).items) == 1
    storage.get_mission_file_path("demo-mission").unlink()
    assert service.get(str(saved.record_id)) == saved
    moved = submit(
        service, update(service, saved, mission_id="other-mission")
    ).saved_records[0]
    assert moved.mission_id == "other-mission"
    storage.get_mission_file_path("other-mission").unlink()
    removed = submit(
        service, RemoveRecord(record_id=moved.record_id, expected_version=2)
    ).saved_records[0]
    with pytest.raises(OperatorError):
        submit(service, RestoreRecord(record_id=removed.record_id, expected_version=3))


def test_linked_move_type_remove_and_restore(service, record_data):
    parent = create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Conference"},
    )
    child = create(
        service,
        record_data,
        record_type="call",
        payload={
            "entry_type": "call",
            "title": "Call",
            "conference_id": str(parent.record_id),
        },
    )
    for command in (
        update(service, parent, mission_id="other-mission"),
        update(
            service,
            parent,
            record_type="journal_entry",
            payload={"entry_type": "note", "title": "Changed type"},
        ),
        RemoveRecord(record_id=parent.record_id, expected_version=1),
        update(service, child, mission_id="other-mission"),
    ):
        with pytest.raises(OperatorError) as conflict:
            submit(service, command)
        assert conflict.value.code == "dependency_conflict"
        assert conflict.value.record_ids
    removed_child = submit(
        service, RemoveRecord(record_id=child.record_id, expected_version=1)
    ).saved_records[0]
    removed_parent = submit(
        service, RemoveRecord(record_id=parent.record_id, expected_version=1)
    ).saved_records[0]
    with pytest.raises(OperatorError) as conflict:
        submit(service, RestoreRecord(record_id=child.record_id, expected_version=2))
    assert conflict.value.code == "dependency_conflict"
    assert removed_child.deleted and removed_parent.deleted


def test_participation_indexes_both_typed_targets(service, record_data):
    from app.operator.references import derive_links

    conference = create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Conference"},
    )
    call = create(
        service,
        record_data,
        record_type="call",
        payload={"entry_type": "call", "title": "Call"},
    )
    participation = create(
        service,
        record_data,
        record_type="participation",
        payload={
            "entry_type": "participation",
            "title": "Participation",
            "conference_id": str(conference.record_id),
            "call_id": str(call.record_id),
        },
    )
    expected = {
        (str(participation.record_id), "participation-to-call", str(call.record_id)),
        (
            str(participation.record_id),
            "participation-to-conference",
            str(conference.record_id),
        ),
    }
    assert derive_links(participation) == expected
    with service.store.connect() as db:
        assert set(db.execute("SELECT * FROM current_links").fetchall()) == expected
    for target in (call, conference):
        with pytest.raises(OperatorError) as conflict:
            submit(
                service, RemoveRecord(record_id=target.record_id, expected_version=1)
            )
        assert conflict.value.code == "dependency_conflict"
    detached = submit(
        service,
        update(
            service,
            participation,
            payload={
                "entry_type": "participation",
                "title": "Detached call",
                "conference_id": str(conference.record_id),
            },
        ),
    ).saved_records[0]
    submit(service, RemoveRecord(record_id=call.record_id, expected_version=1))
    with service.store.connect() as db:
        assert db.execute("SELECT relation FROM current_links").fetchall() == [
            ("participation-to-conference",)
        ]
        assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    assert detached.version == 2


def test_unavailable_planning_is_distinct_from_missing_identity(
    service, record_data, monkeypatch
):
    def unavailable(mission_id):
        raise OSError("private path unavailable")

    monkeypatch.setattr(storage, "load_mission_v2", unavailable)
    with pytest.raises(OperatorError) as error:
        create(service, record_data)
    assert error.value.code == "store_unavailable"
    assert error.value.fields is None
    with service.store.connect() as db:
        assert db.execute("SELECT count(*) FROM commands").fetchone()[0] == 0
