"""HTTP contracts exercise the real journal, receipts and planning references."""

import sqlite3
from uuid import uuid4

import pytest

from tests.operator.api_helpers import BASE, create, headers


def test_unexpected_json_field_does_not_reflect_private_content(api, record_data):
    result = create(api, dict(record_data, **{"private/SQL/notes": "secret"}))
    assert result.status_code == 422
    assert "private" not in result.text
    assert "secret" not in result.text


@pytest.mark.parametrize(
    "change",
    [
        {"provenance": {"kind": "observed"}},
        {"operation": "create"},
        {"record_type": "issue", "payload": {"entry_type": "issue", "title": "x"}},
        {"payload": {"entry_type": "note", "title": "x", "note": "x" * 8001}},
    ],
)
def test_public_dto_rejects_spoofed_and_internal_inputs(api, record_data, change):
    result = create(api, dict(record_data, **change))
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "validation_error"
    assert set(result.json()) == {"error", "request_id"}
    assert "Synthetic content" not in result.text
    assert "x" * 200 not in result.text


@pytest.mark.parametrize(
    "error,code,status,retry",
    [
        ("store_busy", "store_busy", 503, True),
        ("commit_outcome_unknown", "commit_outcome_unknown", 503, True),
        ("sqlite", "store_unavailable", 503, False),
    ],
)
def test_storage_errors_are_sanitized(
    api, record_data, monkeypatch, error, code, status, retry
):
    from app.operator.errors import OperatorError

    service = api.app.state.operator_runtime.service

    def fail(*args, **kwargs):
        if error == "sqlite":
            raise sqlite3.IntegrityError("SQL private /path with contents")
        raise OperatorError(error, retryable=retry)

    monkeypatch.setattr(service, "execute_result", fail)
    result = create(api, record_data)
    assert result.status_code == status
    assert result.json()["error"]["code"] == code
    assert result.json()["error"]["retryable"] is retry
    assert "private" not in result.text
    assert result.headers["Cache-Control"] == "no-store"
    if error == "store_busy":
        assert result.headers["Retry-After"] == "1"


def test_commit_ack_failure_can_retry_without_duplicate(api, record_data, monkeypatch):
    from app.operator.errors import OperatorError

    service = api.app.state.operator_runtime.service
    execute = service.execute_result

    def lost_ack(*args, **kwargs):
        execute(*args, **kwargs)
        raise OperatorError("commit_outcome_unknown", retryable=True)

    monkeypatch.setattr(service, "execute_result", lost_ack)
    key = str(uuid4())
    assert create(api, record_data, key).status_code == 503
    monkeypatch.setattr(service, "execute_result", execute)
    result = create(api, record_data, key)
    assert result.status_code == 201
    assert result.headers["Idempotency-Replayed"] == "true"
    assert len(api.get(BASE + "/journal?mission_id=demo-mission").json()["items"]) == 1


@pytest.mark.parametrize("action", ["update", "remove", "restore"])
def test_internal_workflow_cannot_be_mutated_through_journal(api, record_data, action):
    from app.operator.models import CreateRecord, RemoveRecord

    service = api.app.state.operator_runtime.service
    body = dict(
        record_data,
        record_type="issue",
        payload={"entry_type": "issue", "title": "fixture"},
    )
    epoch = str(service.store.health().api_epoch)
    saved = service.execute(
        CreateRecord(**body), key=str(uuid4()), epoch=epoch
    ).saved_records[0]
    version = 1
    if action == "restore":
        service.execute(
            RemoveRecord(record_id=saved.record_id, expected_version=1),
            key=str(uuid4()),
            epoch=epoch,
        )
        version = 2
    path = BASE + "/records/" + str(saved.record_id)
    if action == "update":
        result = api.put(
            path, json=dict(record_data, expected_version=version), headers=headers(api)
        )
    else:
        result = api.post(
            path + "/" + action,
            json={"expected_version": version},
            headers=headers(api),
        )
    assert result.status_code == 422
    assert result.json()["error"]["fields"] == {
        "record_type": "Workflow is not publicly editable"
    }
    assert service.get(saved.record_id).version == version
