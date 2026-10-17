"""Membership boundaries and one SQLite snapshot protect cross-file consistency."""

import json
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

from app.operator.models import RemoveRecord
from app.operator.store import OperatorStore
from tests.operator.service_helpers import create, submit, update


def test_move_and_concurrent_snapshot(service, record_data, monkeypatch):
    # Wrong membership, current-pointer reads or per-file captures leak later edits.
    from app.operator.projections import capture_projection

    moved = create(service, record_data)
    moved = submit(
        service, update(service, moved, mission_id="other-mission")
    ).saved_records[0]
    submit(
        service,
        update(
            service,
            moved,
            payload={
                "entry_type": "note",
                "title": "Later B only",
                "note": "B only",
            },
        ),
    )
    scoped = []
    for scope in ("preflight", "between_legs", "postflight"):
        scoped.append(create(service, record_data, scope=scope, leg_id=None))
    active = create(service, record_data)
    a = capture_projection(service.store, mission_id="demo-mission", include_audit=True)
    b = capture_projection(
        service.store, mission_id="other-mission", include_audit=True
    )
    a_items = [
        json.loads(row) for row in a.files["operations/activity.jsonl"].splitlines()
    ]
    b_items = [
        json.loads(row) for row in b.files["operations/activity.jsonl"].splitlines()
    ]
    assert [
        r["version"] for r in a_items if r["record_id"] == str(moved.record_id)
    ] == [1, 2]
    assert [r["version"] for r in b_items] == [2, 3]
    assert a_items[1]["identity"] == b_items[0]["identity"]
    assert a_items[1]["association"]["before"]["mission_id"] == "demo-mission"
    assert a_items[1]["association"]["after"]["mission_id"] == "other-mission"
    assert a_items[1]["changes"]["mission_id"] == {
        "before": "demo-mission",
        "after": "other-mission",
    }
    assert [
        r["version"]
        for r in map(json.loads, a.files["operations/audit.jsonl"].splitlines())
        if r["record_id"] == str(moved.record_id)
    ] == [1, 2]
    current = json.loads(a.files["operations/current.json"])
    assert {r["scope"] for r in current} == {
        "mission",
        "preflight",
        "between_legs",
        "postflight",
    }
    assert all(r["leg_id"] is None for r in current)
    assert str(moved.record_id) not in {r["record_id"] for r in current}

    original = service.store.connect
    triggered = False

    def edit_and_remove():
        submit(
            service,
            update(
                service,
                scoped[0],
                payload={
                    "entry_type": "note",
                    "title": "Concurrent newer",
                    "note": "Changed",
                },
            ),
        )
        submit(service, RemoveRecord(record_id=active.record_id, expected_version=1))

    class Connection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, sql, parameters=()):
            nonlocal triggered
            cursor = self.connection.execute(sql, parameters)
            if "AS high_water" in sql and not triggered:
                triggered = True
                # The high-water SELECT has already pinned SQLite's read snapshot.
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(edit_and_remove).result(timeout=10)
            return cursor

    @contextmanager
    def concurrent_connect(*, write=False):
        with original(write=write) as connection:
            yield connection if write else Connection(connection)

    monkeypatch.setattr(service.store, "connect", concurrent_connect)
    pinned = capture_projection(
        service.store, mission_id="demo-mission", include_audit=True
    )
    assert triggered
    assert pinned.high_water == a.high_water == 7
    assert pinned.files == a.files and pinned.checksums == a.checksums
    monkeypatch.setattr(service.store, "connect", original)
    latest = capture_projection(
        service.store, mission_id="demo-mission", include_audit=True
    )
    assert latest.high_water == 9
    assert "Concurrent newer" in {
        r["payload"]["title"]
        for r in json.loads(latest.files["operations/current.json"])
    }
    assert str(active.record_id) not in {
        r["record_id"] for r in json.loads(latest.files["operations/current.json"])
    }
    service.store.close()
    reopened = OperatorStore.open(
        service.store.settings, initialize=False, clock=service.clock
    )
    try:
        restarted = capture_projection(
            reopened, mission_id="demo-mission", include_audit=True
        )
        assert restarted.files == latest.files
        assert restarted.checksums == latest.checksums
        assert restarted.manifest == latest.manifest
    finally:
        reopened.close()


def test_empty_snapshot_is_explicit(service):
    from app.operator.projections import capture_projection

    bundle = capture_projection(service.store, mission_id="demo-mission")
    assert bundle.high_water == 0
    assert bundle.files == {
        "operations/current.json": b"[]\n",
        "operations/activity.jsonl": b"",
    }
    assert bundle.manifest.component_capture_times["operator"] is None
    assert bundle.manifest.unresolved_associations == []


def test_serialization_releases_read_and_missing_planning_keeps_ids(
    service, record_data, monkeypatch
):
    # Slow serialization/association resolution cannot pin WAL readers or erase data.
    from app.mission import storage
    from app.operator import projections

    saved = create(service, record_data)
    (storage.MISSIONS_DIR / "demo-mission" / "mission.json").unlink()
    original_connect = service.store.connect
    active = False

    @contextmanager
    def track_connect(*, write=False):
        nonlocal active
        with original_connect(write=write) as connection:
            active = True
            try:
                yield connection
            finally:
                active = False

    canonical = projections._canonical

    def check_serialization(value):
        assert not active
        return canonical(value)

    monkeypatch.setattr(service.store, "connect", track_connect)
    monkeypatch.setattr(projections, "_canonical", check_serialization)
    bundle = projections.capture_projection(service.store, mission_id="demo-mission")
    assert json.loads(bundle.files["operations/current.json"])[0]["record_id"] == str(
        saved.record_id
    )
    assert bundle.manifest.unresolved_associations == [
        {
            "record_id": str(saved.record_id),
            "status": "missing",
            "unresolved_fields": ["mission_id"],
            "error_code": None,
        }
    ]
    assert bundle.manifest.source_capture_revisions["planning"] is None


def test_typed_relationships_and_type_changes(service, record_data):
    # Dropping typed links, operational type or between-leg association loses reconstruction.
    from app.operator.projections import capture_projection

    conference = create(
        service,
        record_data,
        record_type="conference",
        time={},
        payload={"entry_type": "conference", "title": "Conference"},
    )
    call = create(
        service,
        record_data,
        record_type="call",
        scope="between_legs",
        time={},
        payload={
            "entry_type": "call",
            "title": "Call",
            "conference_id": str(conference.record_id),
            "previous_leg_id": "leg-a",
            "next_leg_id": "leg-a",
        },
    )
    call = submit(
        service,
        update(
            service,
            call,
            payload={"entry_type": "call", "title": "Call", "conference_id": None},
        ),
    ).saved_records[0]
    submit(
        service,
        update(
            service,
            call,
            record_type="journal_entry",
            payload={"entry_type": "note", "title": "Observation"},
        ),
    )
    bundle = capture_projection(service.store, mission_id="demo-mission")
    activity = [
        json.loads(row)
        for row in bundle.files["operations/activity.jsonl"].splitlines()
    ]
    assert activity[1]["changes"]["payload.conference_id"] == {
        "before": None,
        "after": str(conference.record_id),
    }
    assert activity[1]["association"]["after"]["previous_leg_id"] == "leg-a"
    assert activity[1]["association"]["after"]["next_leg_id"] == "leg-a"
    assert activity[2]["changes"]["payload.conference_id"] == {
        "before": str(conference.record_id),
        "after": None,
    }
    assert activity[3]["changes"]["record_type"] == {
        "before": "call",
        "after": "journal_entry",
    }
    assert activity[3]["changes"]["payload.entry_type"] == {
        "before": "call",
        "after": "note",
    }
