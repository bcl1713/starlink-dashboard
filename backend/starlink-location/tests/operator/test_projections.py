"""Operational reconstruction must not require the optional full-text audit."""

import hashlib
import json

from app.operator.models import RemoveRecord, RestoreRecord
from tests.operator.service_helpers import create, submit, update


def lines(bundle, name="activity"):
    return [
        json.loads(row) for row in bundle.files[f"operations/{name}.jsonl"].splitlines()
    ]


def test_default_activity_without_audit(service, record_data, clock):
    # Lost diffs, collapsed revisions, tombstones in current, or hidden audit fail.
    from app.operator.projections import capture_projection

    call = create(
        service,
        record_data,
        record_type="call",
        time={
            "planned_start_at": "2026-10-17T14:00:00Z",
            "planned_end_at": "2026-10-17T14:30:00Z",
        },
        payload={"entry_type": "call", "title": "Synthetic call"},
    )
    call = submit(
        service,
        update(
            service,
            call,
            time={
                "planned_start_at": "2026-10-17T14:10:00Z",
                "planned_end_at": "2026-10-17T14:40:00Z",
            },
        ),
    ).saved_records[0]
    call = submit(
        service,
        update(
            service,
            call,
            payload={
                "entry_type": "call",
                "title": "Synthetic call",
                "status": "cancelled",
            },
        ),
    ).saved_records[0]
    issue = create(
        service,
        record_data,
        record_type="issue",
        time={},
        payload={"entry_type": "issue", "title": "Synthetic issue"},
    )
    issue = submit(
        service,
        update(
            service,
            issue,
            payload={
                "entry_type": "issue",
                "title": "Synthetic issue",
                "status": "resolved",
            },
        ),
    ).saved_records[0]
    submit(
        service,
        update(
            service,
            issue,
            payload={
                "entry_type": "issue",
                "title": "Synthetic issue",
                "status": "open",
            },
        ),
    )
    late = create(
        service,
        record_data,
        record_type="call",
        payload={"entry_type": "call", "title": "Late report"},
    )
    corrected = create(
        service,
        record_data,
        record_type="call",
        time={
            "occurred_at": "2026-10-17T15:00:00Z",
            "ended_at": "2026-10-17T15:45:00Z",
            "precision": "exact",
            "end_state": "known",
        },
        payload={"entry_type": "call", "title": "Corrected call"},
    )
    clock.advance(60)
    corrected = submit(
        service,
        update(
            service,
            corrected,
            time=corrected.time.model_dump(mode="json")
            | {"ended_at": "2026-10-17T15:35:00Z"},
        ),
    ).saved_records[0]
    removed = submit(
        service, RemoveRecord(record_id=corrected.record_id, expected_version=2)
    ).saved_records[0]
    submit(service, RestoreRecord(record_id=removed.record_id, expected_version=3))
    submit(service, RemoveRecord(record_id=late.record_id, expected_version=1))
    bundle = capture_projection(service.store, mission_id="demo-mission")
    current = json.loads(bundle.files["operations/current.json"])
    activity = lines(bundle)
    assert bundle.high_water == 12
    assert len(current) == len({r["record_id"] for r in current}) == 3
    assert all(not r["deleted"] for r in current)
    assert len(activity) == 12
    assert "operations/audit.jsonl" not in bundle.files
    assert activity[1]["changes"]["time.planned_start_at"] == {
        "before": "2026-10-17T14:00:00.000000Z",
        "after": "2026-10-17T14:10:00.000000Z",
    }
    assert activity[2]["changes"]["payload.status"] == {
        "before": "scheduled",
        "after": "cancelled",
    }
    assert activity[4]["changes"]["payload.status"] == {
        "before": "open",
        "after": "resolved",
    }
    assert activity[5]["changes"]["payload.status"] == {
        "before": "resolved",
        "after": "open",
    }
    assert activity[6]["recorded_at"] == "2026-10-17T16:00:00.000000Z"
    assert activity[6]["time"]["occurred_at"] == "2026-10-17T14:30:00.000000Z"
    assert activity[6]["time"]["ended_at"] == "2026-10-17T14:42:00.000000Z"
    assert activity[8]["changes"]["time.ended_at"] == {
        "before": "2026-10-17T15:45:00.000000Z",
        "after": "2026-10-17T15:35:00.000000Z",
    }
    assert [a["reason"] for a in activity[8:11]] == [
        "Operator correction",
        "Operator removal",
        "Operator restoration",
    ]
    assert all(a["reason_origin"] == "automatic" for a in activity[8:11])
    assert activity[9]["changes"]["deleted"] == {"before": False, "after": True}
    assert activity[10]["changes"]["deleted"] == {"before": True, "after": False}
    assert activity[8]["description_origin"] == "generated"
    assert all(a["provenance"]["source_mode"] == "live" for a in activity)
    assert all(a["identity"]["store_id"] == str(bundle.store_id) for a in activity)
    assert activity[0]["identity"]["record_id"] == str(call.record_id)
    assert activity[0]["identity"]["version"] == 1
    assert bundle.manifest.activity_included and not bundle.manifest.audit_included
    assert bundle.manifest.source_capture_revisions == {
        "operator": 12,
        "planning": None,
    }
    assert bundle.manifest.component_capture_times["planning"] is None
    for path, body in bundle.files.items():
        assert bundle.checksums[path] == hashlib.sha256(body).hexdigest()


def test_recording_order_and_text_policy(service, record_data, clock):
    # Acceptance order and revision-local title/origin survive clock regression.
    from app.operator.projections import capture_projection

    note = create(service, record_data, time={})
    clock.advance(-120)
    submit(
        service,
        update(
            service,
            note,
            payload={
                "entry_type": "note",
                "title": "New revision title",
                "note": "Replacement secret",
            },
            audit_note="Operator supplied explanation",
        ),
    )
    clock.advance(-120)
    late = create(service, record_data)
    default = capture_projection(service.store, mission_id="demo-mission")
    activity = lines(default)
    assert [a["journal_seq"] for a in activity] == [1, 2, 3]
    assert (
        activity[0]["recorded_at"]
        > activity[1]["recorded_at"]
        > activity[2]["recorded_at"]
    )
    assert activity[0]["time"]["occurred_at"] is None
    assert activity[1]["title"] == "New revision title"
    assert activity[1]["text_changes"] == ["payload.note", "payload.title"]
    assert activity[1]["reason_origin"] == "operator"
    assert activity[1]["reason"] == "Operator supplied explanation"
    assert [a["retrospective"] for a in activity] == [False, False, True]
    assert activity[2]["command_id"] == str(late.command_id)
    assert activity[0]["provenance"]["observed_at"] is None
    assert activity[0]["provenance"]["predicted_at"] is None
    assert "payload.note" not in activity[1]["changes"]
    assert b"Synthetic content" not in default.files["operations/activity.jsonl"]
    assert b"Replacement secret" not in default.files["operations/activity.jsonl"]
    audit = capture_projection(
        service.store, mission_id="demo-mission", include_audit=True
    )
    assert audit.manifest.audit_included
    assert lines(audit, "audit")[0]["payload"]["note"] == "Synthetic content"
    assert (
        audit.files["operations/activity.jsonl"]
        == default.files["operations/activity.jsonl"]
    )
