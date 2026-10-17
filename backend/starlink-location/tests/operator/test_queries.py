"""Pinned H projection filters after choosing historical current revisions."""

from uuid import uuid4
import pytest
from app.operator.errors import OperatorError
from app.operator.models import RecordFilter, RemoveRecord
from tests.operator.service_helpers import create, submit, update


def test_snapshot_pages_during_move(service, record_data, clock):
    saved = [create(service, record_data, time={}) for _ in range(5)]
    filters = RecordFilter(mission_id="demo-mission")
    page = service.list(filters, limit=2)
    first_H = page.H
    clock.advance(-500)
    submit(service, update(service, saved[0], mission_id="other-mission"))
    submit(service, update(service, saved[1], audit_note="Edited"))
    submit(service, RemoveRecord(record_id=saved[2].record_id, expected_version=1))
    items = list(page.items)
    while page.cursor:
        page = service.list(filters, limit=2, cursor=page.cursor)
        assert page.H == first_H
        items.extend(page.items)
    assert [str(r.record_id) for r in items] == sorted(str(r.record_id) for r in saved)
    assert all(r.version == 1 and not r.deleted for r in items)
    assert len(service.list(filters).items) == 3
    journal = service.journal("demo-mission", limit=2)
    seqs = [r.journal_seq for r in journal.items]
    while journal.cursor:
        journal = service.journal("demo-mission", limit=2, cursor=journal.cursor)
        seqs.extend(r.journal_seq for r in journal.items)
    assert seqs == sorted(seqs) and len(seqs) == 7
    assert service.store.health().clock_regression


@pytest.mark.parametrize("cursor", ["not-a-cursor", "e30="])
def test_invalid_cursors_and_limits(service, record_data, cursor):
    create(service, record_data)
    filters = RecordFilter(mission_id="demo-mission")
    for kwargs in ({"limit": 201}, {"limit": 0}, {"cursor": cursor}):
        with pytest.raises(OperatorError) as invalid:
            service.list(filters, **kwargs)
        assert invalid.value.code == "validation_error"
    create(service, record_data)
    first = service.list(filters, limit=1)
    with pytest.raises(OperatorError):
        service.list(RecordFilter(mission_id="other-mission"), cursor=first.cursor)
    service.store._identity["api_epoch"] = str(uuid4())
    with pytest.raises(OperatorError):
        service.list(filters, cursor=first.cursor)


def test_history_snapshot_and_cursor_structure(service, record_data):
    import base64
    import json

    saved = create(service, record_data)
    current = submit(service, update(service, saved)).saved_records[0]
    page = service.history(str(saved.record_id), limit=1)
    submit(service, update(service, current))
    tail = service.history(str(saved.record_id), limit=1, cursor=page.cursor)
    assert [r.version for r in tail.items] == [2]
    assert tail.H == page.H and tail.as_of == page.as_of and tail.cursor is None
    filters = RecordFilter(mission_id="demo-mission")
    create(service, record_data)
    first = service.list(filters, limit=1)
    state = json.loads(base64.urlsafe_b64decode(first.cursor))
    state["last"] = "invalid-record-id"
    bad = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    with pytest.raises(OperatorError) as invalid:
        service.list(filters, cursor=bad)
    assert invalid.value.code == "validation_error"


@pytest.mark.parametrize("kind", ["history", "journal"])
@pytest.mark.parametrize("boundary", [2**63, 3, -1, True, False, 1.0, "1", None])
def test_sequence_cursors_reject_invalid_boundaries(
    service, record_data, kind, boundary
):
    import base64
    import json

    saved = create(service, record_data)
    submit(service, update(service, saved))
    read = service.history if kind == "history" else service.journal
    identity = str(saved.record_id) if kind == "history" else "demo-mission"
    first = read(identity, limit=1)
    assert first.H == 2
    state = json.loads(base64.urlsafe_b64decode(first.cursor))
    state["last"] = boundary
    cursor = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    with pytest.raises(OperatorError) as invalid:
        read(identity, cursor=cursor)
    assert invalid.value.code == "validation_error"
    assert invalid.value.fields == {"cursor": "Invalid cursor"}


@pytest.mark.parametrize("kind", ["history", "journal"])
@pytest.mark.parametrize("boundary, versions", [(0, [1, 2]), (2, [])])
def test_sequence_cursors_accept_snapshot_endpoints(
    service, record_data, kind, boundary, versions
):
    import base64
    import json

    saved = create(service, record_data)
    submit(service, update(service, saved))
    read = service.history if kind == "history" else service.journal
    identity = str(saved.record_id) if kind == "history" else "demo-mission"
    first = read(identity, limit=1)
    state = json.loads(base64.urlsafe_b64decode(first.cursor))
    state["last"] = boundary
    cursor = base64.urlsafe_b64encode(json.dumps(state).encode()).decode()
    page = read(identity, cursor=cursor)
    assert page.H == 2
    assert [record.version for record in page.items] == versions
