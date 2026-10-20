"""Public current-type checks run after receipt replay and writer admission."""

from contextlib import contextmanager
from uuid import uuid4

from app.operator.models import UpdateRecord
from tests.operator.api_helpers import BASE, create, headers
from tests.operator.service_helpers import submit


def convert_to_risk(service, record_data, saved):
    return submit(
        service,
        UpdateRecord(
            **dict(
                record_data,
                record_type="risk",
                payload={"entry_type": "risk", "title": "internal issue"},
            ),
            record_id=saved["record_id"],
            expected_version=saved["version"],
        ),
    )


def test_exact_public_update_retry_survives_later_internal_type_change(
    api, record_data
):
    service = api.app.state.operator_runtime.service
    saved = create(api, record_data).json()["saved_records"][0]
    path = BASE + "/records/" + saved["record_id"]
    key = str(uuid4())
    body = dict(record_data, expected_version=1)
    result = api.put(path, json=body, headers=headers(api, key))
    assert result.status_code == 200
    convert_to_risk(service, record_data, result.json()["saved_records"][0])
    retry = api.put(path, json=body, headers=headers(api, key))
    assert retry.status_code == 200
    assert retry.json() == result.json()
    assert retry.headers["Idempotency-Replayed"] == "true"
    assert service.get(saved["record_id"]).record_type == "risk"


def test_current_type_gate_rechecks_under_writer_after_concurrent_change(
    api, record_data, monkeypatch
):
    service = api.app.state.operator_runtime.service
    saved = create(api, record_data).json()["saved_records"][0]
    locked = service.references.locked
    changed = False

    @contextmanager
    def interleaved(missions):
        nonlocal changed
        if not changed:
            changed = True
            convert_to_risk(service, record_data, saved)
        with locked(missions):
            yield

    monkeypatch.setattr(service.references, "locked", interleaved)
    result = api.put(
        BASE + "/records/" + saved["record_id"],
        json=dict(record_data, expected_version=1),
        headers=headers(api),
    )
    assert result.status_code == 422
    assert (
        result.json()["error"]["fields"]["record_type"]
        == "Workflow is not publicly editable"
    )
    current = service.get(saved["record_id"])
    assert current.record_type == "risk"
    assert current.version == 2
