"""Independent transport reports retain human provenance and editable UTC facts."""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.operator.errors import OperatorError
from app.operator.models import CreateRecord
from tests.operator.service_helpers import create, submit, update


def row(**changes):
    return {"row_id": str(uuid4()), "service": "VTC", **changes}


def payload(*rows):
    return {"entry_type": "transport_decision", "title": "VTC", "services": list(rows)}


def decision(record_data, *rows):
    return record_data | {
        "record_type": "transport_decision",
        "payload": payload(*rows),
    }


def test_independent_applied_only_and_checked_only(record_data):
    for item in [
        row(applied={"transport": "Ka"}),
        row(checked={"result": "satisfactory"}),
    ]:
        command = CreateRecord.model_validate(decision(record_data, item))
        actual = command.payload.services[0]
        assert actual.intended is None and actual.requested is None
        assert command.payload.reason == ""
        assert command.payload.call_id is None


def test_three_different_transports(record_data):
    command = CreateRecord.model_validate(
        decision(
            record_data,
            row(
                intended={"transport": "Ka"},
                requested={"transport": "X"},
                applied={"transport": "Starshield"},
                checked={"result": "unknown"},
            ),
        )
    )
    actual = command.payload.services[0]
    assert [
        actual.intended.transport,
        actual.requested.transport,
        actual.applied.transport,
    ] == ["Ka", "X", "Starshield"]
    assert actual.applied.time.at is None


@pytest.mark.parametrize(
    "count,valid", [(0, False), (1, True), (32, True), (33, False)]
)
def test_rows_atomic_and_limits(record_data, count, valid):
    data = decision(record_data, *(row() for _ in range(count)))
    if valid:
        assert len(CreateRecord.model_validate(data).payload.services) == count
    else:
        with pytest.raises(ValidationError):
            CreateRecord.model_validate(data)


@pytest.mark.parametrize(
    "field,limit", [("service", 200), ("reason", 1000), ("note", 8000)]
)
def test_text_limits(record_data, field, limit):
    data = decision(record_data, row())
    target = data["payload"]["services"][0] if field == "service" else data["payload"]
    target[field] = "a" * limit
    CreateRecord.model_validate(data)
    target[field] += "a"
    with pytest.raises(ValidationError):
        CreateRecord.model_validate(data)


def test_duplicate_ids_and_blank_service(record_data):
    item = row()
    for items in [(item, item), (row(service="   "),)]:
        with pytest.raises(ValidationError):
            CreateRecord.model_validate(decision(record_data, *items))


def test_times_unknown_editable_and_utc(record_data, clock):
    item = row(
        requested={
            "transport": "unknown",
            "time": {"at": "2026-10-17T17:00:00+02:00", "precision": "approximate"},
        }
    )
    command = CreateRecord.model_validate(decision(record_data, item))
    command.validate_for_acceptance(clock)
    assert command.payload.services[0].requested.time.at.hour == 15
    item["requested"]["time"]["precision"] = "unknown"
    with pytest.raises(ValidationError):
        CreateRecord.model_validate(decision(record_data, item))


def test_future_report_tolerance(record_data, clock):
    for seconds, valid in [(60, True), (61, False)]:
        item = row(
            applied={
                "transport": "X",
                "time": {
                    "at": clock.now() + timedelta(seconds=seconds),
                    "precision": "exact",
                },
            }
        )
        command = CreateRecord.model_validate(decision(record_data, item))
        if valid:
            command.validate_for_acceptance(clock)
        else:
            with pytest.raises(OperatorError, match="validation_error"):
                command.validate_for_acceptance(clock)


def test_replacement_check_requires_explicit_marker(service, record_data):
    saved = create(
        service,
        decision(
            record_data,
            row(applied={"transport": "X"}, checked={"result": "satisfactory"}),
        ),
    )
    changed = deepcopy(saved.payload.model_dump(mode="json"))
    changed["services"][0]["applied"]["transport"] = "Ka"
    with pytest.raises(OperatorError, match="validation_error"):
        submit(service, update(service, saved, payload=changed))
    corrected = submit(
        service,
        update(
            service,
            saved,
            payload=changed,
            replacement_check_row_ids=[changed["services"][0]["row_id"]],
        ),
    ).saved_records[0]
    assert corrected.payload.services[0].checked.result == "satisfactory"
    assert "replacement_check_row_ids" not in corrected.model_dump()
    assert saved.payload.services[0].applied.transport == "X"


def test_pre_upgrade_update_key_replays_with_new_optional_marker(service, record_data):
    """An absent new command field must not change hashes of schema-002 retries."""
    import hashlib
    import json

    from app.operator.commands import execute_in_transaction

    saved = create(service, record_data)
    command = update(
        service, saved, payload={"entry_type": "note", "title": "Legacy correction"}
    )
    key = str(uuid4())
    legacy_body = command.model_dump(mode="json", exclude={"replacement_check_row_ids"})
    legacy_hash = hashlib.sha256(
        json.dumps(legacy_body, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    with service.store.connect(write=True) as connection:
        original = execute_in_transaction(
            connection,
            command,
            key=key,
            request_hash=legacy_hash,
            clock=service.clock,
            actor=service.actor,
        )
    assert submit(service, command, key=key) == original
