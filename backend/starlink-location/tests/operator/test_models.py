"""Contract checks catch lost validation, normalized times, and provenance spoofing."""

from copy import deepcopy
from datetime import datetime
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError


def test_utc_and_unknown_times(record_data, clock):
    # Removing UTC normalization, interval checks, or the injected-clock bound fails.
    from app.operator.errors import OperatorError
    from app.operator.models import RecordInput, SourceProvenance

    record_data["time"].update(
        occurred_at="2026-10-17T16:30:00+02:00",
        ended_at="2026-10-17T16:42:00.123456+02:00",
    )
    record = RecordInput.model_validate(record_data)
    record.validate_for_acceptance(clock)
    assert record.model_dump(mode="json")["time"]["occurred_at"] == (
        "2026-10-17T14:30:00.000000Z"
    )
    assert record.model_dump(mode="json")["time"]["ended_at"] == (
        "2026-10-17T14:42:00.123456Z"
    )
    # Deliberately invalid input must be rejected by the boundary.
    naive_value = datetime(2026, 10, 17, 14, 30)  # noqa: DTZ001
    for naive in ("2026-10-17T14:30:00", naive_value):
        invalid = deepcopy(record_data)
        invalid["time"]["occurred_at"] = naive
        with pytest.raises(ValidationError):
            RecordInput.model_validate(invalid)

    record_data["time"].update(
        occurred_at=None, ended_at=None, precision="unknown", end_state="unknown"
    )
    unknown = RecordInput.model_validate(record_data)
    unknown.validate_for_acceptance(clock)
    assert unknown.model_dump(mode="json")["time"]["occurred_at"] is None
    source = SourceProvenance(kind="operator_reported", source_mode="simulation")
    assert source.model_dump(mode="json")["observed_at"] is None
    assert source.model_dump(mode="json")["predicted_at"] is None

    record_data["time"].update(
        occurred_at="2026-10-16T23:59:00Z",
        ended_at="2026-10-17T00:01:00Z",
        precision="approximate",
        end_state="known",
    )
    RecordInput.model_validate(record_data).validate_for_acceptance(clock)
    record_data["time"]["ended_at"] = "2026-10-16T23:58:00Z"
    with pytest.raises(ValidationError):
        RecordInput.model_validate(record_data)

    record_data["time"].update(
        occurred_at="2026-10-17T16:01:00Z", ended_at=None, end_state="instant"
    )
    RecordInput.model_validate(record_data).validate_for_acceptance(clock)
    record_data["time"]["occurred_at"] = "2026-10-17T16:01:01Z"
    with pytest.raises(OperatorError) as caught:
        RecordInput.model_validate(record_data).validate_for_acceptance(clock)
    assert caught.value.code == "validation_error"
    assert "time.occurred_at" in caught.value.fields


def test_strict_payload_and_origin(record_data, clock):
    # Removing bounds/closed fields or accepting producer claims fails this test.
    from app.operator.models import CreateRecord, RecordInput

    for field, value in (("extra", "bad"), ("title", "x" * 201), ("note", "x" * 8001)):
        invalid = deepcopy(record_data)
        invalid["payload"][field] = value
        with pytest.raises(ValidationError):
            CreateRecord.model_validate(invalid)
    for extra in (
        {"provenance": {"kind": "observed", "source_mode": "live"}},
        {"recorded_at": "2026-10-17T16:00:00Z"},
        {"author": {"backend": "trusted"}},
        {"schema_version": True},
    ):
        with pytest.raises(ValidationError):
            CreateRecord.model_validate({**record_data, **extra})
    for title in ("", "   "):
        invalid = deepcopy(record_data)
        invalid["payload"]["title"] = title
        with pytest.raises(ValidationError):
            CreateRecord.model_validate(invalid)

    record_data["payload"].update(title="x" * 200, note="x" * 8000)
    record_data["time"].update(
        occurred_at=None,
        ended_at=None,
        precision="unknown",
        end_state="unknown",
        planned_start_at="2027-01-01T23:59:00Z",
        planned_end_at="2027-01-02T00:01:00Z",
    )
    planned = RecordInput.model_validate(record_data)
    planned.validate_for_acceptance(clock)
    assert planned.time.occurred_at is None
    record_data["time"]["planned_end_at"] = "2027-01-01T23:58:00Z"
    with pytest.raises(ValidationError):
        RecordInput.model_validate(record_data)


@pytest.mark.parametrize(
    "changes",
    [
        {"precision": "unknown"},
        {"end_state": "instant"},
        {"end_state": "ongoing"},
        {"occurred_at": None},
    ],
)
def test_interval_states_reject_inconsistent_actuals(record_data, changes):
    from app.operator.models import RecordInput

    record_data["time"].update(changes)
    with pytest.raises(ValidationError):
        RecordInput.model_validate(record_data)


def test_commands_are_discriminated_and_versioned(record_data):
    # Dropping expected-version, UUID, scope, or audit bounds would allow bad writes.
    from app.operator.models import OperatorCommand, RecordInput

    adapter = TypeAdapter(OperatorCommand)
    command = adapter.validate_python({**record_data, "operation": "create"})
    assert command.operation == "create"
    record_id = str(uuid4())
    for operation in ("update", "remove", "restore"):
        body = record_data if operation == "update" else {"schema_version": 1}
        valid = {
            **body,
            "operation": operation,
            "record_id": record_id,
            "expected_version": 1,
        }
        assert adapter.validate_python(valid).expected_version == 1
        for note in (None, "", "   ", "x" * 1000):
            adapter.validate_python({**valid, "audit_note": note})
        for bad in (
            {"expected_version": 0},
            {"expected_version": True},
            {"expected_version": "1"},
            {"record_id": "not-a-uuid"},
            {"audit_note": "x" * 1001},
        ):
            with pytest.raises(ValidationError):
                adapter.validate_python({**valid, **bad})
        del valid["expected_version"]
        with pytest.raises(ValidationError):
            adapter.validate_python(valid)
    for changes in ({"scope": "leg"}, {"leg_id": "unexpected-leg"}):
        with pytest.raises(ValidationError):
            RecordInput.model_validate({**record_data, **changes})


def test_internal_payloads_are_closed_and_match_record_type(record_data):
    # A generic JSON payload or unchecked type change would accept these invalid records.
    from app.operator.models import RecordInput

    for record_type in (
        "call",
        "conference",
        "participation",
        "issue",
        "risk",
        "transport_report",
    ):
        payload = {
            "schema_version": 1,
            "entry_type": record_type,
            "title": "Synthetic fixture",
        }
        if record_type == "participation":
            payload["call_id"] = str(uuid4())
        if record_type == "transport_report":
            payload.update(transport="Ka", status="reported_available")
        candidate = {**record_data, "record_type": record_type, "payload": payload}
        assert RecordInput.model_validate(candidate).record_type == record_type
        with pytest.raises(ValidationError):
            RecordInput.model_validate({**candidate, "record_type": "journal_entry"})
        with pytest.raises(ValidationError):
            RecordInput.model_validate(
                {**candidate, "payload": {**payload, "plugin": {}}}
            )


def test_saved_revision_and_receipt_preserve_full_contract(record_data):
    # Lost predecessor/reason invariants or timestamp serialization corrupt audit rows.
    from app.operator.models import CommandReceipt, SavedRecord

    revision = {
        **record_data,
        "record_id": str(uuid4()),
        "version": 1,
        "previous_version": None,
        "journal_seq": 7,
        "command_id": str(uuid4()),
        "operation": "create",
        "deleted": False,
        "recorded_at": "2026-10-17T18:00:00+02:00",
        "author": {"backend": "operator_api", "operator_label": "Unverified label"},
        "provenance": {"kind": "operator_reported", "source_mode": "simulation"},
    }
    saved = SavedRecord.model_validate(revision)
    assert saved.model_dump(mode="json")["recorded_at"] == "2026-10-17T16:00:00.000000Z"
    receipt = CommandReceipt(
        command_id=saved.command_id,
        response_status=201,
        saved_records=[saved],
        canonical_response={
            "schema_version": 1,
            "record": saved.model_dump(mode="json"),
        },
    )
    assert receipt.canonical_response["record"]["time"]["occurred_at"] == (
        "2026-10-17T14:30:00.000000Z"
    )
    for bad in (
        {"previous_version": 1},
        {"version": 2},
        {"deleted": True},
        {"operation": "update"},
    ):
        with pytest.raises(ValidationError):
            SavedRecord.model_validate({**revision, **bad})
    updated = {
        **revision,
        "operation": "update",
        "version": 2,
        "previous_version": 1,
        "reason": "Operator correction",
        "reason_origin": "automatic",
    }
    assert SavedRecord.model_validate(updated).version == 2
    with pytest.raises(ValidationError):
        SavedRecord.model_validate({**updated, "reason": ""})


def test_read_contracts_bound_filters_and_keep_unknown_source_time():
    from app.operator.models import HistoryPage, RecordFilter, RecordPage, StoreHealth

    filters = RecordFilter(mission_id="demo-mission")
    assert filters.include_removed is False
    for bad in ({"mission_id": ""}, {"unknown": True}, {"include_removed": "yes"}):
        with pytest.raises(ValidationError):
            RecordFilter.model_validate({"mission_id": "demo-mission", **bad})
    for page_type in (RecordPage, HistoryPage):
        page = page_type(items=[], cursor=None, H=0, as_of="2026-10-17T16:00:00Z")
        assert page.model_dump(mode="json")["as_of"] == "2026-10-17T16:00:00.000000Z"
        with pytest.raises(ValidationError):
            page_type(items=[], H=-1, as_of="2026-10-17T16:00:00Z")
    health = StoreHealth(
        ready=False, source_mode="live", error_code="store_unavailable"
    )
    assert health.error_code == "store_unavailable"


@pytest.mark.parametrize(
    "kind,default,statuses",
    [
        ("call", "scheduled", ["scheduled", "completed", "cancelled"]),
        ("issue", "open", ["open", "resolved"]),
    ],
)
def test_internal_lifecycle_statuses(record_data, kind, default, statuses):
    # Legacy payloads parse, while invalid domain lifecycle states are rejected.
    from app.operator.models import RecordInput

    data = record_data | {
        "record_type": kind,
        "payload": {"entry_type": kind, "title": "Fixture"},
    }
    assert RecordInput.model_validate(data).payload.status == default
    for status in statuses:
        assert (
            RecordInput.model_validate(
                data | {"payload": data["payload"] | {"status": status}}
            ).payload.status
            == status
        )
    with pytest.raises(ValidationError):
        RecordInput.model_validate(
            data | {"payload": data["payload"] | {"status": "invalid"}}
        )
