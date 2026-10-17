"""Older immutable payloads and receipts survive lifecycle model additions."""

import json
from uuid import uuid4

from tests.operator.service_helpers import submit, update


def test_legacy_status_receipts_and_projection(service, record_data):
    # New defaults must not poison recovery or invent historical status values.
    from app.operator.models import SavedRecord
    from app.operator.recovery import verify_store

    record_id, command_id, key = (str(uuid4()) for _ in range(3))
    body = record_data | {
        "record_type": "call",
        "payload": {
            "schema_version": 1,
            "entry_type": "call",
            "title": "Legacy call",
            "note": "Original",
            "conference_id": None,
            "previous_leg_id": None,
            "next_leg_id": None,
        },
        "record_id": record_id,
        "version": 1,
        "previous_version": None,
        "journal_seq": 1,
        "command_id": command_id,
        "operation": "create",
        "reason": None,
        "reason_origin": None,
        "deleted": False,
        "recorded_at": "2026-10-17T16:00:00.000000Z",
        "author": {"backend": "operator_api", "operator_label": None},
        "provenance": {
            "kind": "operator_reported",
            "source_mode": "live",
            "observed_at": None,
            "predicted_at": None,
            "source_ref": None,
            "mutation_origin": "retrospective",
        },
    }
    # Persist a literal old-format revision/receipt, without current model defaults.
    body["time"] = SavedRecord.model_validate(body).model_dump(mode="json")["time"]
    canonical = {"schema_version": 1, "command_id": command_id, "saved_records": [body]}
    response = canonical | {"response_status": 201, "canonical_response": canonical}
    columns, values = [], []
    for name, value in body.items():
        columns.append(
            name + "_json"
            if name in ("author", "provenance", "payload", "time")
            else name
        )
        values.append(
            json.dumps(value)
            if isinstance(value, dict)
            else int(value) if name == "deleted" else value
        )
    original_response = json.dumps(response)
    with service.store.connect(write=True) as connection:
        connection.execute(
            "INSERT INTO revisions ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            values,
        )
        connection.execute("INSERT INTO records VALUES (?, 1)", (record_id,))
        connection.execute(
            "INSERT INTO commands VALUES (?, ?, ?, 1, ?, 201, ?)",
            (command_id, key, "legacy", body["recorded_at"], original_response),
        )
    assert verify_store(service.store).ready
    from app.operator.projections import capture_projection

    legacy = service.get(record_id)
    assert legacy.payload.status == "scheduled"
    submit(
        service,
        update(
            service,
            legacy,
            payload={
                "entry_type": "call",
                "title": "Legacy call",
                "status": "cancelled",
            },
        ),
    )
    bundle = capture_projection(
        service.store, mission_id="demo-mission", include_audit=True
    )
    activity = [
        json.loads(row)
        for row in bundle.files["operations/activity.jsonl"].splitlines()
    ]
    assert "payload.status" not in activity[0]["changes"]
    assert activity[1]["changes"]["payload.status"] == {
        "before": None,
        "after": "cancelled",
    }
    assert (
        "status"
        not in json.loads(bundle.files["operations/audit.jsonl"].splitlines()[0])[
            "payload"
        ]
    )
    with service.store.connect() as connection:
        assert (
            connection.execute(
                "SELECT response_json FROM commands WHERE command_id=?", (command_id,)
            ).fetchone()[0]
            == original_response
        )
        from app.operator.commands import receipt_for_key

        assert (
            receipt_for_key(connection, key, "legacy").canonical_response == canonical
        )
    assert verify_store(service.store).ready
