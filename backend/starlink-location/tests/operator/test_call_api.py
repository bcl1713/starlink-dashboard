"""Call API defaults, corrections and immutable receipt contracts."""

from copy import deepcopy
from uuid import uuid4

import pytest

from tests.operator.api_helpers import BASE, create, headers


def call_data(record_data, status="scheduled", **payload):
    data = deepcopy(record_data)
    data.update(record_type="call", time={"planned_start_at": "2026-10-17T17:00:00Z"})
    data["payload"] = dict(
        entry_type="call", title="Synthetic party", status=status, **payload
    )
    return data


@pytest.mark.parametrize(
    "status", ["tentative", "scheduled", "delayed", "cancelled", "completed"]
)
@pytest.mark.parametrize("lead", ["omitted", None, 0, 25])
def test_create_lead_contract(api, record_data, status, lead):
    data = call_data(record_data, status)
    if lead != "omitted":
        data["payload"]["prep_lead_minutes"] = lead
    response = create(api, data)
    assert response.status_code == 201, response.text
    expected = (
        (10 if status in ("tentative", "scheduled", "delayed") else None)
        if lead == "omitted"
        else lead
    )
    assert (
        response.json()["saved_records"][0]["payload"]["prep_lead_minutes"] == expected
    )


@pytest.mark.parametrize("lead", [True, 1.5, -1, 10081, "10"])
def test_reject_invalid_lead(api, record_data, lead):
    assert (
        create(api, call_data(record_data, prep_lead_minutes=lead)).status_code == 422
    )


def test_put_requires_lead_and_cannot_change_type(api, record_data):
    data = call_data(record_data)
    response = create(api, data)
    assert response.status_code == 201, response.text
    path = BASE + "/records/" + response.json()["saved_records"][0]["record_id"]
    assert (
        api.put(
            path, json=dict(data, expected_version=1), headers=headers(api)
        ).status_code
        == 422
    )
    assert api.get(path).json()["record"]["version"] == 1
    assert (
        api.put(
            path, json=dict(record_data, expected_version=1), headers=headers(api)
        ).status_code
        == 422
    )
    data["payload"]["prep_lead_minutes"] = None
    result = api.put(path, json=dict(data, expected_version=1), headers=headers(api))
    assert result.status_code == 200
    assert result.json()["saved_records"][0]["payload"]["prep_lead_minutes"] is None


def test_reschedule_replay_and_conflict(api, record_data):
    data = call_data(
        record_data, party="Synthetic participant", communications_kind="vtc"
    )
    key = str(uuid4())
    first = create(api, data, key)
    assert first.status_code == 201, first.text
    path = BASE + "/records/" + first.json()["saved_records"][0]["record_id"]
    updated = deepcopy(data)
    updated["payload"]["prep_lead_minutes"] = 0
    updated["time"]["planned_start_at"] = "2026-10-18T00:15:00Z"
    assert (
        api.put(
            path, json=dict(updated, expected_version=1), headers=headers(api)
        ).status_code
        == 200
    )
    assert create(api, data, key).json() == first.json()
    assert (
        api.put(
            path, json=dict(updated, expected_version=1), headers=headers(api)
        ).status_code
        == 409
    )
    history = api.get(path + "/history").json()["items"]
    assert [item["record"]["time"]["planned_start_at"] for item in history] == [
        "2026-10-17T17:00:00.000000Z",
        "2026-10-18T00:15:00.000000Z",
    ]


def test_retrospective_correct_remove_restore(api, record_data):
    data = call_data(record_data, "completed", party=None)
    data["time"] = record_data["time"]
    response = create(api, data)
    assert response.status_code == 201, response.text
    path = BASE + "/records/" + response.json()["saved_records"][0]["record_id"]
    data["payload"].update(
        party="Corrected synthetic participant", prep_lead_minutes=None
    )
    data["time"]["ended_at"] = "2026-10-17T14:45:00Z"
    assert (
        api.put(
            path, json=dict(data, expected_version=1), headers=headers(api)
        ).status_code
        == 200
    )
    for action, version in [("remove", 2), ("restore", 3)]:
        response = api.post(
            path + "/" + action,
            json={"expected_version": version},
            headers=headers(api),
        )
        assert response.status_code == 200
        record = response.json()["saved_records"][0]
        assert record["payload"]["prep_lead_minutes"] is None
        assert record["time"]["planned_start_at"] is None
        assert record["time"]["ended_at"] == "2026-10-17T14:45:00.000000Z"
    assert len(api.get(path + "/history").json()["items"]) == 4


def test_unknown_timing_and_scheduled_validation(api, record_data):
    data = call_data(record_data)
    data["time"] = {}
    assert create(api, data).status_code == 422
    for status in ("tentative", "completed"):
        data["payload"]["status"] = status
        assert create(api, data).status_code == 201


def test_conference_independent_and_call_associations(api, record_data):
    from tests.operator.service_helpers import create as internal_create

    service = api.app.state.operator_runtime.service
    conference = internal_create(
        service,
        record_data,
        record_type="conference",
        payload={"entry_type": "conference", "title": "Synthetic conference"},
    )
    data = call_data(record_data, "completed", conference_id=str(conference.record_id))
    data["time"] = record_data["time"]
    first = create(api, data).json()["saved_records"][0]
    path = BASE + "/records/" + first["record_id"]
    data["payload"].update(prep_lead_minutes=None, conference_id=None)
    data.update(scope="between_legs")
    data["payload"].update(previous_leg_id="leg-a", next_leg_id="leg-a")
    assert (
        api.put(
            path, json=dict(data, expected_version=1), headers=headers(api)
        ).status_code
        == 200
    )
    for action, version in [("remove", 2), ("restore", 3)]:
        assert (
            api.post(
                path + "/" + action,
                json={"expected_version": version},
                headers=headers(api),
            ).status_code
            == 200
        )
    assert service.get(str(conference.record_id)) == conference
    participation = internal_create(
        service,
        record_data,
        record_type="participation",
        payload={
            "entry_type": "participation",
            "title": "Synthetic participation",
            "call_id": first["record_id"],
        },
    )
    assert (
        api.post(
            path + "/remove", json={"expected_version": 4}, headers=headers(api)
        ).status_code
        == 409
    )
    assert not service.get(str(participation.record_id)).deleted
